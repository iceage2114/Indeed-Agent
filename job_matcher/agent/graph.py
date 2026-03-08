"""
Top-level LangGraph StateGraph assembly for the Job Matcher Agent.
"""

from langgraph.graph import StateGraph, START, END

from agent.state import AgentState
from agent.nodes.resume_parser import parse_resume
from agent.nodes.report_generator import generate_report
from agent.subgraphs.retrieval_subgraph import build_retrieval_subgraph


def build_graph():
    """Assemble and compile the top-level agent graph."""
    graph = StateGraph(AgentState)

    graph.add_node("parse_resume",    parse_resume)
    graph.add_node("retrieval",       build_retrieval_subgraph().compile())
    graph.add_node("generate_report", generate_report)

    graph.add_edge(START, "parse_resume")
    graph.add_conditional_edges(
        "parse_resume",
        lambda s: END if s.get("error") else "retrieval",
    )
    graph.add_edge("retrieval",       "generate_report")
    graph.add_edge("generate_report", END)

    return graph.compile()
