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
from credit_committee.pptx_export import build_ic_memo_pptx
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
        deal_options = {
            f"{deal.borrower} ({deal.created_at})": deal
            for deal in existing_deals
        }
        selected_existing = st.selectbox(
            "Saved deals",
            ["New deal"] + list(deal_options),
        )

    selected_deal = deal_options.get(selected_existing)

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
                        f"- First round done: **{result.agent_name}** - {result.stance}; {result.summary}"
                    )
                    progress.progress(
                        len(completed_views) / (len(AGENTS) * 2 + 1),
                        text=f"Completed {len(completed_views)} of {len(AGENTS)} first-round agents",
                    )
                    render_live_log()

                try:
                    with st.spinner("Running agent committee..."):
                        run = run_committee(
                            deal,
                            on_agent_start=on_agent_start,
                            on_agent_done=on_agent_done,
                        )
                        save_run(conn, run)
                    progress.progress(1.0, text="First round, challenge round, and chair synthesis completed")
                    st.success("Committee run completed.")
                except Exception as exc:
                    st.error(
                        "Committee run failed. Check your OpenAI configuration or unset "
                        "OPENAI_API_KEY to use deterministic mock mode."
                    )
                    st.caption(str(exc))

    runs = list_runs(conn, deal.id)
    if runs:
        st.divider()
        run = runs[0]
        st.subheader("Latest Committee Output")
        tabs = st.tabs(
            [
                "IC Memo",
                "Scorecard",
                "First Views",
                "Challenge Round",
                "Chair Synthesis",
                "Human Decision",
            ]
        )
        with tabs[0]:
            download_cols = st.columns(2)
            download_cols[0].download_button(
                "Download Markdown",
                data=run.ic_pack_markdown,
                file_name=f"{deal.borrower.lower().replace(' ', '-')}-ic-memo.md",
                mime="text/markdown",
            )
            download_cols[1].download_button(
                "Download PowerPoint",
                data=build_ic_memo_pptx(deal, run),
                file_name=f"{deal.borrower.lower().replace(' ', '-')}-ic-memo.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
            st.markdown(run.ic_pack_markdown)
        with tabs[1]:
            _render_scorecard(run)
        with tabs[2]:
            for result in run.agent_results:
                with st.expander(f"{result.agent_name}: {result.stance}", expanded=False):
                    st.write(result.summary)
                    st.write("**Judgment**")
                    st.write(result.judgment or "Not provided.")
                    st.write("**Known facts**")
                    st.markdown(_bullets(result.known_facts or []))
                    st.write("**Assumptions**")
                    st.markdown(_bullets(result.assumptions or []))
                    st.write("**Concerns**")
                    st.markdown(_bullets(result.concerns))
                    st.write("**Mitigants**")
                    st.markdown(_bullets(result.mitigants or []))
                    st.write("**Missing diligence**")
                    st.markdown(_bullets(result.missing_diligence or []))
                    st.write("**Diligence questions**")
                    st.markdown(_bullets(result.diligence_questions))
                    st.write("**Conditions**")
                    st.markdown(_bullets(result.conditions))
        with tabs[3]:
            for result in run.challenge_results or []:
                with st.expander(f"{result.agent_name}: {result.revised_recommendation}", expanded=False):
                    st.write(f"Changed recommendation: {'Yes' if result.changed_recommendation else 'No'}")
                    st.write("**Agreement points**")
                    st.markdown(_bullets(result.agreement_points))
                    st.write("**Challenge points**")
                    st.markdown(_bullets(result.challenge_points))
                    st.write("**Unresolved issues**")
                    st.markdown(_bullets(result.unresolved_issues))
                    st.write("**What would change the view**")
                    st.markdown(_bullets(result.what_would_change_view))
            if not run.challenge_results:
                st.info("No challenge round was saved for this run.")
        with tabs[4]:
            _render_chair_synthesis(run)
        with tabs[5]:
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
    widget_prefix = f"{base.id}:{sample_choice}"

    st.subheader("Deal Intake")
    c1, c2, c3 = st.columns(3)
    borrower = c1.text_input("Borrower", value=base.borrower, key=f"{widget_prefix}:borrower")
    sponsor = c2.text_input("Sponsor", value=base.sponsor, key=f"{widget_prefix}:sponsor")
    sector = c3.text_input("Sector", value=base.sector, key=f"{widget_prefix}:sector")
    geography = c1.text_input("Geography", value=base.geography, key=f"{widget_prefix}:geography")
    revenue_m = c2.number_input(
        "Revenue (m)",
        min_value=0.0,
        value=float(base.revenue_m),
        step=1.0,
        key=f"{widget_prefix}:revenue_m",
    )
    ebitda_m = c3.number_input(
        "EBITDA (m)",
        min_value=0.0,
        value=float(base.ebitda_m),
        step=1.0,
        key=f"{widget_prefix}:ebitda_m",
    )
    total_debt_m = c1.number_input(
        "Total debt (m)",
        min_value=0.0,
        value=float(base.total_debt_m),
        step=1.0,
        key=f"{widget_prefix}:total_debt_m",
    )
    purchase_price_m = c2.number_input(
        "Purchase price / EV (m)",
        min_value=0.0,
        value=float(base.purchase_price_m),
        step=1.0,
        key=f"{widget_prefix}:purchase_price_m",
    )
    sponsor_equity_m = c3.number_input(
        "Sponsor equity (m)",
        min_value=0.0,
        value=float(base.sponsor_equity_m),
        step=1.0,
        key=f"{widget_prefix}:sponsor_equity_m",
    )

    st.subheader("Core Credit Terms")
    t1, t2, t3 = st.columns(3)
    debt_type = t1.text_input("Debt type", value=base.debt_type, key=f"{widget_prefix}:debt_type")
    cash_interest = t2.text_input(
        "Cash interest",
        value=base.cash_interest,
        key=f"{widget_prefix}:cash_interest",
    )
    amortization = t3.text_input(
        "Amortization",
        value=base.amortization,
        key=f"{widget_prefix}:amortization",
    )
    maturity = t1.text_input("Maturity", value=base.maturity, key=f"{widget_prefix}:maturity")
    fcf_conversion = t2.text_input(
        "FCF conversion",
        value=base.fcf_conversion,
        key=f"{widget_prefix}:fcf_conversion",
    )
    covenant_headroom = t3.text_input(
        "Covenant headroom",
        value=base.covenant_headroom,
        key=f"{widget_prefix}:covenant_headroom",
    )

    pricing = st.text_input("Pricing", value=base.pricing, key=f"{widget_prefix}:pricing")
    use_of_proceeds = st.text_area(
        "Use of proceeds",
        value=base.use_of_proceeds,
        height=70,
        key=f"{widget_prefix}:use_of_proceeds",
    )
    collateral = st.text_area(
        "Collateral / security",
        value=base.collateral,
        height=70,
        key=f"{widget_prefix}:collateral",
    )
    covenants = st.text_area(
        "Covenants",
        value=base.covenants,
        height=70,
        key=f"{widget_prefix}:covenants",
    )
    liquidity = st.text_area(
        "Liquidity",
        value=base.liquidity,
        height=70,
        key=f"{widget_prefix}:liquidity",
    )
    thesis = st.text_area(
        "Investment thesis",
        value=base.thesis,
        height=100,
        key=f"{widget_prefix}:thesis",
    )
    key_risks = st.text_area(
        "Key risks",
        value=base.key_risks,
        height=100,
        key=f"{widget_prefix}:key_risks",
    )

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
        debt_type=debt_type,
        cash_interest=cash_interest,
        amortization=amortization,
        maturity=maturity,
        fcf_conversion=fcf_conversion,
        covenant_headroom=covenant_headroom,
        sponsor_equity_m=float(sponsor_equity_m),
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
        debt_type="",
        cash_interest="",
        amortization="",
        maturity="",
        fcf_conversion="",
        covenant_headroom="",
        sponsor_equity_m=0.0,
    )


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) or "- None identified."


