"""Input validation for S3 operations."""

import re
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class S3ValidationError(ValueError):
    """Custom exception for S3 validation errors."""
    pass


def validate_bucket_name(bucket: str) -> str:
    """Validate S3 bucket name according to AWS rules.
    
    Args:
        bucket: Bucket name to validate
        
    Returns:
        Cleaned bucket name
        
    Raises:
        S3ValidationError: If bucket name is invalid
    """
    # Strip trailing slashes
    bucket = bucket.rstrip('/')
    
    # Check length
    if len(bucket) < 3 or len(bucket) > 63:
        raise S3ValidationError(f"Bucket name must be between 3 and 63 characters: '{bucket}'")
    
    # Check valid characters and format
    if not re.match(r'^[a-z0-9][a-z0-9.-]*[a-z0-9]$', bucket):
        raise S3ValidationError(
            f"Bucket name must start and end with lowercase letter or number, "
            f"and contain only lowercase letters, numbers, hyphens, and dots: '{bucket}'"
        )
    
    # Check for consecutive dots or hyphens
    if '..' in bucket or '--' in bucket or '.-' in bucket or '-.' in bucket:
        raise S3ValidationError(
            f"Bucket name cannot contain consecutive dots or hyphens: '{bucket}'"
        )
    
    # Check IP address format
    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', bucket):
        raise S3ValidationError(f"Bucket name cannot be formatted as an IP address: '{bucket}'")
    
    return bucket


def validate_object_key(key: Optional[str]) -> Optional[str]:
    """Validate S3 object key for security.
    
    Args:
        key: Object key to validate
        
    Returns:
        Validated key
        
    Raises:
        S3ValidationError: If key contains path traversal attempts
    """
    if not key:
        return key
    
    # Check for path traversal attempts
    if '..' in key:
        raise S3ValidationError(f"Object key cannot contain path traversal (..): '{key}'")
    
    # Check for null bytes
    if '\x00' in key:
        raise S3ValidationError(f"Object key cannot contain null bytes: '{key}'")
    
    # Warn about keys starting with /
    if key.startswith('/'):
        logger.warning(f"Object key starts with '/', this might cause issues: '{key}'")
    
    return key


def validate_s3_path(bucket: str, key: Optional[str] = None) -> tuple[str, Optional[str]]:
    """Validate complete S3 path (bucket and key).
    
    Args:
        bucket: Bucket name
        key: Object key (optional)
        
    Returns:
        Tuple of (validated_bucket, validated_key)
        
    Raises:
        S3ValidationError: If validation fails
    """
    validated_bucket = validate_bucket_name(bucket)
    validated_key = validate_object_key(key) if key else None
    
    return validated_bucket, validated_key


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """Parse S3 URI into bucket and key.
    
    Args:
        uri: S3 URI (e.g., s3://bucket/path/to/object)
        
    Returns:
        Tuple of (bucket, key)
        
    Raises:
        S3ValidationError: If URI is invalid
    """
    if not uri.startswith('s3://'):
        raise S3ValidationError(f"Invalid S3 URI, must start with 's3://': '{uri}'")
    
    # Remove s3:// prefix
    path = uri[5:]
    
    # Split bucket and key
    parts = path.split('/', 1)
    if not parts[0]:
        raise S3ValidationError(f"Invalid S3 URI, no bucket specified: '{uri}'")
    
    bucket = parts[0]
    key = parts[1] if len(parts) > 1 else ''
    
    # Validate components
    validated_bucket, validated_key = validate_s3_path(bucket, key)
    
    return validated_bucket, validated_key or ''