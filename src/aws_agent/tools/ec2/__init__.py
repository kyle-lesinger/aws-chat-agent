"""EC2 tools for LangChain."""

from typing import List
from langchain_core.tools import BaseTool
from ...credentials.manager import AWSCredentialManager


def get_ec2_tools(credential_manager: AWSCredentialManager) -> List[BaseTool]:
    """Get all EC2 tools.
    
    Args:
        credential_manager: AWS credential manager
        
    Returns:
        List of EC2 tools
    """
    # TODO: Implement EC2 tools
    return []


__all__ = ["get_ec2_tools"]