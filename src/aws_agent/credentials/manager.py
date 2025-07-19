"""AWS Credential Manager with multiple provider support."""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union
import boto3
from botocore.credentials import Credentials
from botocore.session import Session

from .providers import (
    AWSCredentials,
    CredentialProvider,
    EnvironmentProvider,
    ProfileProvider,
    ConfigFileProvider,
    KeyringProvider,
    IAMRoleProvider
)


logger = logging.getLogger(__name__)


class AWSCredentialManager:
    """Manages AWS credentials from multiple sources."""
    
    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
        providers: Optional[List[CredentialProvider]] = None
    ):
        """Initialize credential manager.
        
        Args:
            config_path: Path to custom config file
            providers: List of credential providers (defaults to all)
        """
        self.config_path = Path(config_path) if config_path else Path("aws_config.yml")
        
        # Initialize providers in order of precedence
        self.providers = providers or [
            EnvironmentProvider(),
            ProfileProvider(),
            ConfigFileProvider(self.config_path),
            KeyringProvider(),
            IAMRoleProvider()
        ]
        
        # Cache for credentials
        self._credentials_cache: Dict[str, AWSCredentials] = {}
        
        # Default profile
        self._default_profile = None
    
    def get_credentials(self, profile: Optional[str] = None) -> Optional[AWSCredentials]:
        """Get AWS credentials for the specified profile.
        
        Args:
            profile: AWS profile name (uses default if not specified)
            
        Returns:
            AWS credentials or None if not found
        """
        profile = profile or self._default_profile or "default"
        
        # Check cache first
        if profile in self._credentials_cache:
            return self._credentials_cache[profile]
        
        # Try each provider in order
        for provider in self.providers:
            if not provider.is_available():
                continue
            
            try:
                credentials = provider.get_credentials(profile)
                if credentials:
                    logger.info(f"Got credentials for profile '{profile}' from {provider.__class__.__name__}")
                    self._credentials_cache[profile] = credentials
                    return credentials
            except Exception as e:
                logger.warning(f"Failed to get credentials from {provider.__class__.__name__}: {e}")
        
        logger.error(f"No credentials found for profile '{profile}'")
        return None
    
    def create_session(self, profile: Optional[str] = None) -> boto3.Session:
        """Create a boto3 session with credentials.
        
        Args:
            profile: AWS profile to use
            
        Returns:
            Configured boto3 session
        """
        credentials = self.get_credentials(profile)
        if not credentials:
            raise ValueError(f"No credentials found for profile '{profile or 'default'}'")
        
        session_params = {
            "aws_access_key_id": credentials.access_key_id,
            "aws_secret_access_key": credentials.secret_access_key,
        }
        
        if credentials.session_token:
            session_params["aws_session_token"] = credentials.session_token
        
        if credentials.region:
            session_params["region_name"] = credentials.region
        
        return boto3.Session(**session_params)
    
    def create_client(self, service: str, profile: Optional[str] = None, **kwargs):
        """Create an AWS service client.
        
        Args:
            service: AWS service name (e.g., 's3', 'ec2')
            profile: AWS profile to use
            **kwargs: Additional client parameters
            
        Returns:
            Boto3 service client
        """
        session = self.create_session(profile)
        return session.client(service, **kwargs)
    
    def create_resource(self, service: str, profile: Optional[str] = None, **kwargs):
        """Create an AWS service resource.
        
        Args:
            service: AWS service name (e.g., 's3', 'ec2')
            profile: AWS profile to use
            **kwargs: Additional resource parameters
            
        Returns:
            Boto3 service resource
        """
        session = self.create_session(profile)
        return session.resource(service, **kwargs)
    
    def list_profiles(self) -> List[str]:
        """List all available AWS profiles."""
        profiles = set()
        
        # Check each provider for available profiles
        for provider in self.providers:
            if isinstance(provider, ProfileProvider) and provider.is_available():
                profiles.update(provider.list_profiles())
            elif isinstance(provider, ConfigFileProvider) and provider.is_available():
                # Parse config file for profiles
                try:
                    import yaml
                    with open(provider.config_path, 'r') as f:
                        config = yaml.safe_load(f)
                        if config and "profiles" in config:
                            profiles.update(config["profiles"].keys())
                except Exception:
                    pass
        
        # Add default if we have any credentials
        if self.get_credentials("default"):
            profiles.add("default")
        
        return sorted(list(profiles))
    
    def has_profile(self, profile: str) -> bool:
        """Check if a profile exists."""
        return self.get_credentials(profile) is not None
    
    def set_default_profile(self, profile: str) -> None:
        """Set the default profile."""
        if not self.has_profile(profile):
            raise ValueError(f"Profile '{profile}' not found")
        self._default_profile = profile
    
    def get_default_profile(self) -> str:
        """Get the default profile."""
        if self._default_profile:
            return self._default_profile
        
        # Try to determine default from config
        if isinstance(self.providers[2], ConfigFileProvider) and self.providers[2].is_available():
            try:
                import yaml
                with open(self.providers[2].config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    if config and "default_profile" in config:
                        return config["default_profile"]
            except Exception:
                pass
        
        return "default"
    
    def clear_cache(self) -> None:
        """Clear the credentials cache."""
        self._credentials_cache.clear()
    
    def validate_credentials(self, profile: Optional[str] = None) -> bool:
        """Validate that credentials work by making a simple AWS call.
        
        Args:
            profile: Profile to validate
            
        Returns:
            True if credentials are valid
        """
        try:
            client = self.create_client("sts", profile)
            client.get_caller_identity()
            return True
        except Exception as e:
            logger.error(f"Credential validation failed: {e}")
            return False
    
    def get_account_info(self, profile: Optional[str] = None) -> Optional[Dict[str, str]]:
        """Get AWS account information.
        
        Args:
            profile: Profile to use
            
        Returns:
            Dictionary with account info or None
        """
        try:
            client = self.create_client("sts", profile)
            response = client.get_caller_identity()
            return {
                "account_id": response["Account"],
                "user_id": response["UserId"],
                "arn": response["Arn"]
            }
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            return None