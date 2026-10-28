"""Multi-agent scorecard runner (pitch artifact, not a CI gate).

Runs a small population of agents through the customer-service rule set
in-process and writes a JSON scorecard plus a one-page Markdown summary.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from kavach.composition import SubstrateConfig, build_substrate
from kavach.events import utcnow
from kavach.events.schemas import Mandate, MandateConstraint
from kavach.usecases.customer_service import CustomerServiceRules


async def run_swarm(*, agents: int = 5) -> dict[str, Any]:
    substrate = build_substrate(
        SubstrateConfig(database_url="sqlite+aiosqlite:///:memory:"),
        rule_providers=[CustomerServiceRules()],
    )
    await substrate.create_schema()
    counts = {"allow": 0, "deny": 0, "step_up": 0}
    try:
        for index in range(agents):
            agent_id = f"agent-{index}"
            mandate = Mandate(
                mandate_id=f"m-{index}",
                originator_id="originator",
                originator_kind="human",
                agent_id=agent_id,
                action_scope=["account.funds.transfer", "kyc.*"],
                constraints=[
                    MandateConstraint(path="payment_amount.amount", operator="lte", value=100000)
                ],
                expires_at=utcnow() + timedelta(hours=1),
                nonce=f"n-{index}",
            )
            issued = await substrate.service.issue_mandate(tenant_id="swarm", mandate=mandate)
            stored = await substrate.service.get_mandate(
                tenant_id="swarm", mandate_id=issued.mandate_id
            )
            assert stored is not None
            kyc = await substrate.service.decide(
                tenant_id="swarm",
                agent_id=agent_id,
                session_id="s",
                action_type="kyc.document.verify",
                parameters={},
                use_case="customer_service",
            )
            transfer = await substrate.service.decide(
                tenant_id="swarm",
                agent_id=agent_id,
                session_id="s",
                action_type="account.funds.transfer",
                parameters={"amount": 80000 if index % 2 == 0 else 1000},
                use_case="customer_service",
                mandate_token=stored.token,
            )
            counts[kyc.outcome] += 1
            counts[transfer.outcome] += 1
    finally:
        await substrate.dispose()
    return {"agents": agents, "decisions": agents * 2, "outcomes": counts}


def render_markdown(scorecard: dict[str, Any]) -> str:
    outcomes = scorecard["outcomes"]
    return (
        "# Kavach swarm scorecard\n\n"
        f"Agents: {scorecard['agents']}. Decisions: {scorecard['decisions']}.\n\n"
        f"- allow: {outcomes['allow']}\n"
        f"- deny: {outcomes['deny']}\n"
        f"- step_up: {outcomes['step_up']}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Kavach swarm scorecard")
    parser.add_argument("--agents", type=int, default=5)
    parser.add_argument("--out", type=Path, default=Path("swarm-scorecard.json"))
    args = parser.parse_args()
    scorecard = asyncio.run(run_swarm(agents=args.agents))
    args.out.write_text(json.dumps(scorecard, indent=2))
    md = args.out.with_suffix(".md")
    md.write_text(render_markdown(scorecard))
    print(md.read_text())


if __name__ == "__main__":
    main()
