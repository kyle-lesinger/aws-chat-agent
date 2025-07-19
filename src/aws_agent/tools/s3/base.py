"""Base class for S3 tools."""

from abc import ABC
from typing import Optional
from langchain_core.tools import BaseTool
from pydantic import Field
import logging

from ...credentials.manager import AWSCredentialManager


logger = logging.getLogger(__name__)


class S3BaseTool(BaseTool, ABC):
    """Base class for S3 tools."""
    
    credential_manager: AWSCredentialManager = Field(exclude=True)
    profile: Optional[str] = Field(
        default=None,
        description="AWS profile to use. If not specified, uses the default profile."
    )
    
    def _get_s3_client(self, profile: Optional[str] = None):
        """Get S3 client with proper credentials."""
        profile = profile or self.profile
        return self.credential_manager.create_client("s3", profile)
    
    def _get_s3_resource(self, profile: Optional[str] = None):
        """Get S3 resource with proper credentials."""
        profile = profile or self.profile
        return self.credential_manager.create_resource("s3", profile)
    
    def _handle_error(self, e: Exception, operation: str) -> str:
        """Handle and format AWS errors."""
        error_msg = f"Error during {operation}: {str(e)}"
        logger.error(error_msg)
        
        # Add specific error handling for common S3 errors
        if hasattr(e, 'response'):
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'NoSuchBucket':
                return f"Bucket not found. {error_msg}"
            elif error_code == 'AccessDenied':
                return f"Access denied. Check your AWS credentials and permissions. {error_msg}"
            elif error_code == 'InvalidBucketName':
                return f"Invalid bucket name. {error_msg}"
        
        return error_msg