"""Tool for creating directories (folders) in S3."""

from typing import Any, Optional, Type
from pydantic.v1 import BaseModel, Field

from .base import S3BaseTool
from ...credentials.providers import MFARequiredException


class CreateS3DirectoryInput(BaseModel):
    """Input for creating directory in S3."""
    bucket: str = Field(description="S3 bucket name")
    directory_path: str = Field(
        description="Directory path to create (e.g., 'folder/' or 'path/to/folder/')"
    )
    profile: Optional[str] = Field(
        default=None,
        description="AWS profile to use"
    )


class CreateS3DirectoryTool(S3BaseTool):
    """Tool for creating directories in S3."""
    
    name: str = "create_s3_directory"
    description: str = (
        "Create a directory (folder) in an S3 bucket. "
        "S3 uses prefixes, so this creates an empty object with a trailing slash."
    )
    args_schema: Type[BaseModel] = CreateS3DirectoryInput
    
    def _run(
        self,
        bucket: str,
        directory_path: str,
        profile: Optional[str] = None
    ) -> str:
        """Create directory in S3."""
        try:
            # Strip trailing slashes from bucket name
            bucket = bucket.rstrip('/')
            
            # Ensure directory path ends with /
            if not directory_path.endswith('/'):
                directory_path += '/'
            
            s3_client = self._get_s3_client(profile)
            
            # Create an empty object with the directory path
            s3_client.put_object(
                Bucket=bucket,
                Key=directory_path,
                Body=b''  # Empty content
            )
            
            return (
                f"Successfully created directory '{directory_path}' in bucket '{bucket}'\n"
                f"Note: S3 uses prefixes, so this created an empty object to represent the folder.\n"
                f"Profile: {profile or self.profile or 'default'}"
            )
            
        except MFARequiredException:

            
            # Re-raise MFA exception to be handled by the application

            
            raise

            
        except Exception as e:

            
            return self._handle_error(e, f"creating directory '{directory_path}' in bucket '{bucket}'")
    
    async def _arun(
        self,
        bucket: str,
        directory_path: str,
        profile: Optional[str] = None
    ) -> str:
        """Async create directory in S3."""
        return self._run(bucket, directory_path, profile)