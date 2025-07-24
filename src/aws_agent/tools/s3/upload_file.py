"""Tool for uploading files to S3."""

from typing import Any, Optional, Type
from pathlib import Path
from pydantic.v1 import BaseModel, Field
import mimetypes

from .base import S3BaseTool
from .progress import ProgressPercentage, format_bytes
from .validators import validate_bucket_name, validate_object_key
from ...credentials.providers import MFARequiredException


class UploadToS3Input(BaseModel):
    """Input for uploading file to S3."""
    local_path: str = Field(description="Local file path to upload")
    bucket: str = Field(description="S3 bucket name")
    key: str = Field(description="S3 object key (path in bucket)")
    profile: Optional[str] = Field(
        default=None,
        description="AWS profile to use"
    )


class UploadToS3Tool(S3BaseTool):
    """Tool for uploading files to S3."""
    
    name: str = "upload_to_s3"
    description: str = "Upload a file from local filesystem to S3"
    args_schema: Type[BaseModel] = UploadToS3Input
    
    def _run(
        self,
        local_path: str,
        bucket: str,
        key: str,
        profile: Optional[str] = None
    ) -> str:
        """Upload file to S3."""
        try:
            # Validate inputs
            bucket = validate_bucket_name(bucket)
            key = validate_object_key(key)
            
            local_file = Path(local_path).expanduser()
            
            # Validate local file exists
            if not local_file.exists():
                return f"Error: Local file '{local_path}' does not exist"
            
            if not local_file.is_file():
                return f"Error: '{local_path}' is not a file"
            
            s3_client = self._get_s3_client(profile)
            
            # Get file size
            file_size = local_file.stat().st_size
            
            # Determine content type
            content_type, _ = mimetypes.guess_type(str(local_file))
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            # Create progress callback
            progress_callback = None
            if file_size > 1024 * 1024:  # Show progress for files > 1MB
                progress_callback = ProgressPercentage(str(local_file.name), file_size)
            
            # Upload file with progress
            s3_client.upload_file(
                str(local_file),
                bucket,
                key,
                ExtraArgs=extra_args,
                Callback=progress_callback
            )
            
            return (
                f"Successfully uploaded '{local_path}' to s3://{bucket}/{key}\n"
                f"File size: {format_bytes(file_size)}\n"
                f"Content type: {content_type or 'binary/octet-stream'}\n"
                f"Profile: {profile or self.profile or 'default'}"
            )
            
        except MFARequiredException:
            # Re-raise MFA exception to be handled by the application
            raise
        except Exception as e:
            return self._handle_error(e, f"uploading '{local_path}' to s3://{bucket}/{key}")
    
    async def _arun(
        self,
        local_path: str,
        bucket: str,
        key: str,
        profile: Optional[str] = None
    ) -> str:
        """Async upload file to S3."""
        return self._run(local_path, bucket, key, profile)