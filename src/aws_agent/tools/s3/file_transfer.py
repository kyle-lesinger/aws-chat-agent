"""Advanced file transfer tool for S3."""

from typing import Any, Optional, Type, List
from pathlib import Path
from pydantic.v1 import BaseModel, Field
import os
import fnmatch

from .base import S3BaseTool
from ...credentials.providers import MFARequiredException


class S3FileTransferInput(BaseModel):
    """Input for S3 file transfer operations."""
    source: str = Field(
        description="Source path (local path or s3://bucket/key)"
    )
    destination: str = Field(
        description="Destination path (local path or s3://bucket/key)"
    )
    recursive: bool = Field(
        default=False,
        description="Transfer directories recursively"
    )
    pattern: Optional[str] = Field(
        default=None,
        description="File pattern to match (e.g., '*.txt')"
    )
    profile: Optional[str] = Field(
        default=None,
        description="AWS profile to use"
    )


class S3FileTransferTool(S3BaseTool):
    """Tool for transferring files between local and S3."""
    
    name: str = "s3_file_transfer"
    description: str = (
        "Transfer files between local filesystem and S3. "
        "Supports both upload and download, single files and directories."
    )
    args_schema: Type[BaseModel] = S3FileTransferInput
    
    def _parse_s3_path(self, path: str) -> Optional[tuple[str, str]]:
        """Parse S3 path into bucket and key."""
        if not path.startswith("s3://"):
            return None
        
        path = path[5:]  # Remove 's3://'
        parts = path.split("/", 1)
        bucket = parts[0].rstrip('/')  # Strip trailing slashes from bucket name
        key = parts[1] if len(parts) > 1 else ""
        return bucket, key
    
    def _upload_file(self, local_path: Path, bucket: str, key: str, s3_client) -> dict:
        """Upload a single file to S3."""
        try:
            s3_client.upload_file(str(local_path), bucket, key)
            return {
                'status': 'success',
                'local_path': str(local_path),
                's3_path': f"s3://{bucket}/{key}",
                'size': local_path.stat().st_size
            }
        except Exception as e:
            return {
                'status': 'error',
                'local_path': str(local_path),
                's3_path': f"s3://{bucket}/{key}",
                'error': str(e)
            }
    
    def _download_file(self, bucket: str, key: str, local_path: Path, s3_client) -> dict:
        """Download a single file from S3."""
        try:
            # Ensure path is expanded
            expanded_path = local_path.expanduser()
            expanded_path.parent.mkdir(parents=True, exist_ok=True)
            s3_client.download_file(bucket, key, str(expanded_path))
            return {
                'status': 'success',
                's3_path': f"s3://{bucket}/{key}",
                'local_path': str(expanded_path),
                'size': expanded_path.stat().st_size
            }
        except Exception as e:
            return {
                'status': 'error',
                's3_path': f"s3://{bucket}/{key}",
                'local_path': str(local_path),
                'error': str(e)
            }
    
    def _list_local_files(self, path: Path, pattern: Optional[str], recursive: bool) -> List[Path]:
        """List local files matching pattern."""
        files = []
        
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            if recursive:
                for root, _, filenames in os.walk(path):
                    for filename in filenames:
                        if not pattern or fnmatch.fnmatch(filename, pattern):
                            files.append(Path(root) / filename)
            else:
                for item in path.iterdir():
                    if item.is_file():
                        if not pattern or fnmatch.fnmatch(item.name, pattern):
                            files.append(item)
        
        return files
    
    def _list_s3_objects(self, bucket: str, prefix: str, pattern: Optional[str], 
                        recursive: bool, s3_client) -> List[str]:
        """List S3 objects matching pattern."""
        objects = []
        
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
        
        for page in pages:
            for obj in page.get('Contents', []):
                key = obj['Key']
                
                # Skip if not recursive and object is in subdirectory
                if not recursive and prefix:
                    relative_key = key[len(prefix):].lstrip('/')
                    if '/' in relative_key:
                        continue
                
                # Check pattern
                if not pattern or fnmatch.fnmatch(os.path.basename(key), pattern):
                    objects.append(key)
        
        return objects
    
    def _run(
        self,
        source: str,
        destination: str,
        recursive: bool = False,
        pattern: Optional[str] = None,
        profile: Optional[str] = None
    ) -> str:
        """Transfer files between local and S3."""
        try:
            s3_client = self._get_s3_client(profile)
            
            source_s3 = self._parse_s3_path(source)
            dest_s3 = self._parse_s3_path(destination)
            
            results = []
            
            # Local to S3
            if not source_s3 and dest_s3:
                source_path = Path(source).expanduser()
                dest_bucket, dest_prefix = dest_s3
                
                if not source_path.exists():
                    return f"Error: Source path '{source}' does not exist"
                
                files = self._list_local_files(source_path, pattern, recursive)
                
                for file_path in files:
                    # Calculate S3 key
                    if source_path.is_file():
                        key = dest_prefix or file_path.name
                    else:
                        relative_path = file_path.relative_to(source_path)
                        key = f"{dest_prefix}/{relative_path}".strip('/')
                    
                    result = self._upload_file(file_path, dest_bucket, key, s3_client)
                    results.append(result)
            
            # S3 to Local
            elif source_s3 and not dest_s3:
                source_bucket, source_prefix = source_s3
                dest_path = Path(destination).expanduser()
                
                # Validate destination path
                if dest_path.exists() and dest_path.is_file() and recursive:
                    return f"Error: Cannot download multiple files to a single file path '{dest_path}'"
                
                # Create destination directory if it doesn't exist
                if not dest_path.exists():
                    try:
                        dest_path.mkdir(parents=True, exist_ok=True)
                    except Exception as e:
                        return f"Error: Cannot create destination directory '{dest_path}': {e}"
                
                objects = self._list_s3_objects(
                    source_bucket, source_prefix, pattern, recursive, s3_client
                )
                
                if not objects:
                    return f"No objects found in s3://{source_bucket}/{source_prefix} matching criteria"
                
                for obj_key in objects:
                    # Skip the prefix itself if it's returned as an object
                    if obj_key.rstrip('/') == source_prefix.rstrip('/'):
                        continue
                        
                    # Calculate local path
                    if source_prefix and obj_key.startswith(source_prefix):
                        relative_key = obj_key[len(source_prefix):].lstrip('/')
                    else:
                        relative_key = obj_key
                    
                    # Skip empty relative keys (happens when object key equals prefix)
                    if not relative_key:
                        continue
                    
                    # If downloading a single file to a directory, keep the filename
                    if dest_path.is_dir() or (not dest_path.exists() and destination.endswith('/')):
                        local_path = dest_path / Path(relative_key).name if not recursive else dest_path / relative_key
                    else:
                        # Single file to specific path
                        local_path = dest_path if len(objects) == 1 else dest_path / relative_key
                    result = self._download_file(
                        source_bucket, obj_key, local_path, s3_client
                    )
                    results.append(result)
            
            # S3 to S3
            elif source_s3 and dest_s3:
                source_bucket, source_prefix = source_s3
                dest_bucket, dest_prefix = dest_s3
                
                objects = self._list_s3_objects(
                    source_bucket, source_prefix, pattern, recursive, s3_client
                )
                
                for obj_key in objects:
                    # Calculate destination key
                    if source_prefix and obj_key.startswith(source_prefix):
                        relative_key = obj_key[len(source_prefix):].lstrip('/')
                    else:
                        relative_key = obj_key
                    
                    dest_key = f"{dest_prefix}/{relative_key}".strip('/')
                    
                    try:
                        s3_client.copy_object(
                            CopySource={'Bucket': source_bucket, 'Key': obj_key},
                            Bucket=dest_bucket,
                            Key=dest_key
                        )
                        results.append({
                            'status': 'success',
                            'source': f"s3://{source_bucket}/{obj_key}",
                            'destination': f"s3://{dest_bucket}/{dest_key}"
                        })
                    except Exception as e:
                        results.append({
                            'status': 'error',
                            'source': f"s3://{source_bucket}/{obj_key}",
                            'destination': f"s3://{dest_bucket}/{dest_key}",
                            'error': str(e)
                        })
            
            else:
                return "Error: Cannot transfer between local paths. Use regular file operations."
            
            # Format results
            success_count = sum(1 for r in results if r['status'] == 'success')
            error_count = sum(1 for r in results if r['status'] == 'error')
            
            if not results:
                return "No files were transferred."
            
            summary = f"Transfer completed: {success_count} successful"
            if error_count > 0:
                summary += f", {error_count} failed"
            summary += f"\nProfile: {profile or self.profile or 'default'}\n"
            
            # For S3 to local downloads, show destination directory
            if source_s3 and not dest_s3:
                summary += f"Downloaded to: {dest_path}\n"
            
            summary += "\nFiles transferred:\n"
            
            # Show successful transfers
            success_results = [r for r in results if r['status'] == 'success']
            if success_results:
                for result in success_results[:10]:  # Show first 10
                    if 'local_path' in result:
                        summary += f"✓ {Path(result['local_path']).name}\n"
                    else:
                        summary += f"✓ {result.get('source', result.get('s3_path', 'Unknown'))}\n"
                
                if len(success_results) > 10:
                    summary += f"... and {len(success_results) - 10} more files\n"
            
            # Show errors
            if error_count > 0:
                summary += "\nErrors:\n"
                for result in results:
                    if result['status'] == 'error':
                        summary += f"✗ {result.get('source', result.get('local_path', result.get('s3_path')))}: {result['error']}\n"
            
            return summary
            
        except MFARequiredException:

            
            # Re-raise MFA exception to be handled by the application

            
            raise

            
        except Exception as e:

            
            return self._handle_error(e, f"transferring files from '{source}' to '{destination}'")
    
    async def _arun(
        self,
        source: str,
        destination: str,
        recursive: bool = False,
        pattern: Optional[str] = None,
        profile: Optional[str] = None
    ) -> str:
        """Async transfer files between local and S3."""
        return self._run(source, destination, recursive, pattern, profile)