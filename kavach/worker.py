"""Background worker entrypoint: drains the outbox to webhooks (ADR-0008).

Run with ``python -m kavach.worker``. Shares the substrate configuration
with the API service; only the outbox dispatcher loop runs here.
"""

from __future__ import annotations

import asyncio

from kavach.capabilities.signals.dispatch import SignalDispatcher
from kavach.composition import build_substrate
from kavach.composition.config import SubstrateConfig
from kavach.composition.worker import WebhookDispatcher, httpx_sender


async def _run() -> None:  # pragma: no cover - long-running loop
    substrate = build_substrate(SubstrateConfig())
    if substrate.config.auto_create_schema:
        await substrate.create_schema()
    dispatcher = WebhookDispatcher(substrate.session_factory)
    signals = SignalDispatcher(
        substrate.session_factory,
        httpx_sender,
        receiver_url=substrate.config.signal_receiver_url,
        issuer=substrate.config.signal_issuer,
        audience=substrate.config.signal_audience,
        key=substrate.config.jwt_secret.encode("utf-8"),
    )
    await asyncio.gather(dispatcher.run(), signals.run())


def main() -> None:  # pragma: no cover - process entrypoint
    asyncio.run(_run())


if __name__ == "__main__":  # pragma: no cover
    main()
