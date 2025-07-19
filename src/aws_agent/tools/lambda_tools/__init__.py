"""Lambda tools for LangChain."""

from typing import List
from langchain_core.tools import BaseTool
from ...credentials.manager import AWSCredentialManager


def get_lambda_tools(credential_manager: AWSCredentialManager) -> List[BaseTool]:
    """Get all Lambda tools.
    
    Args:
        credential_manager: AWS credential manager
        
    Returns:
        List of Lambda tools
    """
    # TODO: Implement Lambda tools
    return []


__all__ = ["get_lambda_tools"]