from __future__ import annotations

import json
import os
from typing import Any

from credit_committee.agents import AgentSpec
from credit_committee.models import (
    AgentChallengeResult,
    AgentResult,
    AgentScorecard,
    AggregateScorecard,
    ChairSynthesis,
    Deal,
)

VALID_STANCES = {"Supportive", "Cautious", "Negative", "Needs More Diligence"}
VALID_RECOMMENDATIONS = {"Approve", "Approve with Conditions", "Defer", "Decline"}
VALID_RISK_RATINGS = {"Low", "Medium", "High"}
SCORE_FIELDS = [
    "repayment_capacity",
    "downside_resilience",
    "documentation_quality",
    "sponsor_support",
    "approval_readiness",
]


def llm_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def provider_mode() -> str:
    return "openai" if llm_available() else "mock"


def build_agent_prompt(agent: AgentSpec, deal: Deal, prior_results: list[AgentResult]) -> str:
    return f"""
You are the {agent.name} in an advisory private credit investment committee.
This is the first round. Form an independent view; do not assume any other committee member agrees.

Remit: {agent.remit}
Primary lens: {agent.lens}

{_deal_block(deal)}

Return strict JSON with these keys:
stance, recommendation, risk_rating, summary, known_facts, assumptions, missing_diligence, judgment, positives, concerns, mitigants, dissent, diligence_questions, conditions, scorecard, confidence.
Use short practical bullets. Stance must be one of Supportive, Cautious, Negative, Needs More Diligence.
Recommendation must be one of Approve, Approve with Conditions, Defer, Decline.
Risk rating must be one of Low, Medium, High.
Scorecard must be an object with integer 1-5 values for repayment_capacity, downside_resilience, documentation_quality, sponsor_support, approval_readiness.
Summarize concrete investment judgment, not generic process advice. Include at least one challenge or dissent point where relevant.
Confidence is an integer from 1 to 100. This is advisory only; do not claim approval authority.
""".strip()


def run_agent(agent: AgentSpec, deal: Deal, prior_results: list[AgentResult]) -> AgentResult:
    if not llm_available():
        return mock_agent_result(agent, deal)
    return openai_agent_result(agent, deal, prior_results)


def openai_agent_result(agent: AgentSpec, deal: Deal, prior_results: list[AgentResult]) -> AgentResult:
    payload = _openai_json(build_agent_prompt(agent, deal, prior_results))
    return AgentResult(
        agent_id=agent.agent_id,
        agent_name=agent.name,
        stance=_choice(payload.get("stance"), VALID_STANCES, "Needs More Diligence"),
        recommendation=_choice(payload.get("recommendation"), VALID_RECOMMENDATIONS, "Defer"),
        risk_rating=_choice(payload.get("risk_rating"), VALID_RISK_RATINGS, "Medium"),
        summary=str(payload.get("summary", "")).strip(),
        known_facts=_listify(payload.get("known_facts")),
        assumptions=_listify(payload.get("assumptions")),
        missing_diligence=_listify(payload.get("missing_diligence")),
        judgment=str(payload.get("judgment", "")).strip(),
        positives=_listify(payload.get("positives")),
        concerns=_listify(payload.get("concerns")),
        mitigants=_listify(payload.get("mitigants")),
        dissent=_listify(payload.get("dissent")),
        diligence_questions=_listify(payload.get("diligence_questions")),
        conditions=_listify(payload.get("conditions")),
        scorecard=_scorecard(payload.get("scorecard")),
        confidence=_confidence(payload.get("confidence")),
    )


def build_challenge_prompt(
    agent: AgentSpec,
    deal: Deal,
    first_round: list[AgentResult],
) -> str:
    committee_views = "\n".join(
        (
            f"- {result.agent_name}: {result.recommendation}, {result.risk_rating} risk, "
            f"{result.summary} Concerns: {'; '.join(result.concerns[:3]) or 'None'}"
        )
        for result in first_round
    )
    return f"""
You are the {agent.name} in the challenge round of an advisory private credit committee.

Remit: {agent.remit}
Primary lens: {agent.lens}

{_deal_block(deal)}

First-round committee views:
{committee_views}

Return strict JSON with these keys:
changed_recommendation, revised_recommendation, agreement_points, challenge_points, unresolved_issues, what_would_change_view, confidence.
changed_recommendation must be boolean.
revised_recommendation must be one of Approve, Approve with Conditions, Defer, Decline.
Challenge at least one assumption, missing diligence item, or optimistic conclusion from the first round.
Confidence is an integer from 1 to 100. This is advisory only; do not claim approval authority.
""".strip()


