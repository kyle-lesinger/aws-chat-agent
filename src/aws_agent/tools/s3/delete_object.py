"""Tool for deleting S3 objects."""

from typing import Any, Optional, Type
from langchain_core.pydantic_v1 import BaseModel, Field

from .base import S3BaseTool


class DeleteS3ObjectInput(BaseModel):
    """Input for deleting S3 object."""
    bucket: str = Field(description="S3 bucket name")
    key: str = Field(description="S3 object key to delete")
    profile: Optional[str] = Field(
        default=None,
        description="AWS profile to use"
    )


class DeleteS3ObjectTool(S3BaseTool):
    """Tool for deleting S3 objects."""
    
    name: str = "delete_s3_object"
    description: str = "Delete an object from S3"
    args_schema: Type[BaseModel] = DeleteS3ObjectInput
    
    def _run(
        self,
        bucket: str,
        key: str,
        profile: Optional[str] = None
    ) -> str:
        """Delete S3 object."""
        try:
            # Strip trailing slashes from bucket name
            bucket = bucket.rstrip('/')
            
            s3_client = self._get_s3_client(profile)
            
            # Check if object exists first
            try:
                s3_client.head_object(Bucket=bucket, Key=key)
                # Object exists, delete it
                s3_client.delete_object(Bucket=bucket, Key=key)
                return (
                    f"Successfully deleted s3://{bucket}/{key}\n"
                    f"Profile: {profile or self.profile or 'default'}"
                )
            except s3_client.exceptions.NoSuchKey:
                # Object not found, check if it might be a directory (missing trailing slash)
                if not key.endswith('/'):
                    try:
                        directory_key = key + '/'
                        s3_client.head_object(Bucket=bucket, Key=directory_key)
                        # Directory exists, delete it
                        s3_client.delete_object(Bucket=bucket, Key=directory_key)
                        return (
                            f"Successfully deleted directory s3://{bucket}/{directory_key}\n"
                            f"Profile: {profile or self.profile or 'default'}"
                        )
                    except s3_client.exceptions.NoSuchKey:
                        # Neither the exact key nor with trailing slash exists
                        return f"Object s3://{bucket}/{key} (or {key}/) does not exist"
                else:
                    # Key already ends with /, object truly doesn't exist
                    return f"Object s3://{bucket}/{key} does not exist"
            
        except Exception as e:
            return self._handle_error(e, f"deleting s3://{bucket}/{key}")
    
    async def _arun(
        self,
        bucket: str,
        key: str,
        profile: Optional[str] = None
    ) -> str:
        """Async delete S3 object."""
        return self._run(bucket, key, profile)