"""Tool for listing S3 buckets."""

from typing import Any, Optional, Type
from pydantic.v1 import BaseModel, Field
import json

from .base import S3BaseTool
from ...credentials.providers import MFARequiredException


class ListS3BucketsInput(BaseModel):
    """Input for listing S3 buckets."""
    profile: Optional[str] = Field(
        default=None,
        description="AWS profile to use. If not specified, uses the default profile."
    )


class ListS3BucketsTool(S3BaseTool):
    """Tool for listing S3 buckets."""
    
    name: str = "list_s3_buckets"
    description: str = "List all S3 buckets in the AWS account"
    args_schema: Type[BaseModel] = ListS3BucketsInput
    
    def _run(self, profile: Optional[str] = None) -> str:
        """List S3 buckets."""
        try:
            s3_client = self._get_s3_client(profile)
            response = s3_client.list_buckets()
            
            buckets = []
            for bucket in response.get('Buckets', []):
                buckets.append({
                    'name': bucket['Name'],
                    'creation_date': bucket['CreationDate'].isoformat()
                })
            
            result = {
                'buckets': buckets,
                'count': len(buckets),
                'profile': profile or self.profile or 'default'
            }
            
            return json.dumps(result, indent=2)
            
        except MFARequiredException:
            # Re-raise MFA exception to be handled by the application
            raise
        except Exception as e:
            return self._handle_error(e, "listing S3 buckets")
    
    async def _arun(self, profile: Optional[str] = None) -> str:
        """Async list S3 buckets."""
        # For now, use sync version
        return self._run(profile)