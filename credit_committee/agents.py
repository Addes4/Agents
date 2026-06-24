from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    name: str
    remit: str
    lens: str


AGENTS: list[AgentSpec] = [
    AgentSpec(
        "originator",
        "Sponsor / Originator",
        "Articulate the deal thesis, relationship angle, structure, and why the fund should spend IC time on the opportunity.",
        "commercial upside, sponsor quality, relationship value, execution feasibility",
    ),
    AgentSpec(
        "credit_analyst",
        "Credit Analyst",
        "Assess repayment capacity, leverage, cash generation, and fit with a senior secured private credit mandate.",
        "cash flow stability, leverage, pricing, debt capacity, downside case",
    ),
    AgentSpec(
        "risk_officer",
        "Downside / Risk Officer",
        "Challenge optimistic assumptions and identify principal impairment scenarios.",
        "loss severity, cyclicality, liquidity, refinancing risk, concentration risk",
    ),
    AgentSpec(
        "legal_covenants",
        "Legal / Covenants",
        "Evaluate documentation, controls, covenant protection, baskets, liens, and enforcement position.",
        "covenants, reporting, security package, creditor rights, documentation gaps",
    ),
    AgentSpec(
        "portfolio_ops",
        "Portfolio / Operations",
        "Assess monitoring practicality, operational complexity, sponsor responsiveness, and post-close workload.",
        "reporting cadence, KPI visibility, operational levers, amendment risk",
    ),
    AgentSpec(
        "esg",
        "ESG",
        "Identify ESG, reputational, regulatory, and exclusion-list issues relevant to a private credit lender.",
        "reputation, compliance, environmental exposure, labor practices, governance",
    ),
    AgentSpec(
        "macro",
        "Macro",
        "Assess rate, inflation, consumer/industrial cycle, and financing market sensitivity.",
        "rates, inflation, demand cycle, refinancing environment, macro downside",
    ),
    AgentSpec(
        "industry_expert",
        "Industry Expert",
        "Evaluate sector structure, competitive position, customer behavior, and barriers to entry.",
        "industry durability, competition, customer concentration, secular trends",
    ),
    AgentSpec(
        "valuation",
        "Valuation",
        "Review enterprise value, leverage attachment, sponsor equity cushion, and recovery implications.",
        "valuation multiple, equity cushion, recovery value, collateral coverage",
    ),
    AgentSpec(
        "documentation",
        "Documentation",
        "Check whether the IC pack has enough factual support and whether required approvals are traceable.",
        "source quality, missing facts, audit trail, decision record",
    ),
]
