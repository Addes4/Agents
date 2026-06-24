from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from credit_committee.models import AgentResult, CommitteeRun, Deal


DB_PATH = Path("credit_committee.sqlite3")


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS deals (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            payload TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS committee_runs (
            id TEXT PRIMARY KEY,
            deal_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            created_at TEXT NOT NULL,
            agent_results TEXT NOT NULL,
            ic_pack_markdown TEXT NOT NULL,
            human_decision TEXT DEFAULT '',
            FOREIGN KEY (deal_id) REFERENCES deals(id)
        )
        """
    )
    conn.commit()


def save_deal(conn: sqlite3.Connection, deal: Deal) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO deals (id, created_at, payload) VALUES (?, ?, ?)",
        (deal.id, deal.created_at, json.dumps(deal.to_dict())),
    )
    conn.commit()


def list_deals(conn: sqlite3.Connection) -> list[Deal]:
    rows = conn.execute("SELECT payload FROM deals ORDER BY created_at DESC").fetchall()
    return [Deal.from_dict(json.loads(row["payload"])) for row in rows]


def get_deal(conn: sqlite3.Connection, deal_id: str) -> Deal | None:
    row = conn.execute("SELECT payload FROM deals WHERE id = ?", (deal_id,)).fetchone()
    if row is None:
        return None
    return Deal.from_dict(json.loads(row["payload"]))


def save_run(conn: sqlite3.Connection, run: CommitteeRun) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO committee_runs
        (id, deal_id, mode, created_at, agent_results, ic_pack_markdown)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            run.id,
            run.deal_id,
            run.mode,
            run.created_at,
            json.dumps([result.to_dict() for result in run.agent_results]),
            run.ic_pack_markdown,
        ),
    )
    conn.commit()


def list_runs(conn: sqlite3.Connection, deal_id: str | None = None) -> list[CommitteeRun]:
    if deal_id:
        rows = conn.execute(
            "SELECT * FROM committee_runs WHERE deal_id = ? ORDER BY created_at DESC",
            (deal_id,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM committee_runs ORDER BY created_at DESC").fetchall()
    return [_row_to_run(row) for row in rows]


def update_human_decision(conn: sqlite3.Connection, run_id: str, decision: str) -> None:
    conn.execute(
        "UPDATE committee_runs SET human_decision = ? WHERE id = ?",
        (decision, run_id),
    )
    conn.commit()


def get_human_decision(conn: sqlite3.Connection, run_id: str) -> str:
    row = conn.execute(
        "SELECT human_decision FROM committee_runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    return "" if row is None else str(row["human_decision"] or "")


def _row_to_run(row: sqlite3.Row) -> CommitteeRun:
    return CommitteeRun(
        id=row["id"],
        deal_id=row["deal_id"],
        mode=row["mode"],
        created_at=row["created_at"],
        agent_results=[
            AgentResult.from_dict(value)
            for value in json.loads(row["agent_results"])
        ],
        ic_pack_markdown=row["ic_pack_markdown"],
    )
