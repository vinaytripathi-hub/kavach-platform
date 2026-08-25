"""Customer Service policy rules (the use case configures the substrate).

This module implements the ``PolicyRuleProvider`` extension point
(ADR-0007): it supplies the rule set the substrate's policy capability
evaluates for customer-service agents. The action schema reflects the
process-owner model (ADR-0005 / EU AI Act Art. 25): benign read/KYC/
complaint actions execute automatically; high-value money movement is
escalated to a human (Art. 14); anything outside the schema is denied.
"""

from __future__ import annotations

from kavach.capabilities.policy import (
    PolicyCondition,
    PolicyRule,
    PolicyRuleSet,
)

USE_CASE = "customer_service"

# Threshold (in account currency minor units or rupees) above which a
# funds transfer must be approved by a human operator.
HIGH_VALUE_TRANSFER_THRESHOLD = 50000


def build_rule_set() -> PolicyRuleSet:
    """The Customer Service rule set (default-deny, with explicit allows)."""
    return PolicyRuleSet(
        use_case=USE_CASE,
        version="cs-1",
        default_effect="deny",
        default_step_up_role="supervisor",
        rules=[
            PolicyRule(
                rule_id="allow-kyc",
                description="KYC verification actions are permitted.",
                action_type="kyc.*",
                effect="allow",
                priority=10,
            ),
            PolicyRule(
                rule_id="allow-complaint",
                description="Complaint handling actions are permitted.",
                action_type="complaint.*",
                effect="allow",
                priority=10,
            ),
            PolicyRule(
                rule_id="allow-account-read",
                description="Read-only account operations are permitted.",
                action_type="account.read.*",
                effect="allow",
                priority=10,
            ),
            PolicyRule(
                rule_id="stepup-high-value-transfer",
                description=(
                    "Funds transfers above the high-value threshold require "
                    "human approval (EU AI Act Article 14)."
                ),
                action_type="account.funds.transfer",
                effect="step_up",
                conditions=[
                    PolicyCondition(
                        attribute="parameters.amount",
                        operator="gt",
                        value=HIGH_VALUE_TRANSFER_THRESHOLD,
                    )
                ],
                step_up_role="senior_ops",
                priority=10,
            ),
            PolicyRule(
                rule_id="allow-low-value-transfer",
                description="Low-value transfers are permitted automatically.",
                action_type="account.funds.transfer",
                effect="allow",
                priority=20,
            ),
        ],
    )


class CustomerServiceRules:
    """Rule provider for the Customer Service use case (ADR-0007)."""

    use_case = USE_CASE

    def rule_set(self) -> PolicyRuleSet:
        return build_rule_set()
