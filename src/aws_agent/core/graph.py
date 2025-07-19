"""LangGraph implementation for AWS Agent."""

from typing import Dict, List, Literal, TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool
import json

from .state import AgentState
from .nodes import (
    route_request,
    plan_operation,
    execute_tools,
    handle_error,
    format_response
)


def create_aws_graph(tools: List[BaseTool], llm) -> StateGraph:
    """Create the AWS agent graph with LangGraph."""
    
    # Create the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("route", route_request)
    workflow.add_node("plan", plan_operation)
    workflow.add_node("execute", execute_tools)
    workflow.add_node("error", handle_error)
    workflow.add_node("respond", format_response)
    
    # Add edges
    workflow.set_entry_point("route")
    
    # Routing logic
    workflow.add_conditional_edges(
        "route",
        lambda x: x.get("next", "plan"),
        {
            "plan": "plan",
            "error": "error",
            "respond": "respond"
        }
    )
    
    # Planning can lead to execution or error
    workflow.add_conditional_edges(
        "plan",
        lambda x: "execute" if not x.get("error") else "error",
        {
            "execute": "execute",
            "error": "error"
        }
    )
    
    # Execution can lead to response or error
    workflow.add_conditional_edges(
        "execute",
        lambda x: "respond" if not x.get("error") else "error",
        {
            "respond": "respond",
            "error": "error"
        }
    )
    
    # Error handling always leads to response
    workflow.add_edge("error", "respond")
    
    # Response is the end
    workflow.add_edge("respond", END)
    
    return workflow.compile()