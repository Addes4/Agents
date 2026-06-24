from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class Deal:
    id: str
    borrower: str
    sponsor: str
    sector: str
    geography: str
    revenue_m: float
    ebitda_m: float
    total_debt_m: float
    purchase_price_m: float
    pricing: str
    use_of_proceeds: str
    collateral: str
    covenants: str
    liquidity: str
    thesis: str
    key_risks: str
    created_at: str
    debt_type: str = ""
    cash_interest: str = ""
    amortization: str = ""
    maturity: str = ""
    fcf_conversion: str = ""
    covenant_headroom: str = ""
    sponsor_equity_m: float = 0.0

    @property
    def leverage(self) -> float:
        if self.ebitda_m <= 0:
            return 0.0
        return self.total_debt_m / self.ebitda_m

    @property
    def enterprise_value_multiple(self) -> float:
        if self.ebitda_m <= 0:
            return 0.0
        return self.purchase_price_m / self.ebitda_m

    @property
    def sponsor_equity_percentage(self) -> float:
        if self.purchase_price_m <= 0:
            return 0.0
        return self.sponsor_equity_m / self.purchase_price_m

    def validate(self) -> list[str]:
        errors: list[str] = []
        required = {
            "borrower": self.borrower,
            "sponsor": self.sponsor,
            "sector": self.sector,
            "thesis": self.thesis,
            "key_risks": self.key_risks,
        }
        for field, value in required.items():
            if not value.strip():
                errors.append(f"{field.replace('_', ' ').title()} is required.")
        for field in [
            "revenue_m",
            "ebitda_m",
            "total_debt_m",
            "purchase_price_m",
            "sponsor_equity_m",
        ]:
            if getattr(self, field) < 0:
                errors.append(f"{field} cannot be negative.")
        if self.ebitda_m == 0:
            errors.append("EBITDA must be greater than zero for credit metrics.")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "Deal":
        defaults = {
            "debt_type": "",
            "cash_interest": "",
            "amortization": "",
            "maturity": "",
            "fcf_conversion": "",
            "covenant_headroom": "",
            "sponsor_equity_m": 0.0,
        }
        return cls(**{**defaults, **values})


@dataclass
class AgentResult:
    agent_id: str
    agent_name: str
    stance: str
    summary: str
    positives: list[str]
    concerns: list[str]
    diligence_questions: list[str]
    conditions: list[str]
    confidence: int
    recommendation: str = "Defer"
    risk_rating: str = "Medium"
    dissent: list[str] | None = None
    mitigants: list[str] | None = None
    known_facts: list[str] | None = None
    assumptions: list[str] | None = None
    missing_diligence: list[str] | None = None
    judgment: str = ""
    scorecard: "AgentScorecard | None" = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "AgentResult":
        values = dict(values)
        if values.get("scorecard") is not None and not isinstance(values["scorecard"], AgentScorecard):
            values["scorecard"] = AgentScorecard.from_dict(values["scorecard"])
        defaults = {
            "recommendation": "Defer",
            "risk_rating": "Medium",
            "dissent": [],
            "mitigants": [],
            "known_facts": [],
            "assumptions": [],
            "missing_diligence": [],
            "judgment": "",
            "scorecard": None,
        }
        return cls(**{**defaults, **values})


@dataclass
class AgentScorecard:
    repayment_capacity: int = 3
    downside_resilience: int = 3
    documentation_quality: int = 3
    sponsor_support: int = 3
    approval_readiness: int = 3

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: dict[str, Any] | None) -> "AgentScorecard":
        values = values or {}
        return cls(
            repayment_capacity=_score(values.get("repayment_capacity")),
            downside_resilience=_score(values.get("downside_resilience")),
            documentation_quality=_score(values.get("documentation_quality")),
            sponsor_support=_score(values.get("sponsor_support")),
            approval_readiness=_score(values.get("approval_readiness")),
        )


@dataclass
class AggregateScorecard:
    repayment_capacity: float = 0.0
    downside_resilience: float = 0.0
    documentation_quality: float = 0.0
    sponsor_support: float = 0.0
    approval_readiness: float = 0.0
    lowest_dimension: str = ""
    lowest_score: float = 0.0
    disagreement_dimensions: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: dict[str, Any] | None) -> "AggregateScorecard":
        values = values or {}
        return cls(
            repayment_capacity=float(values.get("repayment_capacity", 0.0)),
            downside_resilience=float(values.get("downside_resilience", 0.0)),
            documentation_quality=float(values.get("documentation_quality", 0.0)),
            sponsor_support=float(values.get("sponsor_support", 0.0)),
            approval_readiness=float(values.get("approval_readiness", 0.0)),
            lowest_dimension=str(values.get("lowest_dimension", "")),
            lowest_score=float(values.get("lowest_score", 0.0)),
            disagreement_dimensions=list(values.get("disagreement_dimensions") or []),
        )


@dataclass
class AgentChallengeResult:
    agent_id: str
    agent_name: str
    changed_recommendation: bool
    revised_recommendation: str
    agreement_points: list[str]
    challenge_points: list[str]
    unresolved_issues: list[str]
    what_would_change_view: list[str]
    confidence: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "AgentChallengeResult":
        defaults = {
            "changed_recommendation": False,
            "revised_recommendation": "Defer",
            "agreement_points": [],
            "challenge_points": [],
            "unresolved_issues": [],
            "what_would_change_view": [],
            "confidence": 60,
        }
        return cls(**{**defaults, **values})


@dataclass
class ChairSynthesis:
    final_advisory_recommendation: str = "Defer"
    committee_rationale: str = ""
    majority_view: list[str] | None = None
    dissenting_view: list[str] | None = None
    gating_diligence: list[str] | None = None
    approval_conditions: list[str] | None = None
    scorecard_interpretation: str = ""
    what_would_change_recommendation: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: dict[str, Any] | None) -> "ChairSynthesis":
        values = values or {}
        defaults = {
            "final_advisory_recommendation": "Defer",
            "committee_rationale": "",
            "majority_view": [],
            "dissenting_view": [],
            "gating_diligence": [],
            "approval_conditions": [],
            "scorecard_interpretation": "",
            "what_would_change_recommendation": [],
        }
        return cls(**{**defaults, **values})


@dataclass
class CommitteeRun:
    id: str
    deal_id: str
    mode: str
    created_at: str
    agent_results: list[AgentResult]
    ic_pack_markdown: str
    challenge_results: list[AgentChallengeResult] | None = None
    aggregate_scorecard: AggregateScorecard | None = None
    chair_synthesis: ChairSynthesis | None = None

    @classmethod
    def new_id(cls) -> str:
        return str(uuid4())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _score(value: Any) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return 3
    return max(1, min(5, score))


def new_deal_id() -> str:
    return str(uuid4())
