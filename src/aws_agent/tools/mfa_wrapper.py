"""MFA wrapper for tools to handle authentication requirements."""

import json
import uuid
from typing import Any, Dict, Optional, Callable
from functools import wraps
import logging

from langchain_core.tools import BaseTool
from ..credentials.providers import MFARequiredException

logger = logging.getLogger(__name__)

# Special marker for MFA required responses
MFA_MARKER = "###MFA_REQUIRED###"


class MFAStatus:
    """MFA status response that tools can return."""
    
    @staticmethod
    def create_mfa_response(profile: str, mfa_device: str, message: str = None) -> str:
        """Create an MFA required response that can be detected by the agent."""
        request_id = str(uuid.uuid4())
        mfa_data = {
            "status": "mfa_required",
            "profile": profile,
            "mfa_device": mfa_device,
            "request_id": request_id,
            "message": message or f"MFA authentication required for profile '{profile}'"
        }
        # Return a specially formatted string that includes our marker
        return f"{MFA_MARKER}{json.dumps(mfa_data)}{MFA_MARKER}"
    
    @staticmethod
    def is_mfa_response(response: str) -> bool:
        """Check if a response is an MFA status response."""
        return isinstance(response, str) and MFA_MARKER in response
    
    @staticmethod
    def parse_mfa_response(response: str) -> Optional[Dict[str, Any]]:
        """Parse MFA data from a response."""
        if not MFAStatus.is_mfa_response(response):
            return None
        
        try:
            # Extract JSON between markers
            start = response.find(MFA_MARKER) + len(MFA_MARKER)
            end = response.rfind(MFA_MARKER)
            if start < end:
                json_str = response[start:end]
                return json.loads(json_str)
        except Exception as e:
            logger.error(f"Failed to parse MFA response: {e}")
        
        return None


def mfa_aware_tool(original_run_method):
    """Decorator to make tool MFA-aware by catching MFARequiredException."""
    
    @wraps(original_run_method)
    def wrapper(self, *args, **kwargs):
        try:
            # Call the original _run method
            return original_run_method(self, *args, **kwargs)
        except MFARequiredException as e:
            logger.info(f"MFA required for tool {self.name}: {e}")
            # Convert exception to MFA status response
            return MFAStatus.create_mfa_response(
                profile=e.profile,
                mfa_device=e.mfa_device,
                message=str(e)
            )
        except Exception as e:
            # Let other exceptions pass through
            raise
    
    return wrapper


class MFAAwareTool(BaseTool):
    """Base class for MFA-aware tools."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store original _run method
        if hasattr(self, '_run'):
            self._original_run = self._run
            # Override _run with our wrapper
            self._run = self._wrapped_run
    
    def _wrapped_run(self, *args, **kwargs):
        """Wrapped run method that handles MFA."""
        try:
            # Call the original _run method
            return self._original_run(*args, **kwargs)
        except MFARequiredException as e:
            logger.info(f"MFA required for tool {self.name}: {e}")
            # Convert exception to MFA status response
            return MFAStatus.create_mfa_response(
                profile=e.profile,
                mfa_device=e.mfa_device,
                message=str(e)
            )
    
    def check_mfa_requirement(self, profile: str) -> Optional[Dict[str, Any]]:
        """Check if MFA is required for a profile before executing."""
        # This can be implemented by subclasses to pre-check MFA requirements
        return None


def wrap_tool_with_mfa(tool: BaseTool) -> BaseTool:
    """Wrap an existing tool to make it MFA-aware."""
    # Wrap the _run method if it exists
    if hasattr(tool, '_run'):
        original_run = tool._run
        tool._run = mfa_aware_tool(original_run)
    
    # Also wrap the run method to ensure we catch at all levels
    original_invoke = tool.invoke
    
    def mfa_aware_invoke(*args, **kwargs):
        try:
            result = original_invoke(*args, **kwargs)
            return result
        except MFARequiredException as e:
            logger.info(f"MFA required in tool.invoke for {tool.name}: {e}")
            return MFAStatus.create_mfa_response(
                profile=e.profile,
                mfa_device=e.mfa_device,
                message=str(e)
            )
    
    tool.invoke = mfa_aware_invoke
    
    return tool