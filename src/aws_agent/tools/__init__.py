"""AWS tools for LangChain integration."""

from typing import List
from langchain_core.tools import BaseTool

from .s3 import get_s3_tools
from .ec2 import get_ec2_tools
from .lambda_tools import get_lambda_tools
from ..credentials.manager import AWSCredentialManager


def get_aws_tools(credential_manager: AWSCredentialManager) -> List[BaseTool]:
    """Get all available AWS tools.
    
    Args:
        credential_manager: AWS credential manager instance
        
    Returns:
        List of AWS tools for LangChain
    """
    tools = []
    
    # Add S3 tools
    tools.extend(get_s3_tools(credential_manager))
    
    # Add EC2 tools
    tools.extend(get_ec2_tools(credential_manager))
    
    # Add Lambda tools
    tools.extend(get_lambda_tools(credential_manager))
    
    return tools


__all__ = ["get_aws_tools", "get_s3_tools", "get_ec2_tools", "get_lambda_tools"]