from __future__ import annotations

from collections import Counter

from credit_committee.models import AgentResult, Deal


def build_ic_pack(deal: Deal, results: list[AgentResult], mode: str) -> str:
    stance_counts = Counter(result.stance for result in results)
    top_concerns = _top_items([item for result in results for item in result.concerns], 8)
    top_questions = _top_items([item for result in results for item in result.diligence_questions], 8)
    top_conditions = _top_items([item for result in results for item in result.conditions], 8)

    return "\n".join(
        [
            f"# Advisory IC Pack: {deal.borrower}",
            "",
            "> Synthetic/demo output. Advisory only; final decisions must be made and recorded by humans.",
            "",
            "## Executive Summary",
            f"- Borrower: {deal.borrower}",
            f"- Sponsor: {deal.sponsor}",
            f"- Sector / geography: {deal.sector} / {deal.geography}",
            f"- EBITDA: {deal.ebitda_m:.1f}m; debt: {deal.total_debt_m:.1f}m; leverage: {deal.leverage:.2f}x",
            f"- Pricing: {deal.pricing}",
            f"- Committee mode: {mode}",
            f"- Advisory stance mix: {_format_counts(stance_counts)}",
            "",
            "## Credit Thesis",
            deal.thesis,
            "",
            "## Risk Matrix",
            *_bullet_lines(top_concerns),
            "",
            "## Agent Views",
            *[_format_agent(result) for result in results],
            "",
            "## Open Diligence Questions",
            *_bullet_lines(top_questions),
            "",
            "## Required Conditions Before Human Approval",
            *_bullet_lines(top_conditions),
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


def _top_items(items: list[str], limit: int) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.append(item)
    return seen[:limit]


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] or ["- None identified."]


def _format_agent(result: AgentResult) -> str:
    concerns = "; ".join(result.concerns[:3]) or "No major concerns."
    return (
        f"### {result.agent_name}\n"
        f"- Stance: {result.stance} ({result.confidence}% confidence)\n"
        f"- Summary: {result.summary}\n"
        f"- Key concerns: {concerns}\n"
    )
