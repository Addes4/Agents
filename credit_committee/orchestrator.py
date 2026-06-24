from __future__ import annotations

from collections.abc import Callable
from statistics import mean

from credit_committee.agents import AGENTS
from credit_committee.ic_pack import build_ic_pack
from credit_committee.llm import (
    mock_chair_synthesis,
    mock_challenge_result,
    provider_mode,
    run_agent,
    run_chair_synthesis,
    run_challenge_agent,
)
from credit_committee.models import (
    AgentChallengeResult,
    AgentResult,
    AggregateScorecard,
    CommitteeRun,
    Deal,
    utc_now_iso,
)

SCORE_FIELDS = {
    "repayment_capacity": "Repayment capacity",
    "downside_resilience": "Downside resilience",
    "documentation_quality": "Documentation quality",
    "sponsor_support": "Sponsor support",
    "approval_readiness": "Approval readiness",
}


def run_committee(
    deal: Deal,
    on_agent_start: Callable[[str], None] | None = None,
    on_agent_done: Callable[[AgentResult], None] | None = None,
) -> CommitteeRun:
    first_round = run_first_round(deal, on_agent_start, on_agent_done)
    challenge_round = run_challenge_round(deal, first_round)
    aggregate_scorecard = build_scorecard(first_round)
    try:
        chair_synthesis = run_chair_synthesis(
            deal,
            first_round,
            challenge_round,
            aggregate_scorecard,
        )
    except Exception as exc:
        if not _is_rate_limit_error(exc):
            raise
        chair_synthesis = mock_chair_synthesis(
            deal,
            first_round,
            challenge_round,
            aggregate_scorecard,
        )
    mode = provider_mode()
    ic_pack_markdown = build_ic_pack(
        deal,
        first_round,
        mode,
        challenge_round,
        aggregate_scorecard,
        chair_synthesis,
    )
    return CommitteeRun(
        id=CommitteeRun.new_id(),
        deal_id=deal.id,
        mode=mode,
        created_at=utc_now_iso(),
        agent_results=first_round,
        challenge_results=challenge_round,
        aggregate_scorecard=aggregate_scorecard,
        chair_synthesis=chair_synthesis,
        ic_pack_markdown=ic_pack_markdown,
    )


def run_first_round(
    deal: Deal,
    on_agent_start: Callable[[str], None] | None = None,
    on_agent_done: Callable[[AgentResult], None] | None = None,
) -> list[AgentResult]:
    results: list[AgentResult] = []
    for agent in AGENTS:
        if on_agent_start:
            on_agent_start(f"First round: {agent.name}")
        result = run_agent(agent, deal, [])
        results.append(result)
        if on_agent_done:
            on_agent_done(result)
    return results


def run_challenge_round(
    deal: Deal,
    first_round: list[AgentResult],
) -> list[AgentChallengeResult]:
    results: list[AgentChallengeResult] = []
    for agent in AGENTS:
        try:
            results.append(run_challenge_agent(agent, deal, first_round))
        except Exception as exc:
            if not _is_rate_limit_error(exc):
                raise
            results.append(mock_challenge_result(agent, deal, first_round))
            remaining_agents = AGENTS[len(results):]
            results.extend(
                mock_challenge_result(remaining_agent, deal, first_round)
                for remaining_agent in remaining_agents
            )
            break
    return results


def build_scorecard(results: list[AgentResult]) -> AggregateScorecard:
    scorecards = [result.scorecard for result in results if result.scorecard is not None]
    if not scorecards:
        return AggregateScorecard()

    averages: dict[str, float] = {}
    disagreement_dimensions: list[str] = []
    for field in SCORE_FIELDS:
        values = [getattr(scorecard, field) for scorecard in scorecards]
        averages[field] = round(mean(values), 1)
        if max(values) - min(values) >= 2:
            disagreement_dimensions.append(SCORE_FIELDS[field])

    lowest_field = min(averages, key=averages.get)
    return AggregateScorecard(
        repayment_capacity=averages["repayment_capacity"],
        downside_resilience=averages["downside_resilience"],
        documentation_quality=averages["documentation_quality"],
        sponsor_support=averages["sponsor_support"],
        approval_readiness=averages["approval_readiness"],
        lowest_dimension=SCORE_FIELDS[lowest_field],
        lowest_score=averages[lowest_field],
        disagreement_dimensions=disagreement_dimensions,
    )


def _is_rate_limit_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    message = str(exc).lower()
    return status_code == 429 or "rate_limit" in message or "rate limit" in message
