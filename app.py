"""Fiducia's Streamlit decision cockpit."""

from __future__ import annotations

import html
import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

try:
    import plotly.express as px
    _PLOTLY_AVAILABLE = True
except ImportError:
    _PLOTLY_AVAILABLE = False

from fiducia.audit import AuditLogger
from fiducia.models import AGENT_LABELS, AGENT_ORDER
from fiducia.policy import expense_benchmark, expense_cap, load_policy
from fiducia.tools import MOCK_PATH, load_funds
from fiducia.workflow import apply_human_decision, run_workflow, stream_workflow


ROOT = Path(__file__).resolve().parent

st.set_page_config(
    page_title="Fiducia | Governed Fund Approval",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');
:root { --ink:#071321; --panel:#0d2033; --line:#254157; --teal:#19c6b3; --gold:#f4b942; --muted:#91a7b8; --red:#ff6b6b; --green:#57d49b; }
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
h1,h2,h3 { font-family:'Manrope',sans-serif !important; letter-spacing:-0.025em; }
.stApp { background: radial-gradient(circle at 75% -10%, #123a50 0, #071321 37%); }
[data-testid="stSidebar"] { background:#091927; border-right:1px solid #1b3448; }
[data-testid="stMetric"] { background:linear-gradient(145deg,#0e2437,#0a1a2a); border:1px solid #1e3c50; padding:14px 16px; border-radius:14px; }
[data-testid="stMetricLabel"] { color:#91a7b8; }
.block-container { padding-top:2rem; padding-bottom:3rem; max-width:1480px; }
.brand-kicker { color:var(--teal); font-size:.74rem; font-weight:800; letter-spacing:.18em; text-transform:uppercase; }
.hero { display:flex; align-items:flex-end; justify-content:space-between; gap:24px; margin-bottom:12px; }
.hero h1 { margin:.2rem 0 .15rem; font-size:2.65rem; line-height:1; }
.hero p { color:#a8bac8; margin:0; max-width:760px; font-size:1rem; }
.demo-pill { border:1px solid #31526a; background:#0c2030; border-radius:999px; padding:8px 13px; color:#b8c8d4; white-space:nowrap; font-size:.78rem; }
.panel { border:1px solid #203b50; background:linear-gradient(145deg,rgba(15,36,54,.96),rgba(8,25,39,.96)); border-radius:18px; padding:18px; box-shadow:0 16px 42px rgba(0,0,0,.18); }
.decision-card { border:1px solid #28516a; background:linear-gradient(140deg,#102d41,#0a1b2b); border-radius:18px; padding:22px; min-height:210px; }
.decision-card.approve { border-color:#2d8c74; box-shadow:inset 4px 0 #57d49b; }
.decision-card.conditions { border-color:#7e6a31; box-shadow:inset 4px 0 #f4b942; }
.decision-card.escalate { border-color:#7e6a31; box-shadow:inset 4px 0 #f4b942; }
.decision-card.reject { border-color:#804047; box-shadow:inset 4px 0 #ff6b6b; }
.decision-label { font-family:'Manrope'; font-size:1.75rem; font-weight:800; margin:.25rem 0 .7rem; }
.eyebrow { color:#91a7b8; font-size:.72rem; letter-spacing:.13em; text-transform:uppercase; font-weight:700; }
.summary { color:#d3dce4; line-height:1.55; }
.agent-flow { display:flex; align-items:stretch; width:100%; gap:8px; margin:10px 0 14px; overflow-x:auto; padding:4px 1px 8px; }
.agent-node { min-width:150px; flex:1; border:1px solid #29465b; background:#0c1d2d; border-radius:14px; padding:13px; position:relative; transition:.2s; }
.agent-node.active { border-color:#19c6b3; box-shadow:0 0 0 2px rgba(25,198,179,.13),0 0 25px rgba(25,198,179,.10); }
.agent-node.complete { border-color:#2d6e62; background:#0d282e; }
.agent-node.failed { border-color:#74414a; background:#291b26; }
.agent-node.pending { opacity:.62; }
.agent-num { width:25px;height:25px;border-radius:8px;display:inline-flex;align-items:center;justify-content:center;background:#193247;color:#bcd0df;font-weight:800;font-size:.72rem;margin-bottom:9px; }
.active .agent-num { background:#19c6b3;color:#071321; }
.complete .agent-num { background:#57d49b;color:#071321; }
.agent-name { font-weight:700;font-size:.84rem;line-height:1.2;min-height:34px; }
.agent-state { color:#91a7b8;font-size:.69rem;margin-top:7px;text-transform:uppercase;letter-spacing:.08em; }
.connector { color:#486579; display:flex; align-items:center; font-size:1.1rem; }
.correction { border:1px solid #765f2e; background:#2a2517; color:#f3d88a; border-radius:10px; padding:8px 12px; font-size:.8rem; margin-top:-4px; }
.alert { border-radius:12px;padding:12px 14px;margin:10px 0;font-size:.88rem;line-height:1.45; }
.alert.gold { background:#2b2515;border:1px solid #6b592b;color:#f5dc94; }
.alert.red { background:#2a171d;border:1px solid #753c45;color:#ffb8bd; }
.alert.teal { background:#102c2d;border:1px solid #286c65;color:#a4ece2; }
.mini-tag { display:inline-block;border:1px solid #35556b;border-radius:999px;padding:3px 8px;margin:2px;color:#b7c9d5;font-size:.68rem; }
.footer-note { color:#7890a2;font-size:.72rem;text-align:center;margin-top:30px; }
div[data-testid="stForm"] { border:1px solid #203b50; border-radius:16px; padding:18px; background:rgba(9,27,42,.7); }
.stButton>button, .stFormSubmitButton>button { border-radius:10px; font-weight:700; }
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_data
def fund_catalog(catalog_version: int) -> list[dict[str, Any]]:
    """Load the catalog, invalidating Streamlit cache when the CSV changes."""

    del catalog_version
    return load_funds()


SCENARIO_LABELS = {
    "SUNX": "Clean case · auto-approval",
    "DATA": "Missing Sharpe → repair 1/2 → green approval",
    "ALPHX": "Fee exception · escalation",
    "SPECX": "Hard stops · reject recommendation",
    "CONFX": "Source conflict · human review",
    "INJX": "Prompt injection · containment",
    "BLANK": "Missing fee · fail closed",
    "AZQ": "Low-cost ETF · peer warning",
    "RET2045": "Target-date fund · suitability",
    "NEWB": "Short history · governance exception",
}


def as_optional_float(value: str) -> float | None:
    stripped = value.strip()
    if not stripped:
        return None
    return float(stripped)


def safe(value: Any) -> str:
    return html.escape(str(value))


def render_agent_graph(state: dict[str, Any] | None) -> str:
    completed = set((state or {}).get("completed_agents", []))
    active = (state or {}).get("active_agent", "")
    results = (state or {}).get("agent_results", {})
    nodes: list[str] = []
    for index, key in enumerate(AGENT_ORDER, 1):
        outcome = results.get(key, {}).get("outcome")
        if key == active:
            css, label = "active", "Active"
        elif key in completed:
            css = "failed" if outcome in {"FAIL", "REJECT"} else "complete"
            label = str(outcome or "Complete").replace("_", " ")
        else:
            css, label = "pending", "Pending"
        nodes.append(
            f'<div class="agent-node {css}"><div class="agent-num">{index:02d}</div>'
            f'<div class="agent-name">{safe(AGENT_LABELS[key])}</div>'
            f'<div class="agent-state">{safe(label)}</div></div>'
        )
        if index < len(AGENT_ORDER):
            nodes.append('<div class="connector">›</div>')
    retry = ""
    if state and state.get("retries"):
        repaired = sum(len(item.get("repaired_fields", [])) for item in state.get("enrichment_history", []))
        identity_mismatches = sorted(
            {
                field
                for item in state.get("enrichment_history", [])
                for field in item.get("identity_mismatches", [])
            }
        )
        identity_guard = (
            " Identity guard blocked enrichment on: "
            + ", ".join(identity_mismatches)
            + ". Restore scenario defaults or review it as a custom case."
            if identity_mismatches
            else ""
        )
        retry = (
            f'<div class="correction">↻ Self-correction loop executed {state["retries"]} time(s); '
            f'{repaired} field(s) restored from an approved synthetic source.'
            f'{safe(identity_guard)}</div>'
        )
    return '<div class="agent-flow">' + "".join(nodes) + "</div>" + retry


def decision_css(recommendation: str) -> str:
    return {
        "APPROVE": "approve",
        "APPROVE_WITH_CONDITIONS": "conditions",
        "ESCALATE": "escalate",
        "REJECT": "reject",
    }.get(recommendation, "")


@st.dialog("Governed human checkpoint", width="large")
def human_review_dialog() -> None:
    state = st.session_state.get("workflow")
    if not state:
        st.warning("Run a case before recording a human decision.")
        return
    st.caption(f"Trace {state['trace_id']} · Agent recommendation: {state['recommendation']}")
    with st.form("human_review_form"):
        reviewer = st.text_input("Reviewer ID", placeholder="e.g., sponsor.jlee")
        action_label = st.selectbox(
            "Decision",
            ["Approve", "Reject", "Return for review"],
        )
        reason = st.text_area(
            "Required rationale",
            placeholder="Cite the evidence and policy basis for this decision or override.",
        )
        second_approver = st.text_input(
            "Second approver ID",
            help="Mandatory when overriding a REJECT recommendation to APPROVE.",
        )
        attested = st.checkbox(
            "I attest that I reviewed the displayed evidence and accept accountability for this action."
        )
        submitted = st.form_submit_button("Attest & record decision", type="primary", width="stretch")
    if submitted:
        if not attested:
            st.error("Attestation is required.")
            return
        action = action_label.upper().replace(" ", "_")
        try:
            st.session_state.workflow = apply_human_decision(
                state,
                reviewer=reviewer,
                action=action,
                reason=reason,
                second_approver=second_approver,
                attested=attested,
            )
        except ValueError as exc:
            st.error(str(exc))
            return
        st.success("Attested decision appended to the tamper-evident audit chain.")
        time.sleep(0.5)
        st.rerun()


funds = fund_catalog(MOCK_PATH.stat().st_mtime_ns)
fund_by_ticker = {str(fund["ticker"]): fund for fund in funds}

with st.sidebar:
    st.markdown('<div class="brand-kicker">Fiducia Control Plane</div>', unsafe_allow_html=True)
    st.markdown("### Demo controls")
    selected_ticker = st.selectbox(
        "Scenario",
        list(fund_by_ticker),
        format_func=lambda ticker: f"{ticker} · {SCENARIO_LABELS.get(ticker, 'Custom scenario')}",
    )
    lock_seeded_identity = st.checkbox(
        "Lock seeded identity",
        value=True,
        help=(
            "Recommended for the live demo. It prevents ticker, fund name, product, "
            "or asset-class edits from invalidating the approved enrichment join."
        ),
    )
    reset_scenario = st.button("Restore scenario defaults", width="stretch")
    model_mode = st.radio(
        "Narrative engine",
        ["offline", "bedrock"],
        format_func=lambda value: "Deterministic / offline" if value == "offline" else "Amazon Bedrock Converse",
        help="Only explanations use the model. Policy outcomes are deterministic in both modes.",
    )
    plan_risk = st.slider("Plan risk ceiling", 1, 10, 7)
    st.markdown("---")
    st.markdown("**Policy boundary**")
    st.caption("AI extracts and explains. Versioned code decides. A named human owns every exception.")
    st.markdown(
        '<span class="mini-tag">Synthetic data</span><span class="mini-tag">No advice</span><span class="mini-tag">Fail closed</span>',
        unsafe_allow_html=True,
    )

scenario_changed = st.session_state.get("loaded_ticker") != selected_ticker
if scenario_changed or reset_scenario:
    st.session_state.loaded_ticker = selected_ticker
    st.session_state.draft = dict(fund_by_ticker[selected_ticker])
    st.session_state.form_epoch = int(st.session_state.get("form_epoch", 0)) + 1
    st.session_state.pop("workflow", None)
    if reset_scenario:
        st.rerun()

form_token = f"{selected_ticker}_{int(st.session_state.get('form_epoch', 0))}"
identity_token = f"{form_token}_{'locked' if lock_seeded_identity else 'custom'}"

draft = st.session_state.draft
state = st.session_state.get("workflow")
if state and (
    int(float(state.get("plan_profile", {}).get("max_risk_score", -1))) != plan_risk
    or state.get("model_mode") != model_mode
):
    st.session_state.pop("workflow", None)
    state = None

st.markdown(
    """
<div class="hero">
  <div>
    <div class="brand-kicker">Evidence-first fund governance</div>
    <h1>Fiducia</h1>
    <p>Five bounded agents turn fund due diligence into a governed, explainable decision packet—without giving the model authority to approve money.</p>
  </div>
  <div class="demo-pill">◉ LIVE PROTOTYPE &nbsp;·&nbsp; POLICY 2026.09-demo.1</div>
</div>
""",
    unsafe_allow_html=True,
)

agent_graph_placeholder = st.empty()
agent_graph_placeholder.markdown(render_agent_graph(state), unsafe_allow_html=True)

def build_dot(state: dict[str, Any]) -> str:
    metrics = state.get("run_metrics", {})
    edges = metrics.get("edges_traversed", {})
    completed = set(state.get("completed_agents", []))
    active = state.get("active_agent", "")
    results = state.get("agent_results", {})

    agent_nodes = {
        "analyst": "Analyst\\nReviewer",
        "compliance": "Compliance\\n& Regulatory",
        "governance": "Governance\\n& Suitability",
        "finance": "Finance\\n& Cost",
        "decision_owner": "Decision\\nOwner",
    }

    lines = [
        'digraph G {',
        '  rankdir=LR;',
        '  node [style=filled fontname="Arial" fontsize=10];',
        '  edge [fontsize=9];',
    ]

    for key, label in agent_nodes.items():
        outcome = results.get(key, {}).get("outcome", "")
        if key == active:
            color = "#19c6b3"
        elif key in completed:
            color = "#ff6b6b" if outcome in {"FAIL", "REJECT"} else "#57d49b"
        else:
            color = "#1a3548"
        lines.append(f'  {key} [label="{label}" fillcolor="{color}" fontcolor="white" shape=box];')

    lines.append('  data_repair [label="Data\\nRepair" fillcolor="#f4b942" fontcolor="black" shape=diamond];')
    lines.append('  human_checkpoint [label="Human\\nCheckpoint" fillcolor="#f4b942" fontcolor="black" shape=octagon];')

    retries = state.get("retries", 0)
    edge_defs = [
        ("analyst", "compliance", ""),
        ("analyst", "data_repair", f"\xd7{retries}" if retries else ""),
        ("data_repair", "analyst", ""),
        ("compliance", "governance", ""),
        ("governance", "finance", ""),
        ("finance", "decision_owner", ""),
        ("decision_owner", "human_checkpoint", ""),
    ]
    for src, dst, label in edge_defs:
        key = f"{src}\u2192{dst}"
        count = edges.get(key, 0)
        lbl = label or (f"\xd7{count}" if count > 1 else "")
        lines.append(f'  {src} -> {dst} [label="{lbl}"];')

    lines.append("}")
    return "\n".join(lines)


def _build_mermaid(state: dict[str, Any]) -> str:
    handoffs = state.get("handoffs", [])
    lines = ["sequenceDiagram"]
    for h in handoffs:
        frm = h.get("from", "?")
        to = h.get("to", "?")
        reason = h.get("reason", h.get("payload_summary", ""))
        lines.append(f"    {frm}->>{to}: {reason}")
    return "\n".join(lines)


cockpit_tab, agents_tab, audit_tab, architecture_tab, monitor_tab, chat_tab = st.tabs(
    ["Decision cockpit", "Agent workspace", "Audit & controls", "Architecture & value", "Orchestration Monitor", "Ask Fiducia"]
)

with cockpit_tab:
    form_col, result_col = st.columns([0.92, 1.28], gap="large")
    with form_col:
        st.markdown("### Fund nomination")
        st.caption(
            "Edit metrics to create a custom case; turn off the identity lock to change "
            "the fund identity. Empty text fields remain missing—never coerced to zero."
        )
        if lock_seeded_identity:
            st.caption(
                "Demo-safe identity lock is ON. Turn it off in the sidebar only when "
                "you intentionally want to test a custom identity or fail-closed route."
            )
        with st.form(f"fund_form_{form_token}"):
            first, second = st.columns(2)
            ticker = first.text_input(
                "Ticker",
                value=str(draft.get("ticker", "")),
                disabled=lock_seeded_identity,
                key=f"{identity_token}_ticker",
            )
            fund_name = second.text_input(
                "Fund name",
                value=str(draft.get("fund_name", "")),
                disabled=lock_seeded_identity,
                key=f"{identity_token}_fund_name",
            )
            fund_type = first.selectbox(
                "Product",
                ["Mutual Fund", "ETF", "Leveraged ETF", "Inverse ETF"],
                index=max(0, ["Mutual Fund", "ETF", "Leveraged ETF", "Inverse ETF"].index(str(draft.get("fund_type", "Mutual Fund"))) if str(draft.get("fund_type", "Mutual Fund")) in ["Mutual Fund", "ETF", "Leveraged ETF", "Inverse ETF"] else 0),
                disabled=lock_seeded_identity,
                key=f"{identity_token}_fund_type",
            )
            asset_options = ["US Equity Index", "US Equity Active", "International Equity", "Investment Grade Bond", "Target Date", "Balanced", "Other"]
            asset = second.selectbox(
                "Asset class",
                asset_options,
                index=asset_options.index(str(draft.get("asset_class", "Other"))) if str(draft.get("asset_class", "Other")) in asset_options else len(asset_options) - 1,
                disabled=lock_seeded_identity,
                key=f"{identity_token}_asset_class",
            )
            nav = first.number_input("NAV ($)", min_value=0.0, value=float(draft.get("nav") or 0.0), step=0.01, key=f"{form_token}_nav")
            expense = second.number_input("Expense ratio (%)", min_value=0.0, value=float(draft.get("expense_ratio") or 0.0), step=0.01, format="%.2f", key=f"{form_token}_expense_ratio")
            sharpe_text = first.text_input("Sharpe ratio", value="" if draft.get("sharpe_ratio") in (None, "") else str(draft.get("sharpe_ratio")), key=f"{form_token}_sharpe_ratio")
            fee_text = second.text_input("Total 12b-1 fee (%)", value="" if draft.get("fee_12b1") in (None, "") else str(draft.get("fee_12b1")), key=f"{form_token}_fee_12b1")
            turnover = first.number_input("Turnover (%)", min_value=0.0, value=float(draft.get("turnover_rate") or 0.0), step=1.0, key=f"{form_token}_turnover_rate")
            aum = second.number_input("AUM ($MM)", min_value=0.0, value=float(draft.get("aum_millions") or 0.0), step=10.0, key=f"{form_token}_aum_millions")
            history = first.number_input("Track record (years)", min_value=0.0, value=float(draft.get("track_record_years") or 0.0), step=0.5, key=f"{form_token}_track_record_years")
            risk = second.slider("Fund risk score", 1, 10, int(float(draft.get("risk_score") or 5)), key=f"{form_token}_risk_score")
            status_options = ["Clear", "Under Review", "Restricted"]
            regulatory_status = first.selectbox("Control status", status_options, index=status_options.index(str(draft.get("regulatory_status", "Clear"))) if str(draft.get("regulatory_status", "Clear")) in status_options else 0, key=f"{form_token}_regulatory_status")
            as_of = second.text_input("As-of date", value=str(draft.get("as_of_date", "2026-09-22")), key=f"{form_token}_as_of_date")
            with st.expander("Fee components & untrusted evidence"):
                fee_left, fee_right = st.columns(2)
                distribution_text = fee_left.text_input("Distribution component (%)", value="" if draft.get("distribution_12b1_fee") in (None, "") else str(draft.get("distribution_12b1_fee")), key=f"{form_token}_distribution_12b1_fee")
                service_text = fee_right.text_input("Service component (%)", value="" if draft.get("service_fee") in (None, "") else str(draft.get("service_fee")), key=f"{form_token}_service_fee")
                sales_load = fee_left.number_input("Front-end sales load (%)", min_value=0.0, value=float(draft.get("sales_load_pct") or 0.0), step=0.25, key=f"{form_token}_sales_load_pct")
                breakpoint_schedule = fee_right.text_input("Breakpoints (threshold:load;…)", value=str(draft.get("breakpoint_schedule", "")), placeholder="250000:3.5;500000:2.5;1000000:1.5", key=f"{form_token}_breakpoint_schedule")
                evidence_note = st.text_area("Evidence note (isolated as data)", value=str(draft.get("evidence_note", "")), key=f"{form_token}_evidence_note")
            submitted = st.form_submit_button("Run governed approval", type="primary", width="stretch")

        if submitted:
            st.session_state.pop("workflow", None)
            state = None
            agent_graph_placeholder.markdown(
                render_agent_graph(None), unsafe_allow_html=True
            )
            try:
                submitted_fund = {
                    "ticker": ticker.strip().upper(),
                    "fund_name": fund_name.strip(),
                    "fund_type": fund_type,
                    "asset_class": asset,
                    "nav": nav,
                    "expense_ratio": expense,
                    "sharpe_ratio": as_optional_float(sharpe_text),
                    "fee_12b1": as_optional_float(fee_text),
                    "distribution_12b1_fee": as_optional_float(distribution_text),
                    "service_fee": as_optional_float(service_text),
                    "sales_load_pct": sales_load,
                    "breakpoint_schedule": breakpoint_schedule.strip() or None,
                    "turnover_rate": turnover,
                    "aum_millions": aum,
                    "track_record_years": history,
                    "risk_score": risk,
                    "regulatory_status": regulatory_status,
                    "as_of_date": as_of.strip(),
                    "source_conflict": bool(draft.get("source_conflict", False)),
                    "evidence_note": evidence_note,
                }
            except ValueError:
                st.error("Sharpe ratio and fee fields must be numbers or blank.")
            else:
                expected_identity = fund_by_ticker.get(submitted_fund["ticker"])
                identity_mismatches = []
                if expected_identity:
                    for identity_field in ("fund_name", "fund_type", "asset_class"):
                        submitted_value = str(submitted_fund.get(identity_field, "")).strip().casefold()
                        expected_value = str(expected_identity.get(identity_field, "")).strip().casefold()
                        if not submitted_value or submitted_value != expected_value:
                            identity_mismatches.append(identity_field)
                if identity_mismatches:
                    st.warning(
                        "Seed identity was modified ("
                        + ", ".join(identity_mismatches)
                        + "). Approved-source enrichment will intentionally fail closed; "
                        "use ‘Restore scenario defaults’ for the rehearsed route."
                    )
                live = st.empty()
                with st.status("Executing bounded agent graph…", expanded=True) as run_status:
                    final_state = None
                    previous_event_count = 0
                    try:
                        for snapshot in stream_workflow(
                            submitted_fund,
                            plan_profile={"plan_id": "ASU-DEMO-401A", "max_risk_score": plan_risk},
                            model_mode=model_mode,
                        ):
                            final_state = snapshot
                            live.markdown(render_agent_graph(snapshot), unsafe_allow_html=True)
                            agent_graph_placeholder.markdown(
                                render_agent_graph(snapshot), unsafe_allow_html=True
                            )
                            new_events = snapshot.get("events", [])[previous_event_count:]
                            for event in new_events[-2:]:
                                st.write(f"**{event['kind'].replace('_', ' ').title()}** · {event['message']}")
                            previous_event_count = len(snapshot.get("events", []))
                            if model_mode == "offline":
                                time.sleep(0.11)
                    except Exception as exc:
                        run_status.update(label="Workflow failed closed", state="error")
                        st.error(f"No decision was finalized: {type(exc).__name__}. Check the audit and service configuration.")
                    else:
                        st.session_state.workflow = final_state
                        state = final_state
                        run_status.update(label="Decision packet assembled", state="complete", expanded=False)
                        st.toast("Governed review completed", icon="✅")

    with result_col:
        st.markdown("### Decision packet")
        if not state:
            st.markdown(
                '<div class="decision-card"><div class="eyebrow">Ready for intake</div><div class="decision-label">Select a scenario and run</div><div class="summary">Start with SUNX for the golden path, DATA for self-correction, or INJX to demonstrate prompt-injection containment.</div></div>',
                unsafe_allow_html=True,
            )
        else:
            recommendation = str(state.get("recommendation", "PENDING"))
            st.markdown(
                f'<div class="decision-card {decision_css(recommendation)}">'
                f'<div class="eyebrow">{safe(state.get("fund", {}).get("ticker", "CASE"))} · Agent recommendation · {safe(state.get("status"))}</div>'
                f'<div class="decision-label">{safe(recommendation.replace("_", " "))}</div>'
                f'<div class="summary">{safe(state.get("final_summary", ""))}</div></div>',
                unsafe_allow_html=True,
            )
            # Self-correcting loop banner
            if state.get("retries", 0) > 0:
                st.markdown(
                    '<div class="alert gold"><b>⚠️ Self-Correcting Loop Triggered</b><br>'
                    'Fiduciary Governor detected anomaly and forced agent re-evaluation. '
                    f'Retry {state["retries"]}/{state.get("max_retries", 2)} completed.</div>',
                    unsafe_allow_html=True,
                )

            # TFGS card
            tfgs = state.get("tfgs_score", 0)
            _tfgs_color = "#57d49b" if tfgs >= 90 else "#f4b942" if tfgs >= 80 else "#ff6b6b"
            st.markdown(
                f'<div style="background:linear-gradient(145deg,#0e2437,#0a1a2a);border:2px solid {_tfgs_color};'
                f'border-radius:14px;padding:14px 18px;margin-bottom:12px;">'
                f'<div style="color:#91a7b8;font-size:.72rem;font-weight:800;letter-spacing:.14em;text-transform:uppercase;">TIAA Fiduciary Guardrail Score</div>'
                f'<div style="color:{_tfgs_color};font-size:2.1rem;font-weight:800;line-height:1.1;">{tfgs}/100</div>'
                f'<div style="color:#91a7b8;font-size:.78rem;">{"✅ Auto-approval eligible" if tfgs >= 90 else "⚠️ Human review required" if tfgs < 80 else "⚡ Conditional — review advised"}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            metric_a, metric_b, metric_c, metric_d = st.columns(4)
            metric_a.metric("Risk", f"{state.get('risk_score', 0)}/100")
            metric_b.metric("Confidence", f"{float(state.get('confidence', 0)):.0%}")
            metric_c.metric("Retries", f"{state.get('retries', 0)}/{state.get('max_retries', 2)}")
            metric_d.metric("Evidence gaps", len(state.get("missing_fields", [])))

            if state.get("human_decision"):
                decision = state["human_decision"]
                st.markdown(
                    f'<div class="alert teal"><b>Attested human decision: {safe(decision["action"])}</b><br>{safe(decision["reason"])} · {safe(decision["reviewer"])}</div>',
                    unsafe_allow_html=True,
                )
            elif state.get("needs_human"):
                reasons = "<br>• ".join(safe(reason) for reason in state.get("human_reasons", []))
                st.markdown(
                    f'<div class="alert gold"><b>Human checkpoint required</b><br>• {reasons}</div>',
                    unsafe_allow_html=True,
                )
                if st.button("Open approval / override", type="primary", width="stretch"):
                    human_review_dialog()
            else:
                st.markdown(
                    '<div class="alert teal"><b>Auto-approval gates passed.</b> No exception, conflict, boundary condition, or confidence shortfall was found.</div>',
                    unsafe_allow_html=True,
                )

            compliance = state.get("agent_results", {}).get("compliance", {})
            finance = state.get("agent_results", {}).get("finance", {})
            if compliance or finance:
                st.markdown("#### Compliance & fee snapshot")
                snap_a, snap_b, snap_c = st.columns(3)
                failed_checks = sum(1 for check in compliance.get("checks", []) if check.get("outcome") == "FAIL")
                snap_a.metric("Compliance exceptions", failed_checks)
                snap_b.metric("Expense vs cap", f"{float(finance.get('cap_delta_bps', 0)):+.0f} bps")
                drag = finance.get("projection", {}).get("estimated_fee_drag_vs_benchmark", 0)
                snap_c.metric("20-year fee drag*", f"${float(drag):,.0f}")
                st.caption("*Illustrative $1M constant-return comparison; not a forecast or investment advice.")

with agents_tab:
    st.markdown("### Live state, rationale & tool evidence")
    st.caption("The UI exposes concise decision rationale, calculations, rule/source identifiers and tool status—not private chain-of-thought.")
    if not state:
        st.info("Run a case to populate the five-agent workspace.")
    else:
        st.markdown(render_agent_graph(state), unsafe_allow_html=True)
        for key in AGENT_ORDER:
            result = state.get("agent_results", {}).get(key)
            if not result:
                continue
            icon = "✓" if result.get("outcome") in {"PASS", "APPROVE"} else "!"
            with st.expander(f"{icon}  {AGENT_LABELS[key]} · {str(result.get('outcome')).replace('_', ' ')}", expanded=key == "decision_owner"):
                left, right = st.columns([1.25, 0.75])
                with left:
                    st.markdown("**Structured explanation**")
                    st.caption("Narrative text is non-authoritative; the structured checks and deterministic gate control the outcome.")
                    st.write(result.get("rationale", ""))
                    if result.get("checks"):
                        check_rows = [
                            {
                                column: json.dumps(value, sort_keys=True)
                                if isinstance(value, (dict, list))
                                else str(value)
                                for column, value in check.items()
                            }
                            for check in result["checks"]
                        ]
                        st.dataframe(pd.DataFrame(check_rows), width="stretch", hide_index=True)
                with right:
                    st.metric("Agent confidence", f"{float(result.get('confidence', 0)):.0%}")
                    model = result.get("model", {})
                    st.caption(f"Narrative: {model.get('provider', 'deterministic')}" + (" · safe fallback" if model.get("fallback") else ""))
                    st.markdown("**Allowlisted tools**")
                    for tool in result.get("tools", []):
                        st.markdown(f'<span class="mini-tag">{safe(tool)}</span>', unsafe_allow_html=True)

        st.markdown("#### Tool invocation ledger")
        tool_rows = state.get("tool_calls", [])
        if tool_rows:
            display_rows = [
                {
                    "Agent": row.get("agent"),
                    "Tool": row.get("tool"),
                    "Status": row.get("status"),
                    "Result": row.get("output_summary"),
                }
                for row in tool_rows
            ]
            st.dataframe(pd.DataFrame(display_rows), width="stretch", hide_index=True)

with audit_tab:
    st.markdown("### Audit integrity & policy controls")
    if not state:
        st.info("Run a case to create a tamper-evident JSONL audit chain.")
    else:
        logger = AuditLogger(state["audit_path"])
        valid, errors = logger.verify()
        audit_path = Path(state["audit_path"])
        records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        top_a, top_b, top_c = st.columns(3)
        top_a.metric("Chain integrity", "VERIFIED" if valid else "FAILED")
        top_b.metric("Audit events", len(records))
        top_c.metric("Policy version", state["policy_version"])
        if not valid:
            st.error("Audit validation failed: " + "; ".join(errors))
        else:
            st.success("Every record hash and previous-hash link validates. Production hardens this with S3 Object Lock, KMS and CloudTrail.")
        audit_rows = [
            {
                "Seq": record["sequence"],
                "Time (UTC)": record["timestamp_utc"],
                "Actor": record["actor"],
                "Event": record["event_type"],
                "Hash": record["event_hash"][:14] + "…",
            }
            for record in records
        ]
        st.dataframe(pd.DataFrame(audit_rows), width="stretch", hide_index=True)
        st.download_button(
            "Download evidence trace (JSONL)",
            data=audit_path.read_bytes(),
            file_name=f"fiducia-{state['trace_id']}.jsonl",
            mime="application/x-ndjson",
        )

        st.markdown("#### Exact human-intervention gates")
        policy = state["policy"]["human_in_the_loop"]
        gates = [
            f"Minimum auto-approval confidence: {policy['minimum_auto_approval_confidence']:.0%}",
            f"Mandatory review risk score: ≥ {policy['mandatory_review_risk_score']}/100",
            f"Fee boundary: within ±{policy['fee_boundary_bps']} bps of category cap",
            "Any missing critical field after two approved-source retries",
            "Any source conflict, prompt injection, hard stop, or non-APPROVE recommendation",
            "REJECT → APPROVE override requires rationale, attestation and a second approver",
        ]
        for gate in gates:
            st.markdown(f"- {gate}")
        st.caption(f"Policy SHA-256: {state.get('policy_hash', 'n/a')}")

        # Fiduciary Guardrail Receipt
        receipt = state.get("fiduciary_guardrail_receipt", {})
        if receipt:
            with st.expander("View Immutable Audit Metadata Receipt — Fiduciary Guardrail (TFGS)"):
                st.json(receipt)

with architecture_tab:
    st.markdown("### Enterprise architecture")
    st.markdown(
        """
<div class="panel">
  <div class="eyebrow">Request path</div>
  <p><b>React / Streamlit</b> → API Gateway + Cognito → <b>AgentCore Runtime</b> (LangGraph) → Bedrock Converse + Guardrails</p>
  <div class="eyebrow">Evidence & policy plane</div>
  <p>S3 source documents → Textract / validated APIs → versioned policy engine → DynamoDB checkpoints → S3 Object Lock audit archive</p>
  <div class="eyebrow">Operations plane</div>
  <p>EventBridge + SQS for fan-out → CloudWatch / OpenTelemetry traces → KMS, IAM least privilege, PrivateLink, CloudTrail</p>
</div>
""",
        unsafe_allow_html=True,
    )
    value_a, value_b, value_c, value_d = st.columns(4)
    value_a.metric("Agent roles", "5 bounded")
    value_b.metric("Critical rules", "Deterministic")
    value_c.metric("Data retries", "≤ 2")
    value_d.metric("Horizontal scale", "Case-isolated")
    st.markdown("#### Business value")
    st.write(
        "Fiducia compresses queue and handoff time, produces a reusable evidence packet once, gives reviewers exception-only work, and creates a measurable control trail. The supplied business case models ROI with transparent assumptions rather than presenting an invented TIAA forecast."
    )
    st.markdown("#### Why this scales")
    st.write(
        "Stateless specialist workers scale independently; long-running state checkpoints by case; rule packs version by product and jurisdiction; SQS absorbs peaks; deterministic checks are cached by evidence hash; models can be routed by task cost without changing policy outcomes."
    )
    st.markdown(
        "[AWS AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html) · [SEC fee bulletin](https://www.sec.gov/investor/alerts/ib_mutualfundfees.pdf) · [FINRA Rule 2341](https://www.finra.org/rules-guidance/rulebooks/finra-rules/2341)"
    )

def _build_visnetwork_html(state: dict) -> str:
    """Return a self-contained HTML string with an animated vis-network agent graph."""
    completed = state.get("completed_agents", [])
    needs_human = state.get("needs_human", False)
    handoffs = state.get("handoffs", [])
    spans = state.get("spans", [])
    per_agent_metrics = state.get("run_metrics", {}).get("per_agent", {})
    retries = state.get("retries", 0)
    recommendation = state.get("recommendation", "")

    # Tool call counts per agent
    tool_counts: dict[str, int] = {}
    for sp in spans:
        if sp.get("kind") == "tool":
            ag = sp.get("attributes", {}).get("agent", sp.get("from_agent", ""))
            if ag:
                tool_counts[ag] = tool_counts.get(ag, 0) + 1

    # Build node list: router → agents → human_gate
    node_defs = [
        {"id": "router", "label": "Strands\nRouter", "group": "router", "title": "Natural-language entry point"},
        {"id": "analyst", "label": f"Analyst\n[{tool_counts.get('analyst', 0)} tools]", "group": "agent",
         "title": f"Analyst agent · tools={tool_counts.get('analyst',0)}"},
        {"id": "compliance", "label": f"Compliance\n[{tool_counts.get('compliance', 0)} tools]", "group": "agent",
         "title": f"Compliance agent · tools={tool_counts.get('compliance',0)}"},
        {"id": "governance", "label": f"Governance\n[{tool_counts.get('governance', 0)} tools]", "group": "agent",
         "title": f"Governance agent · tools={tool_counts.get('governance',0)}"},
        {"id": "finance", "label": f"Finance\n[{tool_counts.get('finance', 0)} tools]", "group": "agent",
         "title": f"Finance agent · tools={tool_counts.get('finance',0)}"},
        {"id": "decision_owner", "label": f"Decision\nOwner\n[{tool_counts.get('decision_owner', 0)} tools]",
         "group": "agent", "title": f"Decision owner · tools={tool_counts.get('decision_owner',0)}"},
    ]
    if needs_human:
        node_defs.append({"id": "human_gate", "label": f"Human\nReview\n({recommendation})",
                           "group": "human", "title": "Human-in-the-loop gate"})
    if retries > 0:
        node_defs.append({"id": "data_repair", "label": f"Data\nRepair\n×{retries}",
                           "group": "retry", "title": f"{retries} repair attempt(s)"})

    # Edge list
    _PIPELINE = ["analyst", "compliance", "governance", "finance", "decision_owner"]
    edge_defs = [{"from": "router", "to": "analyst", "label": "invoke", "dashes": True}]
    for i in range(len(_PIPELINE) - 1):
        edge_defs.append({"from": _PIPELINE[i], "to": _PIPELINE[i + 1], "label": "→"})
    if retries > 0:
        edge_defs.append({"from": "analyst", "to": "data_repair", "label": "repair", "color": "#ff9966"})
        edge_defs.append({"from": "data_repair", "to": "analyst", "label": "retry", "color": "#ff9966", "dashes": True})
    if needs_human:
        edge_defs.append({"from": "decision_owner", "to": "human_gate", "label": "escalate",
                           "color": "#f4b942", "width": 3})
    for h in handoffs[:6]:
        frm, to = h.get("from", ""), h.get("to", "")
        if frm and to and frm != to and frm in {n["id"] for n in node_defs} and to in {n["id"] for n in node_defs}:
            edge_defs.append({"from": frm, "to": to, "label": h.get("message_type", ""), "color": "#19c6b3",
                               "dashes": [5, 5]})

    # Animation sequence: completed agents in order
    anim_sequence = json.dumps(["router"] + completed + (["human_gate"] if needs_human else []))

    nodes_js = json.dumps(node_defs)
    edges_js = json.dumps(edge_defs)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.9/standalone/umd/vis-network.min.js"
  integrity="sha512-M6RAojasCzsf7tNiMQhA1bDE7hNPaCuDzBb+f2wKLXH53j/xWR/AiB73MsCLEzMNTwWLqtWbTJm2V3ACyCcA=="
  crossorigin="anonymous" referrerpolicy="no-referrer"></script>
<style>
  body {{ margin:0; background:#071321; font-family:'DM Sans',sans-serif; }}
  #net {{ width:100%; height:320px; border:1px solid #1e3c50; border-radius:8px; background:#0d2033; }}
  #controls {{ display:flex; gap:8px; padding:6px 4px; align-items:center; }}
  button {{ background:#19c6b3; color:#071321; border:none; padding:5px 14px; border-radius:6px;
             font-weight:700; cursor:pointer; font-size:.82rem; }}
  button:hover {{ background:#0fa898; }}
  #status {{ color:#91a7b8; font-size:.78rem; }}
</style>
</head>
<body>
<div id="controls">
  <button onclick="replayAnimation()">▶ Replay run</button>
  <span id="status">Ready</span>
</div>
<div id="net"></div>
<script>
var GROUP_COLORS = {{
  router:  {{ background:"#254157", border:"#19c6b3", highlight:{{background:"#19c6b3",border:"#ffffff"}} }},
  agent:   {{ background:"#0e2437", border:"#254157", highlight:{{background:"#19c6b3",border:"#ffffff"}} }},
  human:   {{ background:"#3a2200", border:"#f4b942", highlight:{{background:"#f4b942",border:"#ffffff"}} }},
  retry:   {{ background:"#2a1800", border:"#ff9966", highlight:{{background:"#ff9966",border:"#ffffff"}} }},
}};
var ACTIVE_COLOR = {{ background:"#19c6b3", border:"#ffffff", fontColor:"#071321" }};
var DONE_COLOR   = {{ background:"#0f4035", border:"#19c6b3" }};

var nodeData = {nodes_js};
var edgeData = {edges_js};
var animSeq  = {anim_sequence};

// Assign group colors
nodeData.forEach(function(n) {{
  var gc = GROUP_COLORS[n.group] || GROUP_COLORS.agent;
  n.color = gc;
  n.font  = {{ color:"#d3dce4", size:11, multi:true }};
  n.shape = n.group === "human" ? "diamond" : (n.group === "router" ? "hexagon" : "box");
  n.margin = 8;
}});

edgeData.forEach(function(e) {{
  if (!e.color) e.color = {{ color:"#254157", highlight:"#19c6b3" }};
  else e.color = {{ color: e.color, highlight:"#ffffff" }};
  e.font = {{ color:"#91a7b8", size:9, align:"middle" }};
  e.arrows = "to";
  e.smooth = {{ type:"curvedCW", roundness:0.15 }};
}});

var nodes = new vis.DataSet(nodeData);
var edges = new vis.DataSet(edgeData);
var container = document.getElementById("net");
var network = new vis.Network(container, {{nodes:nodes, edges:edges}}, {{
  layout: {{ hierarchical: {{ enabled:true, direction:"LR", sortMethod:"directed", levelSeparation:110, nodeSpacing:60 }} }},
  physics: {{ enabled:false }},
  interaction: {{ tooltipDelay:200, zoomView:false }},
}});

var _animTimer = null;

function replayAnimation() {{
  // Reset all nodes
  nodeData.forEach(function(n) {{
    nodes.update({{ id:n.id, color: GROUP_COLORS[n.group] || GROUP_COLORS.agent }});
  }});
  document.getElementById("status").textContent = "Replaying…";
  if (_animTimer) clearTimeout(_animTimer);
  var step = 0;
  function tick() {{
    if (step >= animSeq.length) {{
      document.getElementById("status").textContent = "Done (" + animSeq.length + " nodes)";
      return;
    }}
    var nid = animSeq[step];
    // Flash active
    nodes.update({{ id:nid, color:ACTIVE_COLOR }});
    setTimeout(function() {{
      nodes.update({{ id:nid, color:DONE_COLOR }});
    }}, 350);
    document.getElementById("status").textContent = "Active: " + nid;
    step++;
    _animTimer = setTimeout(tick, 520);
  }}
  tick();
}}

// Auto-play on load
setTimeout(replayAnimation, 400);
</script>
</body>
</html>"""


with monitor_tab:
    st.markdown("### Orchestration Monitor")
    if not state:
        st.info("Run a case to populate the orchestration monitor.")
    else:
        # 3a. Animated agent graph
        st.markdown("#### Agent execution graph")
        import streamlit.components.v1 as _stc
        _stc.html(_build_visnetwork_html(state), height=380)

        # 3b. KPI row
        metrics_data = state.get("run_metrics", {})
        kpi_cols = st.columns(8)
        kpi_cols[0].metric("Agents Invoked", metrics_data.get("total_agents_invoked", len(state.get("completed_agents", []))))
        kpi_cols[1].metric("Tool Calls", metrics_data.get("total_tool_calls", len(state.get("tool_calls", []))))
        kpi_cols[2].metric("Bedrock Calls", metrics_data.get("total_bedrock_calls", 0))
        kpi_cols[3].metric("Tokens In", metrics_data.get("total_input_tokens", 0))
        kpi_cols[4].metric("Tokens Out", metrics_data.get("total_output_tokens", 0))
        kpi_cols[5].metric("Total Latency (ms)", f"{metrics_data.get('total_latency_ms', 0):.0f}")
        kpi_cols[6].metric("Retries", metrics_data.get("total_retries", state.get("retries", 0)))
        kpi_cols[7].metric("Human Gates", metrics_data.get("human_gates_triggered", 1 if state.get("needs_human") else 0))

        # 3c. Per-agent table
        per_agent = metrics_data.get("per_agent", {})
        if per_agent:
            st.markdown("#### Per-agent summary")
            agent_rows = []
            for name, data in per_agent.items():
                agent_rows.append({
                    "Agent": name,
                    "Invocations": data.get("invocations", 0),
                    "Tool Calls": data.get("tool_calls", 0),
                    "LLM Calls": data.get("llm_calls", 0),
                    "Tokens In": data.get("input_tokens", 0),
                    "Tokens Out": data.get("output_tokens", 0),
                    "Latency (ms)": round(data.get("latency_ms", 0), 1),
                    "Outcome": data.get("outcome") or "",
                    "Confidence": f"{float(data.get('confidence') or 0):.0%}",
                })
            st.dataframe(pd.DataFrame(agent_rows), hide_index=True)

        # 3d. Plotly Gantt timeline
        spans = state.get("spans", [])
        if spans and _PLOTLY_AVAILABLE:
            st.markdown("#### Span timeline")
            kind_colors = {
                "agent": "#19c6b3",
                "tool": "#f4b942",
                "llm": "#a970f4",
                "handoff": "#57d49b",
                "retry": "#ff9966",
                "hitl": "#ff6b6b",
            }
            gantt_rows = []
            for s in spans:
                if s.get("start_ts") and s.get("end_ts"):
                    import datetime
                    gantt_rows.append({
                        "Task": s.get("name", s.get("kind", "?")),
                        "Start": datetime.datetime.utcfromtimestamp(s["start_ts"]).isoformat(),
                        "Finish": datetime.datetime.utcfromtimestamp(s["end_ts"]).isoformat(),
                        "Kind": s.get("kind", "?"),
                    })
            if gantt_rows:
                fig = px.timeline(
                    pd.DataFrame(gantt_rows),
                    x_start="Start", x_end="Finish", y="Task",
                    color="Kind",
                    color_discrete_map=kind_colors,
                    title="Span Gantt",
                )
                fig.update_layout(height=300, paper_bgcolor="#071321", plot_bgcolor="#0d2033",
                                  font_color="#d3dce4")
                st.plotly_chart(fig, use_container_width=True)

        # 3e. Handoff message log
        handoffs = state.get("handoffs", [])
        if handoffs:
            st.markdown("#### Handoff message log")
            for h in handoffs:
                frm = h.get("from", "?")
                to = h.get("to", "?")
                msg_type = h.get("message_type", "?")
                reason = h.get("reason", "")
                with st.expander(f"{frm} → {to} · {msg_type} · {reason[:60]}"):
                    st.json(h)

        # Mermaid sequence diagram
        mermaid_str = _build_mermaid(state)
        if len(mermaid_str.splitlines()) > 1:
            st.markdown("#### Sequence diagram (Mermaid source)")
            st.code(mermaid_str, language="text")

        # 3f. Bedrock call inspector
        llm_spans = [s for s in spans if s.get("kind") == "llm"]
        if llm_spans:
            st.markdown("#### Bedrock call inspector")
            for s in llm_spans:
                attrs = s.get("attributes", {})
                with st.expander(f"{s.get('name', '?')} · {attrs.get('model_id', 'n/a')} · {s.get('duration_ms', 0):.0f}ms"):
                    st.json({
                        "model_id": attrs.get("model_id"),
                        "request_id": attrs.get("request_id"),
                        "latency_ms": s.get("duration_ms"),
                        "input_tokens": attrs.get("input_tokens", 0),
                        "output_tokens": attrs.get("output_tokens", 0),
                        "tools_chosen": attrs.get("tools_called", []),
                        "model_outcome_rejected": attrs.get("model_outcome_rejected", False),
                        "fallback": attrs.get("fallback", False),
                    })

        # 3g. Run all scenarios batch view
        st.markdown("#### Batch scenario runner")
        DEMO_TICKERS = ["SUNX", "DATA", "ALPHX", "SPECX", "CONFX", "INJX", "BLANK"]
        if st.button("Run all 7 demo scenarios (offline)"):
            batch_results = []
            with st.spinner("Running all scenarios…"):
                for ticker in DEMO_TICKERS:
                    demo_fund = fund_by_ticker.get(ticker)
                    if not demo_fund:
                        continue
                    try:
                        s = run_workflow(
                            demo_fund,
                            plan_profile={"plan_id": "ASU-DEMO-401A", "max_risk_score": 7},
                            model_mode="offline",
                        )
                        m = s.get("run_metrics", {})
                        batch_results.append({
                            "Ticker": ticker,
                            "Route": s.get("status", "?"),
                            "Agents": len(s.get("completed_agents", [])),
                            "Tool Calls": m.get("total_tool_calls", len(s.get("tool_calls", []))),
                            "LLM Calls": m.get("total_bedrock_calls", 0),
                            "Latency (ms)": f"{m.get('total_latency_ms', 0):.0f}",
                            "Retries": s.get("retries", 0),
                            "Human Gates": 1 if s.get("needs_human") else 0,
                            "Recommendation": s.get("recommendation", "?"),
                            "Confidence": f"{float(s.get('confidence', 0)):.0%}",
                        })
                    except Exception as batch_err:
                        batch_results.append({"Ticker": ticker, "Route": f"ERROR: {batch_err}"})
            if batch_results:
                st.dataframe(pd.DataFrame(batch_results), hide_index=True)

with chat_tab:
    st.markdown("### Ask Fiducia")
    st.caption(
        "Natural-language interface to the governed workflow. "
        'Try: "Run approval for DATA" or "What is SUNX\'s recommendation?" '
        "Responses route through the Strands agent when Bedrock is configured; offline mode answers directly."
    )

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Ask about a fund or approval…")
    if user_input:
        st.session_state["chat_history"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Routing through Fiducia…"):
                try:
                    _model_mode = st.session_state.get("model_mode", "offline")

                    # Try Strands router (requires bedrock mode + strands installed)
                    _router_response = None
                    if _model_mode == "bedrock":
                        try:
                            from strands import Agent, tool as strands_tool
                            from strands.models import BedrockModel
                            from fiducia.tools import load_funds as _load_funds_chat
                            from fiducia.workflow import run_workflow as _run_wf_chat

                            _funds_chat = {f["ticker"]: f for f in _load_funds_chat()}

                            @strands_tool
                            def run_fund_approval(ticker: str) -> dict:
                                """Run the Fiducia governed approval workflow for a fund ticker.

                                Args:
                                    ticker: Fund ticker symbol (e.g. SUNX, DATA).

                                Returns:
                                    Approval result dict with recommendation and summary.
                                """
                                fund = _funds_chat.get(ticker.strip().upper())
                                if fund is None:
                                    return {"error": f"Unknown ticker: {ticker}"}
                                _s = _run_wf_chat(fund, model_mode=_model_mode)
                                return {
                                    "ticker": ticker.upper(),
                                    "recommendation": _s["recommendation"],
                                    "risk_score": _s["risk_score"],
                                    "needs_human": _s["needs_human"],
                                    "summary": _s["final_summary"],
                                }

                            _nl_system = (
                                "You are Fiducia, a governed fund-approval assistant. "
                                "For fund approvals, always call run_fund_approval. "
                                "Never invent outcomes — only tool results are authoritative."
                            )
                            _bedrock_m = BedrockModel(model_id="us.anthropic.claude-sonnet-5", region_name="us-east-1")
                            _router = Agent(model=_bedrock_m, system_prompt=_nl_system, tools=[run_fund_approval])
                            _router_response = str(_router(user_input))
                        except Exception as _strands_err:
                            _router_response = None  # fall through to offline

                    if _router_response is None:
                        # Offline: simple ticker extraction fallback
                        import re
                        from fiducia.tools import load_funds as _lf
                        from fiducia.workflow import run_workflow as _rwf
                        _all_tickers = {f["ticker"] for f in _lf()}
                        _found = [t for t in _all_tickers if re.search(rf"\b{re.escape(t)}\b", user_input, re.I)]
                        if _found:
                            ticker_hit = _found[0].upper()
                            fund_hit = {f["ticker"]: f for f in _lf()}[ticker_hit]
                            _ws = _rwf(fund_hit, model_mode="offline")
                            _router_response = (
                                f"**{ticker_hit}** — {_ws['recommendation']}  \n"
                                f"{_ws['final_summary']}  \n"
                                f"Needs human review: {'Yes' if _ws['needs_human'] else 'No'}"
                            )
                        else:
                            _router_response = (
                                "I can run governed approvals for these funds: "
                                + ", ".join(sorted(_all_tickers))
                                + ". Try asking: *Run approval for SUNX*."
                            )

                    st.markdown(_router_response)
                    st.session_state["chat_history"].append({"role": "assistant", "content": _router_response})
                except Exception as _chat_err:
                    _err_msg = f"Router error: {_chat_err}"
                    st.error(_err_msg)
                    st.session_state["chat_history"].append({"role": "assistant", "content": _err_msg})

    if st.session_state["chat_history"]:
        if st.button("Clear chat", key="clear_chat"):
            st.session_state["chat_history"] = []
            st.rerun()


st.markdown(
    '<div class="footer-note">Fiducia is a synthetic hackathon prototype for decision support. It is not legal, fiduciary, tax, or investment advice—and it does not represent TIAA internal policy.</div>',
    unsafe_allow_html=True,
)