def _render_scorecard(run) -> None:
    scorecard = run.aggregate_scorecard
    if scorecard is None:
        st.info("No scorecard was saved for this run.")
        return
    cols = st.columns(5)
    cols[0].metric("Repayment", f"{scorecard.repayment_capacity:.1f}/5")
    cols[1].metric("Downside", f"{scorecard.downside_resilience:.1f}/5")
    cols[2].metric("Docs", f"{scorecard.documentation_quality:.1f}/5")
    cols[3].metric("Sponsor", f"{scorecard.sponsor_support:.1f}/5")
    cols[4].metric("Readiness", f"{scorecard.approval_readiness:.1f}/5")
    st.write(f"**Lowest dimension:** {scorecard.lowest_dimension or 'None'} ({scorecard.lowest_score:.1f}/5)")
    st.write("**Disagreement dimensions**")
    st.markdown(_bullets(scorecard.disagreement_dimensions or []))


def _render_chair_synthesis(run) -> None:
    chair = run.chair_synthesis
    if chair is None:
        st.info("No chair synthesis was saved for this run.")
        return
    st.metric("Final advisory recommendation", chair.final_advisory_recommendation)
    st.write(chair.committee_rationale or "No rationale provided.")
    st.write("**Majority view**")
    st.markdown(_bullets(chair.majority_view or []))
    st.write("**Dissenting view**")
    st.markdown(_bullets(chair.dissenting_view or []))
    st.write("**Gating diligence**")
    st.markdown(_bullets(chair.gating_diligence or []))
    st.write("**Approval conditions**")
    st.markdown(_bullets(chair.approval_conditions or []))
    st.write("**What would change the recommendation**")
    st.markdown(_bullets(chair.what_would_change_recommendation or []))


if __name__ == "__main__":
    main()
