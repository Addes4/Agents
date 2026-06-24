from __future__ import annotations

from collections import Counter

from credit_committee.models import (
    AgentChallengeResult,
    AgentResult,
    AggregateScorecard,
    ChairSynthesis,
    Deal,
)


def build_ic_pack(
    deal: Deal,
    results: list[AgentResult],
    mode: str,
    challenge_results: list[AgentChallengeResult] | None = None,
    aggregate_scorecard: AggregateScorecard | None = None,
    chair_synthesis: ChairSynthesis | None = None,
) -> str:
    challenge_results = challenge_results or []
    aggregate_scorecard = aggregate_scorecard or AggregateScorecard()
    chair_synthesis = chair_synthesis or ChairSynthesis()
    stance_counts = Counter(result.stance for result in results)
    recommendation_counts = Counter(result.recommendation for result in results)
    risk_counts = Counter(result.risk_rating for result in results)
    top_concerns = _top_items([item for result in results for item in result.concerns], 8)
    top_mitigants = _top_items([item for result in results for item in (result.mitigants or [])], 6)
    top_dissent = _top_items(
        [item for result in results for item in (result.dissent or [])]
        + [item for result in challenge_results for item in result.challenge_points],
        8,
    )
    top_questions = _top_items([item for result in results for item in result.diligence_questions], 8)
    top_conditions = _top_items(
        (chair_synthesis.approval_conditions or [])
        + [item for result in results for item in result.conditions],
        8,
    )
    missing_diligence = _top_items(
        (chair_synthesis.gating_diligence or [])
        + [item for result in results for item in (result.missing_diligence or [])],
        8,
    )
    assumptions = _top_items([item for result in results for item in (result.assumptions or [])], 8)

    return "\n".join(
        [
            f"# Advisory IC Pack: {deal.borrower}",
            "",
            "> Synthetic/demo output. Advisory only; final decisions must be made and recorded by humans.",
            "",
            "## Executive Summary",
            f"- Chair advisory recommendation: {chair_synthesis.final_advisory_recommendation}",
            f"- Borrower: {deal.borrower}",
            f"- Sponsor: {deal.sponsor}",
            f"- Sector / geography: {deal.sector} / {deal.geography}",
            f"- EBITDA: {deal.ebitda_m:.1f}m; debt: {deal.total_debt_m:.1f}m; leverage: {deal.leverage:.2f}x",
            f"- Sponsor equity: {deal.sponsor_equity_m:.1f}m ({deal.sponsor_equity_percentage:.1%} of EV)",
            f"- Pricing: {deal.pricing}",
            f"- Committee mode: {mode}",
            f"- Advisory stance mix: {_format_counts(stance_counts)}",
            f"- Recommendation mix: {_format_counts(recommendation_counts)}",
            f"- Risk rating mix: {_format_counts(risk_counts)}",
            f"- Chair rationale: {chair_synthesis.committee_rationale or 'No chair rationale generated.'}",
            "",
            "## Scorecard",
            *_scorecard_lines(aggregate_scorecard),
            f"- Interpretation: {chair_synthesis.scorecard_interpretation or 'No scorecard interpretation generated.'}",
            "",
            "## Credit Structure",
            f"- Debt type: {deal.debt_type or 'Not provided'}",
            f"- Cash interest: {deal.cash_interest or 'Not provided'}",
            f"- Amortization: {deal.amortization or 'Not provided'}",
            f"- Maturity: {deal.maturity or 'Not provided'}",
            f"- FCF conversion: {deal.fcf_conversion or 'Not provided'}",
            f"- Covenant headroom: {deal.covenant_headroom or 'Not provided'}",
            "",
            "## Credit Thesis",
            deal.thesis,
            "",
            "## Top Risks",
            *_bullet_lines(top_concerns),
            "",
            "## Mitigants",
            *_bullet_lines(top_mitigants),
            "",
            "## Agent Debate",
            *_bullet_lines(top_dissent),
            "",
            "## Majority View",
            *_bullet_lines(chair_synthesis.majority_view or []),
            "",
            "## Dissenting View",
            *_bullet_lines(chair_synthesis.dissenting_view or []),
            "",
            "## Assumptions",
            *_bullet_lines(assumptions),
            "",
            "## Missing Diligence",
            *_numbered_lines(missing_diligence),
            "",
            "## Challenge Round Summary",
            *[_format_challenge(result) for result in challenge_results],
            "",
            "## Agent Views",
            *[_format_agent(result) for result in results],
            "",
            "## Diligence Grid",
            *_numbered_lines(top_questions),
            "",
            "## Required Conditions Before Human Approval",
            *_numbered_lines(top_conditions),
            "",
            "## What Would Change The Recommendation",
            *_bullet_lines(chair_synthesis.what_would_change_recommendation or []),
            "",
            "## Human Decision Record",
            "- Final decision: Pending",
            "- Decision maker(s):",
            "- Date:",
            "- Conditions accepted / waived:",
            "- Rationale:",
        ]
    )


