from __future__ import annotations

from credit_committee.models import Deal, new_deal_id, utc_now_iso


def sample_deals() -> dict[str, Deal]:
    return {
        "Healthcare services platform": Deal(
            id=new_deal_id(),
            borrower="Northstar Care Partners",
            sponsor="Arden Ridge Capital",
            sector="Healthcare services",
            geography="United States",
            revenue_m=220.0,
            ebitda_m=34.0,
            total_debt_m=168.0,
            purchase_price_m=340.0,
            pricing="SOFR + 625 bps, 1.0% floor, 2.0% OID",
            use_of_proceeds="Sponsor buyout and refinancing of existing debt",
            collateral="First-lien security over substantially all assets and equity pledges",
            covenants="Maintenance leverage covenant with 30% EBITDA cushion and monthly reporting",
            liquidity="18m revolver availability with minimum liquidity covenant",
            thesis="Recurring demand, fragmented local markets, and sponsor playbook for add-on acquisitions.",
            key_risks="Labor availability, reimbursement pressure, acquisition integration, and regional concentration.",
            created_at=utc_now_iso(),
        ),
        "Industrial software carve-out": Deal(
            id=new_deal_id(),
            borrower="VectorWorks Automation",
            sponsor="Kestrel Partners",
            sector="Industrial software",
            geography="Europe",
            revenue_m=96.0,
            ebitda_m=18.0,
            total_debt_m=112.0,
            purchase_price_m=252.0,
            pricing="EURIBOR + 700 bps, 3.0% OID",
            use_of_proceeds="Corporate carve-out, transition services, and growth investment",
            collateral="Share pledges, IP pledge where available, receivables, and bank accounts",
            covenants="Incurrence-style covenant package with springing liquidity test",
            liquidity="Limited opening cash; relies on revolver availability and transition services continuity",
            thesis="Sticky installed base and mission-critical software embedded in plant workflows.",
            key_risks="Carve-out execution, customer churn, limited standalone financial history, and high leverage.",
            created_at=utc_now_iso(),
        ),
    }
