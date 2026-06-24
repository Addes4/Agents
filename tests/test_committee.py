from __future__ import annotations

import sqlite3

from credit_committee.db import init_db, list_deals, list_runs, save_deal, save_run
from credit_committee.llm import build_agent_prompt, mock_agent_result
from credit_committee.agents import AGENTS
from credit_committee.orchestrator import run_committee
from credit_committee.samples import sample_deals


def test_deal_validation_requires_core_fields() -> None:
    deal = sample_deals()["Healthcare services platform"]
    valid = deal.validate()
    assert valid == []

    deal.ebitda_m = 0
    assert "EBITDA must be greater than zero for credit metrics." in deal.validate()


def test_mock_agent_result_is_role_specific() -> None:
    deal = sample_deals()["Industrial software carve-out"]
    result = mock_agent_result(AGENTS[3], deal)

    assert result.agent_name == "Legal / Covenants"
    assert result.stance in {"Supportive", "Cautious", "Needs More Diligence"}
    assert result.conditions


def test_prompt_contains_structured_credit_metrics() -> None:
    deal = sample_deals()["Healthcare services platform"]
    prompt = build_agent_prompt(AGENTS[1], deal, [])

    assert "Leverage:" in prompt
    assert deal.borrower in prompt
    assert "Return strict JSON" in prompt


def test_committee_run_builds_ic_pack_in_mock_mode(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    deal = sample_deals()["Healthcare services platform"]
    run = run_committee(deal)

    assert len(run.agent_results) == len(AGENTS)
    assert "Advisory IC Pack" in run.ic_pack_markdown
    assert "Human Decision Record" in run.ic_pack_markdown
    assert run.mode == "mock"


def test_sqlite_persistence_round_trip() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    deal = sample_deals()["Healthcare services platform"]
    run = run_committee(deal)

    save_deal(conn, deal)
    save_run(conn, run)

    assert list_deals(conn)[0].borrower == deal.borrower
    assert list_runs(conn, deal.id)[0].ic_pack_markdown == run.ic_pack_markdown
