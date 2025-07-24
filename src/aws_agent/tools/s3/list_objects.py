"""Tool for listing objects in an S3 bucket."""

from typing import Any, Optional, Type
from pydantic.v1 import BaseModel, Field
import json
from datetime import datetime

from .base import S3BaseTool
from ...credentials.providers import MFARequiredException


class ListS3ObjectsInput(BaseModel):
    """Input for listing S3 objects."""
    bucket: str = Field(description="Name of the S3 bucket")
    prefix: Optional[str] = Field(
        default="",
        description="Prefix to filter objects (e.g., 'folder/')"
    )
    max_keys: Optional[int] = Field(
        default=100,
        description="Maximum number of objects to return"
    )
    delimiter: Optional[str] = Field(
        default="/",
        description="Delimiter to use for grouping objects (typically '/')"
    )
    profile: Optional[str] = Field(
        default=None,
        description="AWS profile to use"
    )


class ListS3ObjectsTool(S3BaseTool):
    """Tool for listing objects in an S3 bucket."""
    
    name: str = "list_s3_objects"
    description: str = "List objects in an S3 bucket with optional prefix filtering"
    args_schema: Type[BaseModel] = ListS3ObjectsInput
    
    def _format_size(self, size: int) -> str:
        """Format size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
    
    def _run(
        self,
        bucket: str,
        prefix: str = "",
        max_keys: int = 100,
        delimiter: str = "/",
        profile: Optional[str] = None
    ) -> str:
        """List objects in S3 bucket with formatted output."""
        try:
            # Validate and clean bucket name
            from .validators import validate_bucket_name, validate_object_key
            bucket = validate_bucket_name(bucket)
            prefix = validate_object_key(prefix) if prefix else ""
            
            s3_client = self._get_s3_client(profile)
            
            # List objects with delimiter to get both objects and "directories"
            params = {
                'Bucket': bucket,
                'MaxKeys': max_keys,
                'Delimiter': delimiter
            }
            if prefix:
                params['Prefix'] = prefix
            
            response = s3_client.list_objects_v2(**params)
            
            # Build the output
            lines = []
            lines.append(f"Contents of s3://{bucket}/{prefix}")
            lines.append("-" * 60)
            
            # First, list directories (CommonPrefixes)
            directories = response.get('CommonPrefixes', [])
            for dir_info in sorted(directories, key=lambda x: x['Prefix']):
                dir_name = dir_info['Prefix']
                # Remove the prefix from display if showing contents of a subdirectory
                if prefix and dir_name.startswith(prefix):
                    display_name = dir_name[len(prefix):]
                else:
                    display_name = dir_name
                lines.append(f"[DIR]  {display_name}")
            
            # Then list files
            objects = response.get('Contents', [])
            for obj in sorted(objects, key=lambda x: x['Key']):
                key = obj['Key']
                # Skip if this is just the prefix itself (happens with folders)
                if key == prefix:
                    continue
                
                # Remove the prefix from display if showing contents of a subdirectory
                if prefix and key.startswith(prefix):
                    display_name = key[len(prefix):]
                else:
                    display_name = key
                
                size = self._format_size(obj['Size'])
                last_modified = obj['LastModified'].strftime('%Y-%m-%d %H:%M')
                
                lines.append(f"{display_name:<50} {size:>10} {last_modified}")
            
            # Summary
            lines.append("-" * 60)
            total_objects = len(objects)
            total_dirs = len(directories)
            lines.append(f"Total: {total_dirs} directories, {total_objects} objects")
            
            if response.get('IsTruncated', False):
                lines.append(f"\nNote: List truncated at {max_keys} items.")
            
            # Return as plain text
            return "\n".join(lines)
            
        except MFARequiredException:
            # Re-raise MFA exception to be handled by the application
            raise
        except Exception as e:
            return self._handle_error(e, f"listing objects in bucket '{bucket}'")
    
    async def _arun(
        self,
        bucket: str,
        prefix: str = "",
        max_keys: int = 100,
        delimiter: str = "/",
        profile: Optional[str] = None
    ) -> str:
        """Async list objects in S3 bucket."""
        return self._run(bucket, prefix, max_keys, delimiter, profile)