def run_challenge_agent(
    agent: AgentSpec,
    deal: Deal,
    first_round: list[AgentResult],
) -> AgentChallengeResult:
    if not llm_available():
        return mock_challenge_result(agent, deal, first_round)
    return openai_challenge_result(agent, deal, first_round)


def openai_challenge_result(
    agent: AgentSpec,
    deal: Deal,
    first_round: list[AgentResult],
) -> AgentChallengeResult:
    payload = _openai_json(build_challenge_prompt(agent, deal, first_round))
    return AgentChallengeResult(
        agent_id=agent.agent_id,
        agent_name=agent.name,
        changed_recommendation=_bool(payload.get("changed_recommendation")),
        revised_recommendation=_choice(
            payload.get("revised_recommendation"),
            VALID_RECOMMENDATIONS,
            "Defer",
        ),
        agreement_points=_listify(payload.get("agreement_points")),
        challenge_points=_listify(payload.get("challenge_points")),
        unresolved_issues=_listify(payload.get("unresolved_issues")),
        what_would_change_view=_listify(payload.get("what_would_change_view")),
        confidence=_confidence(payload.get("confidence")),
    )


def build_chair_prompt(
    deal: Deal,
    first_round: list[AgentResult],
    challenge_round: list[AgentChallengeResult],
    aggregate_scorecard: AggregateScorecard,
) -> str:
    first_views = "\n".join(
        f"- {result.agent_name}: {result.recommendation}; {result.summary}"
        for result in first_round
    )
    challenges = "\n".join(
        f"- {result.agent_name}: {'; '.join(result.challenge_points[:2]) or 'No challenge'}"
        for result in challenge_round
    )
    return f"""
You are the IC Chair synthesizing an advisory private credit committee.

{_deal_block(deal)}

First-round views:
{first_views}

Challenge-round points:
{challenges}

Aggregate scorecard:
- Repayment capacity: {aggregate_scorecard.repayment_capacity:.1f}/5
- Downside resilience: {aggregate_scorecard.downside_resilience:.1f}/5
- Documentation quality: {aggregate_scorecard.documentation_quality:.1f}/5
- Sponsor support: {aggregate_scorecard.sponsor_support:.1f}/5
- Approval readiness: {aggregate_scorecard.approval_readiness:.1f}/5
- Lowest dimension: {aggregate_scorecard.lowest_dimension} ({aggregate_scorecard.lowest_score:.1f}/5)
- Disagreement dimensions: {', '.join(aggregate_scorecard.disagreement_dimensions or []) or 'None'}

Return strict JSON with these keys:
final_advisory_recommendation, committee_rationale, majority_view, dissenting_view, gating_diligence, approval_conditions, scorecard_interpretation, what_would_change_recommendation.
final_advisory_recommendation must be one of Approve, Approve with Conditions, Defer, Decline.
Be concise, specific, and advisory only. Humans make the final decision.
""".strip()


def run_chair_synthesis(
    deal: Deal,
    first_round: list[AgentResult],
    challenge_round: list[AgentChallengeResult],
    aggregate_scorecard: AggregateScorecard,
) -> ChairSynthesis:
    if not llm_available():
        return mock_chair_synthesis(deal, first_round, challenge_round, aggregate_scorecard)
    payload = _openai_json(build_chair_prompt(deal, first_round, challenge_round, aggregate_scorecard))
    return ChairSynthesis(
        final_advisory_recommendation=_choice(
            payload.get("final_advisory_recommendation"),
            VALID_RECOMMENDATIONS,
            "Defer",
        ),
        committee_rationale=str(payload.get("committee_rationale", "")).strip(),
        majority_view=_listify(payload.get("majority_view")),
        dissenting_view=_listify(payload.get("dissenting_view")),
        gating_diligence=_listify(payload.get("gating_diligence")),
        approval_conditions=_listify(payload.get("approval_conditions")),
        scorecard_interpretation=str(payload.get("scorecard_interpretation", "")).strip(),
        what_would_change_recommendation=_listify(payload.get("what_would_change_recommendation")),
    )


