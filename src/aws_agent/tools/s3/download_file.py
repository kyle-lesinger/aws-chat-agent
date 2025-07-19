"""Tool for downloading files from S3."""

from typing import Any, Optional, Type
from pathlib import Path
from langchain_core.pydantic_v1 import BaseModel, Field

from .base import S3BaseTool


class DownloadFromS3Input(BaseModel):
    """Input for downloading file from S3."""
    bucket: str = Field(description="S3 bucket name")
    key: str = Field(description="S3 object key")
    local_path: str = Field(description="Local path to save the file")
    profile: Optional[str] = Field(
        default=None,
        description="AWS profile to use"
    )


class DownloadFromS3Tool(S3BaseTool):
    """Tool for downloading files from S3."""
    
    name: str = "download_from_s3"
    description: str = "Download a file from S3 to local filesystem"
    args_schema: Type[BaseModel] = DownloadFromS3Input
    
    def _run(
        self,
        bucket: str,
        key: str,
        local_path: str,
        profile: Optional[str] = None
    ) -> str:
        """Download file from S3."""
        try:
            # Strip trailing slashes from bucket name
            bucket = bucket.rstrip('/')
            
            # Expand user home directory (~)
            local_file = Path(local_path).expanduser()
            
            # Create parent directory if it doesn't exist
            local_file.parent.mkdir(parents=True, exist_ok=True)
            
            s3_client = self._get_s3_client(profile)
            
            # Get object metadata first
            response = s3_client.head_object(Bucket=bucket, Key=key)
            file_size = response['ContentLength']
            content_type = response.get('ContentType', 'binary/octet-stream')
            
            # Download file
            s3_client.download_file(bucket, key, str(local_file))
            
            return (
                f"Successfully downloaded s3://{bucket}/{key} to '{local_file}'\n"
                f"File size: {file_size:,} bytes\n"
                f"Content type: {content_type}\n"
                f"Profile: {profile or self.profile or 'default'}"
            )
            
        except Exception as e:
            return self._handle_error(e, f"downloading s3://{bucket}/{key}")
    
    async def _arun(
        self,
        bucket: str,
        key: str,
        local_path: str,
        profile: Optional[str] = None
    ) -> str:
        """Async download file from S3."""
        return self._run(bucket, key, local_path, profile)