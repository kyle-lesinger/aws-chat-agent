"""Base class for S3 tools."""

from abc import ABC
from typing import Optional
from langchain_core.tools import BaseTool
from pydantic import Field
import logging

from ...credentials.manager import AWSCredentialManager
from ...credentials.providers import MFARequiredException
from .client_pool import s3_client_pool
from .validators import validate_bucket_name, validate_object_key, validate_s3_path
from ..mfa_wrapper import MFAAwareTool, MFAStatus


logger = logging.getLogger(__name__)


class S3BaseTool(MFAAwareTool, ABC):
    """Base class for S3 tools."""
    
    credential_manager: AWSCredentialManager = Field(exclude=True)
    profile: Optional[str] = Field(
        default=None,
        description="AWS profile to use. If not specified, uses the default profile."
    )
    
    def _get_s3_client(self, profile: Optional[str] = None):
        """Get S3 client with proper credentials using connection pool."""
        profile = profile or self.profile
        logger.info(f"S3BaseTool._get_s3_client called with profile: {profile}, self.profile: {self.profile}")
        try:
            # Try to use the connection pool first
            return s3_client_pool.get_client(profile)
        except MFARequiredException:
            # Re-raise MFA exception to be handled by the application
            raise
        except Exception as e:
            # Fallback to creating a new client if pool fails
            logger.warning(f"Failed to get client from pool: {e}. Creating new client.")
            try:
                return self.credential_manager.create_client("s3", profile)
            except MFARequiredException:
                # Re-raise MFA exception to be handled by the application
                raise
    
    def _get_s3_resource(self, profile: Optional[str] = None):
        """Get S3 resource with proper credentials."""
        profile = profile or self.profile
        try:
            return self.credential_manager.create_resource("s3", profile)
        except MFARequiredException:
            # Re-raise MFA exception to be handled by the application
            raise
    
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