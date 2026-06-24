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
        for field in ["revenue_m", "ebitda_m", "total_debt_m", "purchase_price_m"]:
            if getattr(self, field) < 0:
                errors.append(f"{field} cannot be negative.")
        if self.ebitda_m == 0:
            errors.append("EBITDA must be greater than zero for credit metrics.")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "Deal":
        return cls(**values)


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "AgentResult":
        return cls(**values)


@dataclass
class CommitteeRun:
    id: str
    deal_id: str
    mode: str
    created_at: str
    agent_results: list[AgentResult]
    ic_pack_markdown: str

    @classmethod
    def new_id(cls) -> str:
        return str(uuid4())


def new_deal_id() -> str:
    return str(uuid4())
