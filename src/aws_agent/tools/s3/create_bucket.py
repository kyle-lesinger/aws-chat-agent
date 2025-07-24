"""Tool for creating S3 buckets."""

from typing import Any, Optional, Type
from pydantic.v1 import BaseModel, Field

from .base import S3BaseTool
from ...credentials.providers import MFARequiredException


class CreateS3BucketInput(BaseModel):
    """Input for creating S3 bucket."""
    bucket_name: str = Field(description="Name of the bucket to create")
    region: Optional[str] = Field(
        default=None,
        description="AWS region for the bucket (defaults to profile region)"
    )
    profile: Optional[str] = Field(
        default=None,
        description="AWS profile to use"
    )


class CreateS3BucketTool(S3BaseTool):
    """Tool for creating S3 buckets."""
    
    name: str = "create_s3_bucket"
    description: str = "Create a new S3 bucket"
    args_schema: Type[BaseModel] = CreateS3BucketInput
    
    def _run(
        self,
        bucket_name: str,
        region: Optional[str] = None,
        profile: Optional[str] = None
    ) -> str:
        """Create S3 bucket."""
        try:
            # Strip trailing slashes from bucket name
            bucket_name = bucket_name.rstrip('/')
            
            s3_client = self._get_s3_client(profile)
            
            # Get region from client if not specified
            if not region:
                session = self.credential_manager.create_session(profile)
                region = session.region_name or 'us-east-1'
            
            # Create bucket with proper configuration
            if region == 'us-east-1':
                # us-east-1 doesn't accept LocationConstraint
                s3_client.create_bucket(Bucket=bucket_name)
            else:
                s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': region}
                )
            
            # Enable versioning by default
            s3_client.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={'Status': 'Enabled'}
            )
            
            return (
                f"Successfully created bucket '{bucket_name}' in region '{region}'\n"
                f"Versioning: Enabled\n"
                f"Profile: {profile or self.profile or 'default'}"
            )
            
        except MFARequiredException:

            
            # Re-raise MFA exception to be handled by the application

            
            raise

            
        except Exception as e:

            
            return self._handle_error(e, f"creating bucket '{bucket_name}'")
    
    async def _arun(
        self,
        bucket_name: str,
        region: Optional[str] = None,
        profile: Optional[str] = None
    ) -> str:
        """Async create S3 bucket."""
        return self._run(bucket_name, region, profile)