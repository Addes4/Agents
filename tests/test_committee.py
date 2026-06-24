from __future__ import annotations

import sqlite3
from zipfile import ZipFile

from credit_committee.db import init_db, list_deals, list_runs, save_deal, save_run
from credit_committee.llm import (
    _bool,
    _confidence,
    _choice,
    _scorecard,
    build_agent_prompt,
    mock_agent_result,
)
from credit_committee.agents import AGENTS
from credit_committee.models import AgentResult, AgentScorecard, CommitteeRun, Deal
import credit_committee.orchestrator as orchestrator
from credit_committee.orchestrator import build_scorecard, run_committee
from credit_committee.pptx_export import build_ic_memo_pptx
from credit_committee.samples import sample_deals


def test_deal_validation_requires_core_fields() -> None:
    deal = sample_deals()["Healthcare services platform"]
    valid = deal.validate()
    assert valid == []

    deal.ebitda_m = 0
    assert "EBITDA must be greater than zero for credit metrics." in deal.validate()


def test_deal_from_dict_defaults_new_credit_fields() -> None:
    values = {
        "id": "deal-1",
        "borrower": "Borrower",
        "sponsor": "Sponsor",
        "sector": "Software",
        "geography": "United States",
        "revenue_m": 100.0,
        "ebitda_m": 20.0,
        "total_debt_m": 80.0,
        "purchase_price_m": 200.0,
        "pricing": "SOFR + 600",
        "use_of_proceeds": "Buyout",
        "collateral": "First lien",
        "covenants": "Maintenance leverage covenant",
        "liquidity": "Adequate",
        "thesis": "Recurring revenue.",
        "key_risks": "Churn.",
        "created_at": "2026-01-01T00:00:00+00:00",
    }

    deal = Deal.from_dict(values)

    assert deal.debt_type == ""
    assert deal.sponsor_equity_m == 0.0


def test_mock_agent_result_is_role_specific() -> None:
    deal = sample_deals()["Industrial software carve-out"]
    result = mock_agent_result(AGENTS[3], deal)

    assert result.agent_name == "Legal / Covenants"
    assert result.stance in {"Supportive", "Cautious", "Needs More Diligence"}
    assert result.recommendation in {"Approve with Conditions", "Defer"}
    assert result.risk_rating in {"Low", "Medium", "High"}
    assert result.conditions


def test_prompt_contains_structured_credit_metrics() -> None:
    deal = sample_deals()["Healthcare services platform"]
    prompt = build_agent_prompt(AGENTS[1], deal, [])

    assert "Leverage:" in prompt
    assert "Sponsor equity:" in prompt
    assert "Covenant headroom:" in prompt
    assert deal.borrower in prompt
    assert "Return strict JSON" in prompt
    assert "recommendation" in prompt


def test_llm_normalizers_reject_invalid_values() -> None:
    assert _choice("Approve", {"Approve", "Defer"}, "Defer") == "Approve"
    assert _choice("Maybe", {"Approve", "Defer"}, "Defer") == "Defer"
    assert _confidence("120") == 100
    assert _confidence("0") == 1
    assert _confidence("bad") == 60
    assert _bool("yes") is True
    assert _bool("") is False
    assert _scorecard({"repayment_capacity": 9}).repayment_capacity == 5


def test_agent_result_from_dict_defaults_new_fields() -> None:
    result = AgentResult.from_dict(
        {
            "agent_id": "credit_analyst",
            "agent_name": "Credit Analyst",
            "stance": "Cautious",
            "summary": "Needs work.",
            "positives": [],
            "concerns": [],
            "diligence_questions": [],
            "conditions": [],
            "confidence": 50,
        }
    )

    assert result.recommendation == "Defer"
    assert result.risk_rating == "Medium"
    assert result.dissent == []
    assert result.mitigants == []
    assert result.known_facts == []
    assert result.scorecard is None


