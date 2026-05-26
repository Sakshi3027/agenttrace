"""
AgentTrace — Traced Lead Research Agent
Same agent as lead_agent.py but with full observability via StepTracer.
"""

from agent.lead_agent import (
    AgentState, get_llm, web_search,
    build_agent, GROQ_API_KEY
)
from tracer.tracer import RunTracer, StepTracer
from tracer.trace_db import save_step, get_all_runs, get_steps_for_run
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
import uuid


# ─── TRACED NODES ─────────────────────────────────────────────────────────────
def make_traced_node(step_name: str, run_tracer: RunTracer, original_func):
    """Wrap any agent node with tracing."""
    def traced_node(state: AgentState) -> AgentState:
        input_text = f"Company: {state['company']}"
        with StepTracer(run_tracer.run_id, step_name, input_text) as step:
            result = original_func(state)
            # Capture output based on step
            output_map = {
                "research_company": result.get("company_info", ""),
                "find_recent_news": result.get("recent_news", ""),
                "identify_decision_makers": result.get("decision_makers", ""),
                "write_outreach_summary": result.get("outreach_summary", ""),
            }
            step.output_text = output_map.get(step_name, "")
        return result
    return traced_node


def run_traced_agent(company: str) -> tuple[AgentState, str]:
    """
    Run the lead research agent with full tracing.
    Returns (result, run_id).
    """
    from agent.lead_agent import research_company, find_recent_news, identify_decision_makers, write_outreach_summary

    with RunTracer(company) as run_tracer:
        run_id = run_tracer.run_id

        # Build traced graph
        workflow = StateGraph(AgentState)
        workflow.add_node("research_company", make_traced_node("research_company", run_tracer, research_company))
        workflow.add_node("find_recent_news", make_traced_node("find_recent_news", run_tracer, find_recent_news))
        workflow.add_node("identify_decision_makers", make_traced_node("identify_decision_makers", run_tracer, identify_decision_makers))
        workflow.add_node("write_outreach_summary", make_traced_node("write_outreach_summary", run_tracer, write_outreach_summary))

        workflow.set_entry_point("research_company")
        workflow.add_edge("research_company", "find_recent_news")
        workflow.add_edge("find_recent_news", "identify_decision_makers")
        workflow.add_edge("identify_decision_makers", "write_outreach_summary")
        workflow.add_edge("write_outreach_summary", END)

        agent = workflow.compile()

        initial_state = AgentState(
            company=company,
            company_info="",
            recent_news="",
            decision_makers="",
            outreach_summary="",
            steps_completed=[],
            errors=[],
        )

        print(f"\n🔍 Running Traced Agent for: {company}")
        result = agent.invoke(initial_state)
        print(f"✅ Run {run_id[:8]} complete — {len(result['steps_completed'])} steps traced")

    return result, run_id


if __name__ == "__main__":
    # Run against a few companies to build up trace data
    companies = ["Stripe", "Notion", "Linear"]
    for company in companies:
        result, run_id = run_traced_agent(company)
        print(f"  Run ID: {run_id[:8]} | Outreach preview: {result['outreach_summary'][:100]}...")

    print("\n📊 All runs in database:")
    runs_df = get_all_runs()
    print(runs_df[["company", "status", "total_latency_ms", "started_at"]].to_string())
