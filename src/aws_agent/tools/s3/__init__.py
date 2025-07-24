"""S3 tools for LangChain."""

from typing import List
from langchain_core.tools import BaseTool

from .list_buckets import ListS3BucketsTool
from .list_objects import ListS3ObjectsTool
from .upload_file import UploadToS3Tool
from .download_file import DownloadFromS3Tool
from .create_bucket import CreateS3BucketTool
from .delete_object import DeleteS3ObjectTool
from .file_transfer import S3FileTransferTool
from .create_directory import CreateS3DirectoryTool
from ...credentials.manager import AWSCredentialManager
from .client_pool import s3_client_pool


def get_s3_tools(credential_manager: AWSCredentialManager) -> List[BaseTool]:
    """Get all S3 tools.
    
    Args:
        credential_manager: AWS credential manager
        
    Returns:
        List of S3 tools
    """
    # Set credential manager on the client pool
    s3_client_pool.set_credential_manager(credential_manager)
    
    return [
        ListS3BucketsTool(credential_manager=credential_manager),
        ListS3ObjectsTool(credential_manager=credential_manager),
        UploadToS3Tool(credential_manager=credential_manager),
        DownloadFromS3Tool(credential_manager=credential_manager),
        CreateS3BucketTool(credential_manager=credential_manager),
        DeleteS3ObjectTool(credential_manager=credential_manager),
        S3FileTransferTool(credential_manager=credential_manager),
        CreateS3DirectoryTool(credential_manager=credential_manager),
    ]


__all__ = [
    "get_s3_tools",
    "ListS3BucketsTool",
    "ListS3ObjectsTool", 
    "UploadToS3Tool",
    "DownloadFromS3Tool",
    "CreateS3BucketTool",
    "DeleteS3ObjectTool",
    "S3FileTransferTool",
    "CreateS3DirectoryTool"
]