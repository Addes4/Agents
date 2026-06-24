from __future__ import annotations

from collections.abc import Callable

from credit_committee.agents import AGENTS
from credit_committee.ic_pack import build_ic_pack
from credit_committee.llm import provider_mode, run_agent
from credit_committee.models import AgentResult, CommitteeRun, Deal, utc_now_iso


def run_committee(
    deal: Deal,
    on_agent_start: Callable[[str], None] | None = None,
    on_agent_done: Callable[[AgentResult], None] | None = None,
) -> CommitteeRun:
    results: list[AgentResult] = []
    for agent in AGENTS:
        if on_agent_start:
            on_agent_start(agent.name)
        result = run_agent(agent, deal, results)
        results.append(result)
        if on_agent_done:
            on_agent_done(result)

    mode = provider_mode()
    return CommitteeRun(
        id=CommitteeRun.new_id(),
        deal_id=deal.id,
        mode=mode,
        created_at=utc_now_iso(),
        agent_results=results,
        ic_pack_markdown=build_ic_pack(deal, results, mode),
    )