def _format_counts(counts: Counter[str]) -> str:
    if not counts:
        return "No agent views generated"
    return ", ".join(f"{stance}: {count}" for stance, count in counts.items())


def _advisory_recommendation(counts: Counter[str]) -> str:
    if not counts:
        return "Defer"
    priority = ["Decline", "Defer", "Approve with Conditions", "Approve"]
    return max(priority, key=lambda recommendation: (counts[recommendation], -priority.index(recommendation)))


def _top_items(items: list[str], limit: int) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.append(item)
    return seen[:limit]


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] or ["- None identified."]


def _numbered_lines(items: list[str]) -> list[str]:
    return [f"{index}. {item}" for index, item in enumerate(items, start=1)] or ["1. None identified."]


def _scorecard_lines(scorecard: AggregateScorecard) -> list[str]:
    return [
        f"- Repayment capacity: {scorecard.repayment_capacity:.1f}/5",
        f"- Downside resilience: {scorecard.downside_resilience:.1f}/5",
        f"- Documentation quality: {scorecard.documentation_quality:.1f}/5",
        f"- Sponsor support: {scorecard.sponsor_support:.1f}/5",
        f"- Approval readiness: {scorecard.approval_readiness:.1f}/5",
        f"- Lowest dimension: {scorecard.lowest_dimension or 'None'} ({scorecard.lowest_score:.1f}/5)",
        f"- Disagreement dimensions: {', '.join(scorecard.disagreement_dimensions or []) or 'None'}",
    ]


def _format_challenge(result: AgentChallengeResult) -> str:
    challenges = "; ".join(result.challenge_points[:3]) or "No challenge points."
    unresolved = "; ".join(result.unresolved_issues[:2]) or "No unresolved issues."
    return (
        f"### {result.agent_name}\n"
        f"- Revised recommendation: {result.revised_recommendation}"
        f" ({'changed' if result.changed_recommendation else 'unchanged'})\n"
        f"- Challenge points: {challenges}\n"
        f"- Unresolved issues: {unresolved}\n"
    )


def _format_agent(result: AgentResult) -> str:
    concerns = "; ".join(result.concerns[:3]) or "No major concerns."
    mitigants = "; ".join((result.mitigants or [])[:2]) or "No specific mitigants."
    dissent = "; ".join((result.dissent or [])[:2]) or "No dissent noted."
    missing = "; ".join((result.missing_diligence or [])[:2]) or "No missing diligence noted."
    return (
        f"### {result.agent_name}\n"
        f"- Recommendation: {result.recommendation}; risk rating: {result.risk_rating}\n"
        f"- Stance: {result.stance} ({result.confidence}% confidence)\n"
        f"- Summary: {result.summary}\n"
        f"- Judgment: {result.judgment or 'No judgment supplied.'}\n"
        f"- Key concerns: {concerns}\n"
        f"- Mitigants: {mitigants}\n"
        f"- Challenge points: {dissent}\n"
        f"- Missing diligence: {missing}\n"
    )
