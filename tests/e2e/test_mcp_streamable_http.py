"""Streamable-HTTP transport conformance for the Kavach MCP server.

Launches the server as a subprocess over HTTP and connects the official MCP
streamable-http client. Proves the networked transport and the handshake;
tool calls that need a live API are covered by the memory-stream test.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from collections.abc import Iterator

import pytest

pytest.importorskip("mcp")

import anyio
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

_EXPECTED_TOOLS = {
    "decide",
    "verify_mandate",
    "issue_mandate",
    "resolve_step_up",
    "get_trust",
    "get_timeline",
}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_port(port: int, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    raise TimeoutError(f"MCP server did not open port {port}")


@pytest.fixture
def http_server_url() -> Iterator[str]:
    port = _free_port()
    proc = subprocess.Popen(  # noqa: S603 — fixed argv, our own module
        [
            sys.executable,
            "-m",
            "kavach.experiences.mcp_server",
            "--transport",
            "streamable-http",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
    )
    try:
        _wait_for_port(port)
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.mark.anyio
async def test_streamable_http_lists_tools(http_server_url: str) -> None:
    with anyio.fail_after(20):
        async with streamable_http_client(http_server_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                listed = await session.list_tools()
    names = {tool.name for tool in listed.tools}
    assert names >= _EXPECTED_TOOLS


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
