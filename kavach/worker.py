"""Background worker entrypoint: drains the outbox to webhooks (ADR-0008).

Run with ``python -m kavach.worker``. Shares the substrate configuration
with the API service; only the outbox dispatcher loop runs here.
"""

from __future__ import annotations

import asyncio

from kavach.composition import build_substrate
from kavach.composition.config import SubstrateConfig
from kavach.composition.worker import WebhookDispatcher


async def _run() -> None:  # pragma: no cover - long-running loop
    substrate = build_substrate(SubstrateConfig())
    if substrate.config.auto_create_schema:
        await substrate.create_schema()
    dispatcher = WebhookDispatcher(substrate.session_factory)
    await dispatcher.run()


def main() -> None:  # pragma: no cover - process entrypoint
    asyncio.run(_run())


if __name__ == "__main__":  # pragma: no cover
    main()
