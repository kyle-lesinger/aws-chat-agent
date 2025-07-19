"""Simplified AWS Agent using LangChain's built-in agent."""

from typing import List, Optional, Union, Dict, Any
from pathlib import Path
import yaml
import os
from dotenv import load_dotenv

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.tools import BaseTool

from ..tools import get_aws_tools
from ..credentials.manager import AWSCredentialManager

SYSTEM_PROMPT = """You are an AWS Agent specialized in helping users manage AWS services.

You have access to various AWS tools for services like S3, EC2, and Lambda. When a user asks you to perform AWS operations, use the appropriate tools.

For S3 operations:
- To list buckets: use list_s3_buckets
- To list files/objects in a bucket: use list_s3_objects with the bucket name

CRITICAL FORMATTING RULE FOR S3 LISTINGS:
When the list_s3_objects tool returns output, you MUST display it EXACTLY as provided, preserving all line breaks and formatting. The tool returns a pre-formatted text with:
- A header line showing the bucket path
- Directories shown as "[DIR] directoryname/"
- Files shown with their name, size, and date
- A summary line at the bottom

DO NOT reformat this output into bullet points or any other format. Simply introduce it with a phrase like "Here are the contents of bucket X:" and then show the exact output.

Other S3 operations:
- To download a single file: use download_from_s3
- To download multiple files or entire directories: use s3_file_transfer with recursive=true
- To upload files: use upload_to_s3 for single files, s3_file_transfer for multiple
- To transfer files/directories between S3 and local: use s3_file_transfer
- To delete objects: use delete_s3_object (automatically handles directories with or without trailing slash)
- To create a directory/folder in S3: use create_s3_directory (e.g., to create "test/" in bucket "my-bucket", use bucket="my-bucket" and directory_path="test/")

IMPORTANT S3 DIRECTORY CONCEPTS:
- S3 doesn't have real directories/folders - they are simulated using object keys with trailing slashes
- When creating a directory, the key must end with "/" (e.g., "test/")
- When deleting directories, the delete_s3_object tool will automatically try both with and without trailing slash
- When listing or navigating, directories appear as "[DIR]" entries

IMPORTANT: When users ask to download objects from a directory/prefix in S3 (like "save objects within bucket/path/"), use s3_file_transfer with:
- source: "s3://bucket/path/"
- destination: the local directory path
- recursive: true (to get all objects in the path)

Always be helpful and provide clear information about what you're doing. If an operation fails, explain the error clearly and suggest possible solutions.

Remember to use the correct AWS profile if the user specifies one."""


class SimpleAWSAgent:
    """Simplified AWS Agent using LangChain's agent framework."""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        tools: Optional[List[BaseTool]] = None,
        credential_manager: Optional[AWSCredentialManager] = None,
        profile: Optional[str] = None,
        config_path: Optional[Union[str, Path]] = None
    ):
        """Initialize the AWS Agent."""
        # Load environment variables
        load_dotenv()
        
        # Load config
        config_path = config_path or Path("aws_config.yml")
        config = {}
        if Path(config_path).exists():
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
        
        # Get agent config
        agent_config = config.get("agent", {})
        
        # Initialize LLM
        if not llm:
            api_key = agent_config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
            self.llm = ChatOpenAI(
                model=agent_config.get("model", "gpt-3.5-turbo"),
                temperature=agent_config.get("temperature", 0),
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
        
        # Get tools
        self.tools = tools or get_aws_tools(self.credential_manager)
        
        # Create prompt
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # Create agent
        agent = create_openai_tools_agent(self.llm, self.tools, self.prompt)
        
        # Create executor
        self.executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True
        )
        
        # Chat history
        self.chat_history = []
    
    def chat(self, message: str, profile: Optional[str] = None) -> str:
        """Send a message to the agent and get a response."""
        # Use specified profile or default
        current_profile = profile or self.profile
        
        # Add profile to context if specified
        if current_profile and current_profile != "default":
            message = f"[Using AWS profile: {current_profile}] {message}"
        
        try:
            # Run agent
            result = self.executor.invoke({
                "input": message,
                "chat_history": self.chat_history[-10:]  # Keep last 10 messages
            })
            
            # Update history
            self.chat_history.append(HumanMessage(content=message))
            self.chat_history.append(AIMessage(content=result["output"]))
            
            return result["output"]
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.chat_history.append(HumanMessage(content=message))
            self.chat_history.append(AIMessage(content=error_msg))
            return error_msg
    
    def clear_history(self):
        """Clear chat history."""
        self.chat_history = []
    
    async def achat(self, message: str, profile: Optional[str] = None) -> str:
        """Async version of chat."""
        # For now, just use sync version
        return self.chat(message, profile)