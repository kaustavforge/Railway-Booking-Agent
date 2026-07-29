"""
LangGraph StateGraph compilation.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from app.tools import TOOLS
from app.agent.state import AgentState
from app.agent.nodes import agent_node, complaint_approval_node
from app.database.connection import checkpointer


def route_after_agent(state: AgentState):
    last_message = state["messages"][-1]
    tool_calls = last_message.tool_calls

    if not tool_calls:
        return END
    if tool_calls[0]["name"] == "file_complaint":
        return "complaint_approval"
    return "tools"


graph_builder = StateGraph(AgentState)
graph_builder.add_node("agent", agent_node)
graph_builder.add_node("tools", ToolNode(TOOLS))
graph_builder.add_node("complaint_approval", complaint_approval_node)

graph_builder.add_edge(START, "agent")
graph_builder.add_conditional_edges(
    "agent",
    route_after_agent,
    {"tools": "tools", "complaint_approval": "complaint_approval", END: END},
)
graph_builder.add_edge("tools", "agent")
graph_builder.add_edge("complaint_approval", "agent")

graph = graph_builder.compile(checkpointer=checkpointer)


def retrieve_all_threads():
    all_threads = set()
    for checkpoint in checkpointer.list(None):
        all_threads.add(checkpoint.config["configurable"]["thread_id"])  # type: ignore[typeddict-item]
    return list(all_threads)
