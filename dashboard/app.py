"""
AgentTrace — Observability Dashboard
Real-time visibility into agent health, step scores, and alerts.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from tracer.drift import get_health_summary, get_score_history, get_latency_stats
from tracer.trace_db import get_all_runs, get_steps_for_run, get_evals_for_run, db_exists
from tracer.evaluator import evaluate_run
from agent.traced_agent import run_traced_agent

st.set_page_config(
    page_title="AgentTrace",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
st.sidebar.image("https://img.icons8.com/fluency/96/search.png", width=60)
st.sidebar.title("AgentTrace")
st.sidebar.caption("LLM Agent Observability Framework")

page = st.sidebar.radio("Navigate", [
    "🏠 Agent Health",
    "🔍 Run Explorer",
    "📊 Eval Analytics",
    "⚡ Run New Agent",
])

st.sidebar.divider()
if st.sidebar.button("🔄 Refresh", use_container_width=True):
    st.rerun()

# ─── PAGE: AGENT HEALTH ───────────────────────────────────────────────────────
if page == "🏠 Agent Health":
    st.title("🔭 AgentTrace — Agent Health Dashboard")
    st.caption("Real-time observability for your LLM agent")

    summary = get_health_summary()

    # Status banner
    status = summary["status"]
    color_map = {"healthy": "green", "degraded": "orange", "critical": "red", "no_data": "gray"}
    emoji_map = {"healthy": "✅", "degraded": "⚠️", "critical": "🚨", "no_data": "❓"}
    color = color_map.get(status, "gray")
    emoji = emoji_map.get(status, "❓")
    st.markdown(f"### Agent Status: :{color}[{emoji} {status.upper()}]")

    # KPI row
    runs_df = get_all_runs()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Overall Score", f"{summary.get('overall_score', 0):.2f}")
    col2.metric("Total Runs", len(runs_df))
    col3.metric("Active Alerts", summary.get("alert_count", 0))
    success_rate = len(runs_df[runs_df["status"] == "success"]) / len(runs_df) * 100 if len(runs_df) > 0 else 0
    col4.metric("Success Rate", f"{success_rate:.0f}%")

    st.divider()

    # Alerts
    alerts = summary.get("alerts", [])
    if alerts:
        st.subheader("🚨 Active Alerts")
        for alert in alerts:
            sev_color = "red" if alert["severity"] == "HIGH" else "orange"
            st.markdown(f":{sev_color}[**[{alert['severity']}] {alert['type']}**] — {alert['message']}")
        st.divider()

    # Step score gauges
    st.subheader("📈 Step Quality Scores")
    step_stats = summary.get("step_stats", [])
    if step_stats:
        cols = st.columns(len(step_stats))
        for i, step in enumerate(step_stats):
            score = step["avg_score"]
            color = "#4CAF50" if score >= 0.85 else "#FF9800" if score >= 0.70 else "#F44336"
            with cols[i]:
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=score * 100,
                    gauge={
                        "axis": {"range": [0, 100]},
                        "bar": {"color": color},
                        "steps": [
                            {"range": [0, 70], "color": "#ffebee"},
                            {"range": [70, 85], "color": "#fff3e0"},
                            {"range": [85, 100], "color": "#e8f5e9"},
                        ],
                    },
                    title={"text": step["step_name"].replace("_", " ").title(), "font": {"size": 12}},
                ))
                fig.update_layout(height=200, margin=dict(t=40, b=0, l=10, r=10))
                st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Score history line chart
    st.subheader("📉 Score Trend Over Time")
    history = get_score_history()
    if not history.empty:
        history["run_label"] = history["company"] + " (" + history["evaluated_at"].str[:10] + ")"
        fig = px.line(
            history, x="run_label", y="score",
            color="step_name", markers=True,
            labels={"score": "Quality Score", "run_label": "Run", "step_name": "Step"},
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.add_hline(y=0.70, line_dash="dash", line_color="orange", annotation_text="Alert threshold (0.70)")
        fig.update_layout(height=400, yaxis=dict(range=[0, 1.1]))
        st.plotly_chart(fig, use_container_width=True)

    # Latency
    st.subheader("⚡ Step Latency")
    latency_df = get_latency_stats()
    if not latency_df.empty:
        fig = px.bar(
            latency_df, x="step_name", y="avg_latency_ms",
            color="avg_latency_ms", color_continuous_scale="RdYlGn_r",
            labels={"avg_latency_ms": "Avg Latency (ms)", "step_name": "Step"},
        )
        fig.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

# ─── PAGE: RUN EXPLORER ───────────────────────────────────────────────────────
elif page == "🔍 Run Explorer":
    st.title("🔍 Run Explorer")
    st.caption("Inspect every agent run, step by step.")

    runs_df = get_all_runs()
    if runs_df.empty:
        st.warning("No runs yet. Go to 'Run New Agent' to get started.")
        st.stop()

    # Run selector
    runs_df["label"] = runs_df["company"] + " — " + runs_df["started_at"].str[:19] + " (" + runs_df["status"] + ")"
    selected_label = st.selectbox("Select a run:", runs_df["label"].tolist())
    selected_run = runs_df[runs_df["label"] == selected_label].iloc[0]
    run_id = selected_run["run_id"]

    col1, col2, col3 = st.columns(3)
    col1.metric("Company", selected_run["company"])
    col2.metric("Total Latency", f"{selected_run['total_latency_ms']}ms")
    col3.metric("Status", selected_run["status"])

    st.divider()

    # Steps
    steps_df = get_steps_for_run(run_id)
    evals_df = get_evals_for_run(run_id)

    st.subheader("Step Breakdown")
    for _, step in steps_df.iterrows():
        step_eval = evals_df[evals_df["step_name"] == step["step_name"]] if not evals_df.empty else pd.DataFrame()
        score = step_eval.iloc[0]["score"] if len(step_eval) > 0 else None
        reasoning = step_eval.iloc[0]["reasoning"] if len(step_eval) > 0 else ""

        score_str = f"Score: {score:.2f}" if score is not None else "Not evaluated"
        status_emoji = "✅" if step["status"] == "success" else "❌"

        with st.expander(f"{status_emoji} **{step['step_name']}** — {step['latency_ms']}ms — {score_str}", expanded=True):
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Input:**")
                st.text(step["input_text"] or "N/A")
            with col_b:
                st.markdown("**Output:**")
                st.text(step["output_text"] or "N/A")

            if reasoning:
                st.markdown(f"**Eval reasoning:** {reasoning}")

            if score is not None:
                score_color = "green" if score >= 0.85 else "orange" if score >= 0.70 else "red"
                st.markdown(f"**Quality score:** :{score_color}[{score:.2f}]")

# ─── PAGE: EVAL ANALYTICS ─────────────────────────────────────────────────────
elif page == "📊 Eval Analytics":
    st.title("📊 Eval Analytics")
    st.caption("Aggregate quality metrics across all agent runs.")

    history = get_score_history()
    if history.empty:
        st.warning("No evals yet.")
        st.stop()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Score Distribution by Step")
        fig = px.box(
            history, x="step_name", y="score",
            color="step_name",
            color_discrete_sequence=px.colors.qualitative.Set2,
            labels={"score": "Quality Score", "step_name": "Step"},
        )
        fig.add_hline(y=0.70, line_dash="dash", line_color="orange")
        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Score by Company")
        company_scores = history.groupby(["company", "step_name"])["score"].mean().reset_index()
        fig = px.bar(
            company_scores, x="company", y="score",
            color="step_name", barmode="group",
            color_discrete_sequence=px.colors.qualitative.Set2,
            labels={"score": "Avg Score", "company": "Company"},
        )
        fig.add_hline(y=0.70, line_dash="dash", line_color="orange")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("All Eval Results")
    display_cols = ["company", "step_name", "score", "reasoning", "evaluated_at"]
    st.dataframe(history[display_cols].sort_values("evaluated_at", ascending=False), use_container_width=True)

# ─── PAGE: RUN NEW AGENT ──────────────────────────────────────────────────────
elif page == "⚡ Run New Agent":
    st.title("⚡ Run New Agent")
    st.caption("Run the lead research agent on any company and trace it in real time.")

    company = st.text_input("Company name:", placeholder="e.g. Figma, Notion, Vercel")

    col1, col2 = st.columns(2)
    run_agent = col1.button("🚀 Run Agent + Trace", type="primary", disabled=not company)
    run_and_eval = col2.button("🚀 Run + Trace + Eval", type="primary", disabled=not company)

    if (run_agent or run_and_eval) and company:
        with st.spinner(f"Running agent for {company}..."):
            result, run_id = run_traced_agent(company)

        st.success(f"✅ Run complete! Run ID: `{run_id[:8]}`")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Company Info")
            st.info(result["company_info"])
            st.subheader("Recent News")
            st.info(result["recent_news"])
        with col2:
            st.subheader("Decision Makers")
            st.info(result["decision_makers"])
            st.subheader("Outreach Draft")
            st.success(result["outreach_summary"])

        if run_and_eval:
            st.divider()
            st.subheader("🧑‍⚖️ Running Evals...")
            with st.spinner("Evaluating output quality..."):
                eval_results = evaluate_run(run_id)

            for eval_result in eval_results:
                score = eval_result["score"]
                color = "green" if score >= 0.85 else "orange" if score >= 0.70 else "red"
                st.markdown(f"**{eval_result['step_name']}:** :{color}[{score:.2f}] — {eval_result['reasoning']}")

            st.divider()
            st.info("Go to **Agent Health** to see updated dashboard.")
