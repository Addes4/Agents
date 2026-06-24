from __future__ import annotations

from dataclasses import replace

import streamlit as st

from credit_committee.agents import AGENTS
from credit_committee.db import (
    connect,
    get_human_decision,
    list_deals,
    list_runs,
    save_deal,
    save_run,
    update_human_decision,
)
from credit_committee.llm import provider_mode
from credit_committee.models import Deal, new_deal_id, utc_now_iso
from credit_committee.orchestrator import run_committee
from credit_committee.samples import sample_deals


st.set_page_config(page_title="Credit Committee", layout="wide")


def main() -> None:
    conn = connect()
    st.title("Private Credit Committee")
    st.warning(
        "Synthetic/demo workflow only. Do not enter confidential borrower, sponsor, fund, or portfolio data."
    )

    with st.sidebar:
        st.subheader("Mode")
        st.write(f"Agent provider: `{provider_mode()}`")
        st.caption("Set OPENAI_API_KEY to use live LLM responses. Otherwise mock mode is used.")
        existing_deals = list_deals(conn)
        selected_existing = st.selectbox(
            "Saved deals",
            ["New deal"] + [f"{deal.borrower} ({deal.created_at})" for deal in existing_deals],
        )

    selected_deal = None
    if selected_existing != "New deal":
        selected_deal = existing_deals[[
            f"{deal.borrower} ({deal.created_at})" for deal in existing_deals
        ].index(selected_existing)]

    deal = deal_form(selected_deal)
    if st.button("Save Deal", type="secondary"):
        errors = deal.validate()
        if errors:
            for error in errors:
                st.error(error)
        else:
            save_deal(conn, deal)
            st.success("Deal saved.")

    st.divider()
    left, right = st.columns([1, 1])
    with left:
        st.subheader("Credit Snapshot")
        metric_cols = st.columns(4)
        metric_cols[0].metric("Revenue", f"{deal.revenue_m:.1f}m")
        metric_cols[1].metric("EBITDA", f"{deal.ebitda_m:.1f}m")
        metric_cols[2].metric("Leverage", f"{deal.leverage:.2f}x")
        metric_cols[3].metric("EV / EBITDA", f"{deal.enterprise_value_multiple:.2f}x")
        st.write("**Thesis**")
        st.write(deal.thesis or "Not provided.")
        st.write("**Key risks**")
        st.write(deal.key_risks or "Not provided.")

    with right:
        st.subheader("Run Committee")
        st.caption("The committee is advisory only; humans make and record final decisions.")
        if st.button("Run Advisory Committee", type="primary"):
            errors = deal.validate()
            if errors:
                for error in errors:
                    st.error(error)
            else:
                save_deal(conn, deal)
                progress = st.progress(0, text="Preparing committee...")
                live_log = st.empty()
                completed_views: list[str] = []

                def render_live_log(active_agent: str | None = None) -> None:
                    lines = []
                    if active_agent:
                        lines.append(f"- Running: **{active_agent}**")
                    lines.extend(completed_views)
                    live_log.markdown("\n".join(lines) or "- Waiting to start...")

                def on_agent_start(agent_name: str) -> None:
                    render_live_log(agent_name)

                def on_agent_done(result) -> None:
                    completed_views.append(
                        f"- Done: **{result.agent_name}** - {result.stance}; {result.summary}"
                    )
                    progress.progress(
                        len(completed_views) / len(AGENTS),
                        text=f"Completed {len(completed_views)} of {len(AGENTS)} agents",
                    )
                    render_live_log()

                with st.spinner("Running agent committee..."):
                    run = run_committee(
                        deal,
                        on_agent_start=on_agent_start,
                        on_agent_done=on_agent_done,
                    )
                    save_run(conn, run)
                progress.progress(1.0, text="Committee run completed")
                st.success("Committee run completed.")

    runs = list_runs(conn, deal.id)
    if runs:
        st.divider()
        run = runs[0]
        st.subheader("Latest Committee Output")
        tabs = st.tabs(["Agent Views", "IC Pack", "Human Decision"])
        with tabs[0]:
            for result in run.agent_results:
                with st.expander(f"{result.agent_name}: {result.stance}", expanded=False):
                    st.write(result.summary)
                    st.write("**Concerns**")
                    st.markdown(_bullets(result.concerns))
                    st.write("**Diligence questions**")
                    st.markdown(_bullets(result.diligence_questions))
                    st.write("**Conditions**")
                    st.markdown(_bullets(result.conditions))
        with tabs[1]:
            st.download_button(
                "Download IC Pack",
                data=run.ic_pack_markdown,
                file_name=f"{deal.borrower.lower().replace(' ', '-')}-ic-pack.md",
                mime="text/markdown",
            )
            st.markdown(run.ic_pack_markdown)
        with tabs[2]:
            current_decision = get_human_decision(conn, run.id)
            decision = st.text_area(
                "Human final decision notes",
                value=current_decision,
                height=180,
                placeholder="Record final decision, approvers, date, conditions accepted or waived, and rationale.",
            )
            if st.button("Save Human Decision"):
                update_human_decision(conn, run.id, decision)
                st.success("Human decision notes saved.")


