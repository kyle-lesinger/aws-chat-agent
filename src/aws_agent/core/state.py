"""Agent state management for AWS operations."""

from typing import Any, Dict, List, Optional, TypedDict
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


class AgentState(TypedDict):
    """State for the AWS agent."""
    
    messages: List[BaseMessage]
    current_service: Optional[str]
    aws_profile: Optional[str]
    operation_history: List[Dict[str, Any]]
    context: Dict[str, Any]
    error: Optional[str]


class AWSOperation(BaseModel):
    """Represents an AWS operation."""
    
    service: str = Field(description="AWS service name (s3, ec2, lambda, etc.)")
    action: str = Field(description="Action to perform")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    profile: Optional[str] = Field(default=None, description="AWS profile to use")
    

class AWSOperationResult(BaseModel):
    """Result of an AWS operation."""
    
    success: bool
    service: str
    action: str
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)