def mock_agent_result(agent: AgentSpec, deal: Deal) -> AgentResult:
    leverage = deal.leverage
    high_leverage = leverage >= 5.5
    thin_liquidity = "tight" in deal.liquidity.lower() or "limited" in deal.liquidity.lower()
    covenant_light = "cov-lite" in deal.covenants.lower() or "incurrence" in deal.covenants.lower()
    weak_fcf = "40" in deal.fcf_conversion or "limited" in deal.fcf_conversion.lower()

    stance = "Cautious" if high_leverage or thin_liquidity or covenant_light else "Supportive"
    if high_leverage and covenant_light:
        stance = "Needs More Diligence"
    recommendation = "Approve with Conditions" if stance == "Supportive" else "Defer"
    risk_rating = "High" if high_leverage and covenant_light else "Medium"
    if stance == "Supportive" and not weak_fcf:
        risk_rating = "Low"

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
    if weak_fcf:
        concerns.append("Free cash flow conversion may be thin during the underwriting period.")

    return AgentResult(
        agent_id=agent.agent_id,
        agent_name=agent.name,
        stance=stance,
        recommendation=recommendation,
        risk_rating=risk_rating,
        summary=(
            f"{agent.name} view: {deal.borrower} can be considered for committee discussion, "
            f"but the recommendation depends on validating cash conversion, covenant protection, "
            f"and sponsor support for a {deal.leverage:.2f}x structure."
        ),
        positives=[
            f"Sponsor is identified as {deal.sponsor}, enabling diligence on prior behavior.",
            f"Pricing and leverage are explicit: {deal.pricing}, {leverage:.2f}x debt / EBITDA.",
            f"Sponsor equity is {deal.sponsor_equity_m:.1f}m, or {deal.sponsor_equity_percentage:.1%} of EV.",
            "Structured facts are sufficient to frame an initial IC discussion.",
        ],
        concerns=concerns,
        known_facts=[
            f"Debt / EBITDA is {leverage:.2f}x.",
            f"Sponsor equity is {deal.sponsor_equity_m:.1f}m.",
            f"Covenant headroom: {deal.covenant_headroom or 'not provided'}.",
        ],
        assumptions=[
            "Management adjustments and sponsor projections require diligence support.",
            "Liquidity and FCF conversion are based on intake text, not a model.",
        ],
        missing_diligence=[
            "Quality of earnings bridge to underwritten EBITDA.",
            "Downside model showing liquidity and covenant headroom.",
        ],
        judgment=(
            "Proceed only if diligence confirms recurring cash flow, covenant intervention rights, "
            "and adequate sponsor support."
        ),
        mitigants=[
            "Require quality of earnings support and customer diligence before final committee approval.",
            "Tie final hold size and documentation flexibility to covenant headroom and FCF conversion.",
        ],
        dissent=[
            "Committee should challenge whether downside liquidity remains adequate after interest and required capex.",
        ],
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
        scorecard=AgentScorecard(
            repayment_capacity=3 if high_leverage else 4,
            downside_resilience=2 if thin_liquidity or weak_fcf else 3,
            documentation_quality=2 if covenant_light else 4,
            sponsor_support=4 if deal.sponsor_equity_percentage >= 0.35 else 3,
            approval_readiness=2 if stance == "Needs More Diligence" else 3,
        ),
        confidence=70 if stance == "Supportive" else 58,
    )