def deal_form(existing: Deal | None) -> Deal:
    if "draft_deal_id" not in st.session_state:
        st.session_state["draft_deal_id"] = new_deal_id()
    if "draft_created_at" not in st.session_state:
        st.session_state["draft_created_at"] = utc_now_iso()

    samples = sample_deals()
    sample_choice = st.selectbox("Load synthetic sample", ["Blank"] + list(samples.keys()))
    base = existing or blank_deal()
    if sample_choice != "Blank":
        base = replace(
            samples[sample_choice],
            id=existing.id if existing else st.session_state["draft_deal_id"],
            created_at=existing.created_at if existing else st.session_state["draft_created_at"],
        )

    st.subheader("Deal Intake")
    c1, c2, c3 = st.columns(3)
    borrower = c1.text_input("Borrower", value=base.borrower)
    sponsor = c2.text_input("Sponsor", value=base.sponsor)
    sector = c3.text_input("Sector", value=base.sector)
    geography = c1.text_input("Geography", value=base.geography)
    revenue_m = c2.number_input("Revenue (m)", min_value=0.0, value=float(base.revenue_m), step=1.0)
    ebitda_m = c3.number_input("EBITDA (m)", min_value=0.0, value=float(base.ebitda_m), step=1.0)
    total_debt_m = c1.number_input("Total debt (m)", min_value=0.0, value=float(base.total_debt_m), step=1.0)
    purchase_price_m = c2.number_input("Purchase price / EV (m)", min_value=0.0, value=float(base.purchase_price_m), step=1.0)
    pricing = c3.text_input("Pricing", value=base.pricing)
    use_of_proceeds = st.text_area("Use of proceeds", value=base.use_of_proceeds, height=70)
    collateral = st.text_area("Collateral / security", value=base.collateral, height=70)
    covenants = st.text_area("Covenants", value=base.covenants, height=70)
    liquidity = st.text_area("Liquidity", value=base.liquidity, height=70)
    thesis = st.text_area("Investment thesis", value=base.thesis, height=100)
    key_risks = st.text_area("Key risks", value=base.key_risks, height=100)

    return Deal(
        id=base.id,
        borrower=borrower,
        sponsor=sponsor,
        sector=sector,
        geography=geography,
        revenue_m=float(revenue_m),
        ebitda_m=float(ebitda_m),
        total_debt_m=float(total_debt_m),
        purchase_price_m=float(purchase_price_m),
        pricing=pricing,
        use_of_proceeds=use_of_proceeds,
        collateral=collateral,
        covenants=covenants,
        liquidity=liquidity,
        thesis=thesis,
        key_risks=key_risks,
        created_at=base.created_at,
    )


def blank_deal() -> Deal:
    return Deal(
        id=st.session_state["draft_deal_id"],
        borrower="",
        sponsor="",
        sector="",
        geography="",
        revenue_m=0.0,
        ebitda_m=0.0,
        total_debt_m=0.0,
        purchase_price_m=0.0,
        pricing="",
        use_of_proceeds="",
        collateral="",
        covenants="",
        liquidity="",
        thesis="",
        key_risks="",
        created_at=st.session_state["draft_created_at"],
    )


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) or "- None identified."


if __name__ == "__main__":
    main()
