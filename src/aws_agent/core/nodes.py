"""Graph nodes for AWS Agent operations."""

from typing import Any, Dict, List
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool
import json
import traceback

from .state import AgentState, AWSOperation, AWSOperationResult


def route_request(state: AgentState) -> Dict[str, Any]:
    """Route the request to appropriate handler."""
    messages = state["messages"]
    if not messages:
        return {"error": "No messages provided", "next": "error"}
    
    last_message = messages[-1]
    
    # Simple routing logic - can be enhanced with LLM-based routing
    if "error" in state and state["error"]:
        return {"next": "error"}
    
    # Check if this is a chat message or a specific operation
    if hasattr(last_message, 'content'):
        content = last_message.content.lower()
        
        # Direct to planning for AWS operations
        if any(svc in content for svc in ["s3", "ec2", "lambda", "bucket", "instance", "function"]):
            return {"next": "plan"}
        
        # For general queries, might need just a response
        if any(word in content for word in ["what", "how", "list", "show", "help"]):
            return {"next": "plan"}
    
    return {"next": "plan"}


def plan_operation(state: AgentState) -> Dict[str, Any]:
    """Plan the AWS operation based on user request."""
    messages = state["messages"]
    last_message = messages[-1]
    
    try:
        # Extract operation details from the message
        # In a real implementation, this would use an LLM to parse the intent
        content = last_message.content.lower() if hasattr(last_message, 'content') else ""
        
        # Simple parsing logic - would be replaced with LLM-based parsing
        operation = None
        if "s3" in content or "bucket" in content:
            if "list" in content:
                operation = AWSOperation(service="s3", action="list_buckets")
            elif "upload" in content:
                operation = AWSOperation(service="s3", action="upload_file")
            elif "download" in content:
                operation = AWSOperation(service="s3", action="download_file")
        elif "ec2" in content or "instance" in content:
            if "list" in content:
                operation = AWSOperation(service="ec2", action="list_instances")
            elif "start" in content:
                operation = AWSOperation(service="ec2", action="start_instance")
            elif "stop" in content:
                operation = AWSOperation(service="ec2", action="stop_instance")
        
        if operation:
            return {
                "context": {
                    **state.get("context", {}),
                    "planned_operation": operation.model_dump()
                }
            }
        else:
            return {"error": "Could not understand the requested operation"}
            
    except Exception as e:
        return {"error": f"Planning failed: {str(e)}"}


def execute_tools(state: AgentState) -> Dict[str, Any]:
    """Execute the planned AWS operation using tools."""
    context = state.get("context", {})
    planned_op = context.get("planned_operation")
    
    if not planned_op:
        return {"error": "No operation planned"}
    
    try:
        # Create tool invocation
        tool_name = f"{planned_op['service']}_{planned_op['action']}"
        tool_input = planned_op.get("parameters", {})
        
        # Add profile if specified
        if state.get("aws_profile"):
            tool_input["profile"] = state["aws_profile"]
        
        # This would execute the actual tool
        # For now, we'll simulate a response
        result = AWSOperationResult(
            success=True,
            service=planned_op["service"],
            action=planned_op["action"],
            result={"message": f"Successfully executed {tool_name}"},
            metadata={"profile": state.get("aws_profile", "default")}
        )
        
        # Update operation history
        history = state.get("operation_history", [])
        history.append(result.model_dump())
        
        return {
            "operation_history": history,
            "context": {
                **context,
                "last_result": result.model_dump()
            }
        }
        
    except Exception as e:
        return {"error": f"Execution failed: {str(e)}"}


def handle_error(state: AgentState) -> Dict[str, Any]:
    """Handle errors and prepare error response."""
    error = state.get("error", "Unknown error occurred")
    
    # Log error for debugging
    context = state.get("context", {})
    context["error_handled"] = True
    context["error_message"] = error
    
    return {
        "context": context,
        "error": None  # Clear error after handling
    }


def format_response(state: AgentState) -> Dict[str, Any]:
    """Format the final response to the user."""
    context = state.get("context", {})
    messages = state["messages"]
    
    # Check if there was an error
    if context.get("error_handled"):
        response = f"I encountered an error: {context.get('error_message', 'Unknown error')}"
    elif "last_result" in context:
        result = context["last_result"]
        if result["success"]:
            response = f"Successfully completed {result['service']} {result['action']}"
            if result.get("result"):
                response += f"\n{json.dumps(result['result'], indent=2)}"
        else:
            response = f"Operation failed: {result.get('error', 'Unknown error')}"
    else:
        response = "I'm ready to help with AWS operations. What would you like to do?"
    
    # Add response message
    messages.append(AIMessage(content=response))
    
    return {"messages": messages}