def mock_challenge_result(
    agent: AgentSpec,
    deal: Deal,
    first_round: list[AgentResult],
) -> AgentChallengeResult:
    original = next((result for result in first_round if result.agent_id == agent.agent_id), None)
    revised = original.recommendation if original else "Defer"
    challenge_points = [
        "Challenge whether downside liquidity remains adequate after cash interest and required capex.",
        "Confirm covenant headroom is based on lender-defined EBITDA, not sponsor-adjusted EBITDA.",
    ]
    if deal.leverage >= 5.5:
        revised = "Defer"
        challenge_points.append("Elevated leverage should prevent approval until downside debt capacity is proven.")
    return AgentChallengeResult(
        agent_id=agent.agent_id,
        agent_name=agent.name,
        changed_recommendation=bool(original and revised != original.recommendation),
        revised_recommendation=revised,
        agreement_points=[
            "The committee agrees that cash conversion and covenant protection are gating topics.",
        ],
        challenge_points=challenge_points,
        unresolved_issues=[
            "Normalized EBITDA, downside liquidity, and final documentation terms remain unresolved.",
        ],
        what_would_change_view=[
            "A supported downside case with acceptable covenant headroom and liquidity would improve the view.",
            "Weak QofE support or loose documentation would push the view toward decline.",
        ],
        confidence=62,
    )


def mock_chair_synthesis(
    deal: Deal,
    first_round: list[AgentResult],
    challenge_round: list[AgentChallengeResult],
    aggregate_scorecard: AggregateScorecard,
) -> ChairSynthesis:
    recommendations = [result.revised_recommendation for result in challenge_round]
    if "Decline" in recommendations:
        final = "Decline"
    elif recommendations.count("Defer") >= 3 or aggregate_scorecard.approval_readiness < 3:
        final = "Defer"
    elif aggregate_scorecard.documentation_quality < 3:
        final = "Approve with Conditions"
    else:
        final = "Approve with Conditions"
    return ChairSynthesis(
        final_advisory_recommendation=final,
        committee_rationale=(
            f"The committee view for {deal.borrower} is {final} because leverage, FCF conversion, "
            "liquidity, and documentation quality remain the key approval gates."
        ),
        majority_view=[
            "The opportunity is reviewable if diligence validates EBITDA quality and cash conversion.",
            "Approval should depend on covenant protection, liquidity headroom, and final documentation.",
        ],
        dissenting_view=[
            "The downside case may not support the proposed leverage without tighter lender controls.",
        ],
        gating_diligence=[
            "Quality of earnings support for adjusted EBITDA.",
            "Downside model with liquidity bridge and covenant headroom.",
            "Final documentation grid covering reporting, baskets, and consent rights.",
        ],
        approval_conditions=[
            "Satisfactory QofE and customer diligence.",
            "Documented covenant package with early intervention rights.",
            "Final hold size sized to downside debt capacity.",
        ],
        scorecard_interpretation=(
            f"Lowest score is {aggregate_scorecard.lowest_dimension} at "
            f"{aggregate_scorecard.lowest_score:.1f}/5."
        ),
        what_would_change_recommendation=[
            "Improved downside liquidity and covenant headroom would support approval.",
            "Weaker EBITDA support or looser documentation would push the recommendation lower.",
        ],
    )


def _deal_block(deal: Deal) -> str:
    return f"""
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
- Sponsor equity: {deal.sponsor_equity_m:.1f}m ({deal.sponsor_equity_percentage:.1%} of EV)
- Debt type: {deal.debt_type or "Not provided"}
- Cash interest: {deal.cash_interest or "Not provided"}
- Amortization: {deal.amortization or "Not provided"}
- Maturity: {deal.maturity or "Not provided"}
- Pricing: {deal.pricing}
- FCF conversion: {deal.fcf_conversion or "Not provided"}
- Covenant headroom: {deal.covenant_headroom or "Not provided"}
- Use of proceeds: {deal.use_of_proceeds}
- Collateral/security: {deal.collateral}
- Covenants: {deal.covenants}
- Liquidity: {deal.liquidity}
- Investment thesis: {deal.thesis}
- Key risks: {deal.key_risks}
""".strip()


def _openai_json(prompt: str) -> dict[str, Any]:
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
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    return _coerce_payload(response.choices[0].message.content or "{}")


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


def _choice(value: Any, valid: set[str], default: str) -> str:
    text = str(value or "").strip()
    return text if text in valid else default


def _confidence(value: Any) -> int:
    try:
        confidence = int(value)
    except (TypeError, ValueError):
        return 60
    return max(1, min(100, confidence))


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return bool(value)


def _scorecard(value: Any) -> AgentScorecard:
    return AgentScorecard.from_dict(value if isinstance(value, dict) else {})