def test_scorecard_aggregation_identifies_lowest_and_disagreement() -> None:
    results = [
        AgentResult(
            agent_id="a",
            agent_name="A",
            stance="Supportive",
            summary="",
            positives=[],
            concerns=[],
            diligence_questions=[],
            conditions=[],
            confidence=70,
            scorecard=AgentScorecard(
                repayment_capacity=5,
                downside_resilience=2,
                documentation_quality=3,
                sponsor_support=4,
                approval_readiness=3,
            ),
        ),
        AgentResult(
            agent_id="b",
            agent_name="B",
            stance="Cautious",
            summary="",
            positives=[],
            concerns=[],
            diligence_questions=[],
            conditions=[],
            confidence=60,
            scorecard=AgentScorecard(
                repayment_capacity=2,
                downside_resilience=2,
                documentation_quality=4,
                sponsor_support=4,
                approval_readiness=2,
            ),
        ),
    ]

    aggregate = build_scorecard(results)

    assert aggregate.repayment_capacity == 3.5
    assert aggregate.lowest_dimension == "Downside resilience"
    assert "Repayment capacity" in aggregate.disagreement_dimensions


def test_committee_run_builds_ic_pack_in_mock_mode(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    deal = sample_deals()["Healthcare services platform"]
    run = run_committee(deal)

    assert len(run.agent_results) == len(AGENTS)
    assert len(run.challenge_results or []) == len(AGENTS)
    assert run.aggregate_scorecard is not None
    assert run.chair_synthesis is not None
    assert "Advisory IC Pack" in run.ic_pack_markdown
    assert "Chair advisory recommendation" in run.ic_pack_markdown
    assert "Scorecard" in run.ic_pack_markdown
    assert "Agent Debate" in run.ic_pack_markdown
    assert "Challenge Round Summary" in run.ic_pack_markdown
    assert "Diligence Grid" in run.ic_pack_markdown
    assert "Human Decision Record" in run.ic_pack_markdown
    assert run.mode == "mock"


def test_rate_limit_in_challenge_round_falls_back_to_mock(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    deal = sample_deals()["Healthcare services platform"]

    def fake_run_agent(agent, deal, prior_results):
        return mock_agent_result(agent, deal)

    def rate_limited_challenge(agent, deal, first_round):
        raise RuntimeError("rate_limit_exceeded")

    def rate_limited_chair(deal, first_round, challenge_round, aggregate_scorecard):
        raise RuntimeError("rate_limit_exceeded")

    monkeypatch.setattr(orchestrator, "run_agent", fake_run_agent)
    monkeypatch.setattr(orchestrator, "run_challenge_agent", rate_limited_challenge)
    monkeypatch.setattr(orchestrator, "run_chair_synthesis", rate_limited_chair)

    run = run_committee(deal)

    assert len(run.agent_results) == len(AGENTS)
    assert len(run.challenge_results or []) == len(AGENTS)
    assert run.chair_synthesis is not None
    assert "Challenge Round Summary" in run.ic_pack_markdown


def test_committee_run_from_legacy_shape_has_defaults() -> None:
    run = CommitteeRun(
        id="run-1",
        deal_id="deal-1",
        mode="mock",
        created_at="2026-01-01T00:00:00+00:00",
        agent_results=[],
        ic_pack_markdown="memo",
    )

    assert run.challenge_results is None
    assert run.aggregate_scorecard is None
    assert run.chair_synthesis is None


def test_sqlite_persistence_round_trip() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    deal = sample_deals()["Healthcare services platform"]
    run = run_committee(deal)

    save_deal(conn, deal)
    save_run(conn, run)

    assert list_deals(conn)[0].borrower == deal.borrower
    assert list_deals(conn)[0].sponsor_equity_m == deal.sponsor_equity_m
    saved_run = list_runs(conn, deal.id)[0]
    assert saved_run.ic_pack_markdown == run.ic_pack_markdown
    assert saved_run.agent_results[0].recommendation
    assert len(saved_run.challenge_results or []) == len(AGENTS)
    assert saved_run.aggregate_scorecard is not None
    assert saved_run.chair_synthesis is not None


def test_powerpoint_export_builds_valid_package(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    deal = sample_deals()["Healthcare services platform"]
    run = run_committee(deal)
    pptx_path = tmp_path / "memo.pptx"

    pptx_path.write_bytes(build_ic_memo_pptx(deal, run))

    with ZipFile(pptx_path) as package:
        names = set(package.namelist())
        assert "[Content_Types].xml" in names
        assert "ppt/presentation.xml" in names
        assert "ppt/slides/slide1.xml" in names
        slide_xml = package.read("ppt/slides/slide1.xml")
        assert slide_xml.startswith(b'<?xml')
        assert b"17365D" in slide_xml
        assert b"Private Credit Committee | Advisory draft" in slide_xml
