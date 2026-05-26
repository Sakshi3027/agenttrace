"""
AgentTrace — Lead Research Agent
Given a company name, researches it and writes a personalized outreach summary.
This is the agent we will wrap with observability.
"""

from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from ddgs import DDGS
import json
import time
from agent.config import GROQ_API_KEY, GROQ_MODEL

# ─── STATE ────────────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    company: str
    company_info: str
    recent_news: str
    decision_makers: str
    outreach_summary: str
    steps_completed: list
    errors: list

# ─── LLM ──────────────────────────────────────────────────────────────────────
def get_llm():
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL,
        temperature=0.1,
    )

# ─── TOOLS ────────────────────────────────────────────────────────────────────
def web_search(query: str, max_results: int = 3) -> str:
    """Search the web using DuckDuckGo — free, no API key needed."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No results found."
        formatted = []
        for r in results:
            formatted.append(f"Title: {r.get('title','')}\nSnippet: {r.get('body','')}\nURL: {r.get('href','')}")
        return "\n\n".join(formatted)
    except Exception as e:
        return f"Search failed: {str(e)}"

# ─── AGENT NODES ──────────────────────────────────────────────────────────────
def research_company(state: AgentState) -> AgentState:
    """Step 1: Research basic company information."""
    company = state["company"]
    print(f"  [Step 1] Researching {company}...")

    search_results = web_search(f"{company} company overview business what they do")
    llm = get_llm()

    messages = [
        SystemMessage(content="You are a business research analyst. Extract and summarize key company information concisely."),
        HumanMessage(content=f"""Based on these search results about {company}, provide a 3-4 sentence company overview covering: what they do, their market, approximate size, and key value proposition.

Search results:
{search_results}

Company overview:""")
    ]

    response = llm.invoke(messages)
    state["company_info"] = response.content
    state["steps_completed"].append("research_company")
    return state


def find_recent_news(state: AgentState) -> AgentState:
    """Step 2: Find recent news and developments."""
    company = state["company"]
    print(f"  [Step 2] Finding recent news for {company}...")

    search_results = web_search(f"{company} news 2024 2025 recent developments funding product launch")
    llm = get_llm()

    messages = [
        SystemMessage(content="You are a business intelligence analyst. Summarize recent company news concisely."),
        HumanMessage(content=f"""Based on these search results, summarize the 2-3 most relevant recent developments for {company} in 2-3 sentences. Focus on funding, product launches, partnerships, or growth signals.

Search results:
{search_results}

Recent developments:""")
    ]

    response = llm.invoke(messages)
    state["recent_news"] = response.content
    state["steps_completed"].append("find_recent_news")
    return state


def identify_decision_makers(state: AgentState) -> AgentState:
    """Step 3: Identify key decision makers."""
    company = state["company"]
    print(f"  [Step 3] Identifying decision makers at {company}...")

    search_results = web_search(f"{company} CEO CTO VP leadership team executives")
    llm = get_llm()

    messages = [
        SystemMessage(content="You are a sales intelligence analyst. Identify key decision makers concisely."),
        HumanMessage(content=f"""Based on these search results, identify 2-3 key decision makers at {company}. For each, provide their name, title, and one sentence about their focus area.

Search results:
{search_results}

Key decision makers:""")
    ]

    response = llm.invoke(messages)
    state["decision_makers"] = response.content
    state["steps_completed"].append("identify_decision_makers")
    return state


def write_outreach_summary(state: AgentState) -> AgentState:
    """Step 4: Write personalized outreach summary."""
    company = state["company"]
    print(f"  [Step 4] Writing outreach summary for {company}...")

    llm = get_llm()

    messages = [
        SystemMessage(content="You are an expert B2B sales copywriter. Write concise, personalized outreach that doesn't sound generic."),
        HumanMessage(content=f"""Write a personalized outreach email opening (3-4 sentences) for {company} based on this research:

Company Overview: {state['company_info']}
Recent News: {state['recent_news']}
Key Decision Makers: {state['decision_makers']}

The outreach should reference specific details from the research and feel genuinely personalized. Do not use generic phrases like "I hope this email finds you well."

Outreach:""")
    ]

    response = llm.invoke(messages)
    state["outreach_summary"] = response.content
    state["steps_completed"].append("write_outreach_summary")
    return state


# ─── BUILD GRAPH ──────────────────────────────────────────────────────────────
def build_agent():
    """Build and compile the LangGraph agent."""
    workflow = StateGraph(AgentState)

    workflow.add_node("research_company", research_company)
    workflow.add_node("find_recent_news", find_recent_news)
    workflow.add_node("identify_decision_makers", identify_decision_makers)
    workflow.add_node("write_outreach_summary", write_outreach_summary)

    workflow.set_entry_point("research_company")
    workflow.add_edge("research_company", "find_recent_news")
    workflow.add_edge("find_recent_news", "identify_decision_makers")
    workflow.add_edge("identify_decision_makers", "write_outreach_summary")
    workflow.add_edge("write_outreach_summary", END)

    return workflow.compile()


# ─── RUN ──────────────────────────────────────────────────────────────────────
def run_agent(company: str) -> AgentState:
    """Run the lead research agent for a given company."""
    agent = build_agent()

    initial_state = AgentState(
        company=company,
        company_info="",
        recent_news="",
        decision_makers="",
        outreach_summary="",
        steps_completed=[],
        errors=[],
    )

    print(f"\n🔍 Running Lead Research Agent for: {company}")
    result = agent.invoke(initial_state)
    print(f"✅ Completed {len(result['steps_completed'])} steps")
    return result


if __name__ == "__main__":
    result = run_agent("Stripe")
    print("\n" + "="*50)
    print("COMPANY INFO:", result["company_info"])
    print("\nRECENT NEWS:", result["recent_news"])
    print("\nDECISION MAKERS:", result["decision_makers"])
    print("\nOUTREACH:", result["outreach_summary"])
