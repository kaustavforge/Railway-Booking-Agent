"""
Agent graph nodes — agent_node and complaint_approval_node.
"""

import random

from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.types import interrupt

from app.config.settings import llm, SYSTEM_PROMPT
from app.tools import TOOLS
from app.agent.state import AgentState

# Bind tools to LLM
llm_with_tools = llm.bind_tools(TOOLS)


def agent_node(state: AgentState):
    system_message = SystemMessage(content=SYSTEM_PROMPT)
    messages = [system_message, *state["messages"]]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def complaint_approval_node(state: AgentState):
    last_message = state["messages"][-1]
    tool_call = last_message.tool_calls[0]
    category = tool_call["args"]["category"]
    description = tool_call["args"]["description"]

    decision = interrupt(
        {
            "type": "approval",
            "reason": "Agent wants to file a complaint on your behalf.",
            "category": category,
            "description": description,
            "instruction": "Approve this complaint? yes/no",
        }
    )

    if decision["approved"] == "no":
        result_text = "Complaint was not approved, so it was not filed."
    else:
        ticket_number = random.randint(10000, 99999)
        ticket_id = f"TCK-{ticket_number}"
        result_text = (
            f"Complaint filed successfully. Ticket ID: {ticket_id}. "
            f"Category: {category}. Description: {description}."
        )

    tool_message = ToolMessage(content=result_text, tool_call_id=tool_call["id"])
    return {"messages": [tool_message]}
