from __future__ import annotations

import json
import os
from typing import Any

from credit_committee.agents import AgentSpec
from credit_committee.models import AgentResult, Deal


def llm_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def provider_mode() -> str:
    return "openai" if llm_available() else "mock"


def build_agent_prompt(agent: AgentSpec, deal: Deal, prior_results: list[AgentResult]) -> str:
    prior = "\n".join(
        f"- {result.agent_name}: {result.stance}; {result.summary}"
        for result in prior_results
    ) or "No prior committee views."
    return f"""
You are the {agent.name} in an advisory private credit investment committee.

Remit: {agent.remit}
Primary lens: {agent.lens}

Deal:
- Borrower: {deal.borrower}
- Sponsor: {deal.sponsor}
- Sector: {deal.sector}
- Geography: {deal.geography}
- Revenue: {deal.revenue_m:.1f}m
- EBITDA: {deal.ebitda_m:.1f}m
- Total debt: {deal.total_debt_m:.1f}m
- Leverage: {deal.leverage:.2f}x
- Purchase price: {deal.purchase_price_m:.1f}m
- EV / EBITDA: {deal.enterprise_value_multiple:.2f}x
- Pricing: {deal.pricing}
- Use of proceeds: {deal.use_of_proceeds}
- Collateral/security: {deal.collateral}
- Covenants: {deal.covenants}
- Liquidity: {deal.liquidity}
- Investment thesis: {deal.thesis}
- Key risks: {deal.key_risks}

Prior committee views:
{prior}

Return strict JSON with these keys:
stance, summary, positives, concerns, diligence_questions, conditions, confidence.
Use short practical bullets. Stance must be one of Supportive, Cautious, Negative, Needs More Diligence.
Confidence is an integer from 1 to 100. This is advisory only; do not claim approval authority.
""".strip()


def run_agent(agent: AgentSpec, deal: Deal, prior_results: list[AgentResult]) -> AgentResult:
    if not llm_available():
        return mock_agent_result(agent, deal)
    return openai_agent_result(agent, deal, prior_results)


def openai_agent_result(agent: AgentSpec, deal: Deal, prior_results: list[AgentResult]) -> AgentResult:
    from openai import OpenAI

    client = OpenAI()
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You return strict JSON for an advisory private credit committee workflow.",
            },
            {"role": "user", "content": build_agent_prompt(agent, deal, prior_results)},
        ],
        response_format={"type": "json_object"},
    )
    payload = _coerce_payload(response.choices[0].message.content or "{}")
    return AgentResult(
        agent_id=agent.agent_id,
        agent_name=agent.name,
        stance=str(payload.get("stance", "Needs More Diligence")),
        summary=str(payload.get("summary", "")).strip(),
        positives=_listify(payload.get("positives")),
        concerns=_listify(payload.get("concerns")),
        diligence_questions=_listify(payload.get("diligence_questions")),
        conditions=_listify(payload.get("conditions")),
        confidence=int(payload.get("confidence", 60)),
    )


def mock_agent_result(agent: AgentSpec, deal: Deal) -> AgentResult:
    leverage = deal.leverage
    high_leverage = leverage >= 5.5
    thin_liquidity = "tight" in deal.liquidity.lower() or "limited" in deal.liquidity.lower()
    covenant_light = "cov-lite" in deal.covenants.lower() or "incurrence" in deal.covenants.lower()

    stance = "Cautious" if high_leverage or thin_liquidity or covenant_light else "Supportive"
    if high_leverage and covenant_light:
        stance = "Needs More Diligence"

    role_concern = {
        "originator": "Confirm sponsor alignment and whether economics compensate for execution complexity.",
        "credit_analyst": "Validate EBITDA quality, free cash flow conversion, and debt service capacity.",
        "risk_officer": "Quantify default and recovery under a severe downside case.",
        "legal_covenants": "Tighten covenant definitions, baskets, information rights, and enforcement triggers.",
        "portfolio_ops": "Confirm reporting cadence and early-warning KPIs the team can monitor post-close.",
        "esg": "Screen for reputational, regulatory, environmental, labor, and governance issues.",
        "macro": "Stress test rate, inflation, and demand-cycle pressure on margins and liquidity.",
        "industry_expert": "Benchmark the borrower against sector growth, churn, pricing power, and competitors.",
        "valuation": "Validate entry multiple, sponsor equity cushion, and collateral recovery support.",
        "documentation": "Make sure all assertions in the IC pack are sourced and decision conditions are auditable.",
    }[agent.agent_id]

    concerns = [role_concern]
    if high_leverage:
        concerns.append(f"Leverage of {leverage:.2f}x is elevated for a cash-flow loan.")
    if thin_liquidity:
        concerns.append("Liquidity description suggests limited cushion if performance slips.")
    if covenant_light:
        concerns.append("Covenant package may leave lenders reacting too late.")

    return AgentResult(
        agent_id=agent.agent_id,
        agent_name=agent.name,
        stance=stance,
        summary=(
            f"{agent.name} view: {deal.borrower} can be considered for committee discussion, "
            f"but the credit case depends on proving {deal.sector.lower()} resilience and lender protections."
        ),
        positives=[
            f"Sponsor is identified as {deal.sponsor}, enabling diligence on prior behavior.",
            f"Pricing and leverage are explicit: {deal.pricing}, {leverage:.2f}x debt / EBITDA.",
            "Structured facts are sufficient to frame an initial IC discussion.",
        ],
        concerns=concerns,
        diligence_questions=[
            "What is normalized EBITDA after one-time items and run-rate adjustments?",
            "How does liquidity hold up under a 15-25% EBITDA downside?",
            "Which covenant breach gives lenders the earliest practical intervention right?",
        ],
        conditions=[
            "Deliver quality of earnings support for adjusted EBITDA.",
            "Provide downside model with covenant headroom and liquidity bridge.",
            "Confirm final credit agreement includes agreed reporting and lender consent rights.",
        ],
        confidence=70 if stance == "Supportive" else 58,
    )


def _coerce_payload(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _listify(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []
