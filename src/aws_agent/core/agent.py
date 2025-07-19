"""Main AWS Agent implementation using LangChain and LangGraph."""

from typing import Any, Dict, List, Optional, Union
from langchain_core.language_models import BaseLLM
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
import logging
from pathlib import Path
import yaml
import os
from dotenv import load_dotenv

from .state import AgentState
from .graph import create_aws_graph
from ..tools import get_aws_tools
from ..credentials.manager import AWSCredentialManager


logger = logging.getLogger(__name__)


class AWSAgent:
    """Intelligent AWS Agent for natural language AWS operations."""
    
    def __init__(
        self,
        llm: Optional[BaseLLM] = None,
        tools: Optional[List[BaseTool]] = None,
        credential_manager: Optional[AWSCredentialManager] = None,
        profile: Optional[str] = None,
        config_path: Optional[Union[str, Path]] = None
    ):
        """Initialize the AWS Agent.
        
        Args:
            llm: Language model to use (defaults to GPT-4)
            tools: List of tools (defaults to all AWS tools)
            credential_manager: AWS credential manager
            profile: Default AWS profile to use
            config_path: Path to AWS config file
        """
        # Load environment variables from .env file if it exists
        load_dotenv()
        
        # Load config if not provided
        config_path = config_path or Path("aws_config.yml")
        config = {}
        if Path(config_path).exists():
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                logger.error(f"Invalid YAML in config file {config_path}: {e}")
                config = {}
            except Exception as e:
                logger.error(f"Error loading config file {config_path}: {e}")
                config = {}
        
        # Get agent config
        agent_config = config.get("agent", {})
        
        # Initialize LLM with API key from config or environment
        if not llm:
            api_key = agent_config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
            self.llm = ChatOpenAI(
                model=agent_config.get("model", "gpt-3.5-turbo"),
                temperature=agent_config.get("temperature", 0),
                streaming=True,
                api_key=api_key
            )
        else:
            self.llm = llm
        
        # Initialize credential manager
        self.credential_manager = credential_manager or AWSCredentialManager(
            config_path=config_path
        )
        
        # Set default profile
        self.profile = profile or self.credential_manager.get_default_profile()
        
        # Get tools with credential manager
        self.tools = tools or get_aws_tools(self.credential_manager)
        
        # Create the graph
        self.graph = create_aws_graph(self.tools, self.llm)
        
        # Initialize state
        self.state: AgentState = {
            "messages": [],
            "current_service": None,
            "aws_profile": self.profile,
            "operation_history": [],
            "context": {},
            "error": None
        }
        
        # Add system message
        self._add_system_message()
    
    def _add_system_message(self):
        """Add the system message to initialize the agent."""
        system_prompt = """You are an intelligent AWS Agent that helps users perform AWS operations using natural language.

You have access to various AWS services including S3, EC2, Lambda, and more. You can:
- List, create, and manage S3 buckets and objects
- Start, stop, and manage EC2 instances
- Deploy and invoke Lambda functions
- Transfer files between local system and AWS
- Switch between different AWS profiles

Always:
1. Confirm the AWS profile being used
2. Provide clear status updates
3. Handle errors gracefully
4. Ask for clarification when needed

Current AWS Profile: {profile}
""".format(profile=self.profile)
        
        self.state["messages"].append(SystemMessage(content=system_prompt))
    
    async def arun(self, message: str) -> str:
        """Run the agent asynchronously with a message."""
        # Add user message
        self.state["messages"].append(HumanMessage(content=message))
        
        # Run the graph
        result = await self.graph.ainvoke(self.state)
        
        # Update state
        self.state = result
        
        # Return the last AI message
        for msg in reversed(self.state["messages"]):
            if hasattr(msg, "__class__") and msg.__class__.__name__ == "AIMessage":
                return msg.content
        
        return "No response generated"
    
    def run(self, message: str) -> str:
        """Run the agent synchronously with a message."""
        # Add user message
        self.state["messages"].append(HumanMessage(content=message))
        
        # Run the graph
        result = self.graph.invoke(self.state)
        
        # Update state
        self.state = result
        
        # Return the last AI message
        for msg in reversed(self.state["messages"]):
            if hasattr(msg, "__class__") and msg.__class__.__name__ == "AIMessage":
                return msg.content
        
        return "No response generated"
    
    def set_profile(self, profile: str) -> None:
        """Switch to a different AWS profile."""
        if self.credential_manager.has_profile(profile):
            self.profile = profile
            self.state["aws_profile"] = profile
            logger.info(f"Switched to AWS profile: {profile}")
        else:
            raise ValueError(f"Profile '{profile}' not found")
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Get the operation history."""
        return self.state.get("operation_history", [])
    
    def clear_history(self) -> None:
        """Clear the conversation and operation history."""
        self.state["messages"] = []
        self.state["operation_history"] = []
        self.state["context"] = {}
        self.state["error"] = None
        self._add_system_message()
    
    def get_available_profiles(self) -> List[str]:
        """Get list of available AWS profiles."""
        return self.credential_manager.list_profiles()
    
    def get_current_profile(self) -> str:
        """Get the current AWS profile."""
        return self.profile