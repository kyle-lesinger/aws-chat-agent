"""Credential providers for AWS authentication."""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, Tuple
import configparser
import json
import yaml
from dataclasses import dataclass
import keyring
from cryptography.fernet import Fernet
import boto3


@dataclass
class AWSCredentials:
    """AWS credentials container."""
    access_key_id: str
    secret_access_key: str
    session_token: Optional[str] = None
    region: Optional[str] = None
    profile_name: Optional[str] = None


class CredentialProvider(ABC):
    """Base class for credential providers."""
    
    @abstractmethod
    def get_credentials(self, profile: Optional[str] = None) -> Optional[AWSCredentials]:
        """Get AWS credentials."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available."""
        pass


class EnvironmentProvider(CredentialProvider):
    """Provider for environment variable credentials."""
    
    def get_credentials(self, profile: Optional[str] = None) -> Optional[AWSCredentials]:
        """Get credentials from environment variables."""
        access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
        
        if not (access_key and secret_key):
            return None
        
        return AWSCredentials(
            access_key_id=access_key,
            secret_access_key=secret_key,
            session_token=os.environ.get("AWS_SESSION_TOKEN"),
            region=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            profile_name="environment"
        )
    
    def is_available(self) -> bool:
        """Check if environment credentials are available."""
        return bool(os.environ.get("AWS_ACCESS_KEY_ID"))


class ProfileProvider(CredentialProvider):
    """Provider for AWS profile credentials."""
    
    def __init__(self):
        self.credentials_path = Path.home() / ".aws" / "credentials"
        self.config_path = Path.home() / ".aws" / "config"
    
    def get_credentials(self, profile: Optional[str] = None) -> Optional[AWSCredentials]:
        """Get credentials from AWS profiles."""
        profile = profile or "default"
        
        # Parse credentials file
        credentials = configparser.ConfigParser()
        if self.credentials_path.exists():
            credentials.read(self.credentials_path)
        
        # Parse config file
        config = configparser.ConfigParser()
        if self.config_path.exists():
            config.read(self.config_path)
        
        # Handle both 'profile <name>' and '<name>' formats in config
        config_section = f"profile {profile}" if profile != "default" else "default"
        
        # Check if profile exists in either file
        has_creds = profile in credentials
        has_config = config_section in config
        
        if not has_creds and not has_config:
            return None
        
        # Get credentials from credentials file
        access_key_id = None
        secret_access_key = None
        session_token = None
        
        if has_creds:
            profile_creds = credentials[profile]
            access_key_id = profile_creds.get("aws_access_key_id")
            secret_access_key = profile_creds.get("aws_secret_access_key")
            session_token = profile_creds.get("aws_session_token")
        
        # Get region and other settings from config file
        region = "us-east-1"
        if has_config:
            config_profile = config[config_section]
            region = config_profile.get("region", "us-east-1")
            
            # If no credentials in credentials file, check for role_arn or other auth methods
            if not access_key_id and "role_arn" in config_profile:
                # This profile uses IAM role assumption, let boto3 handle it
                try:
                    session = boto3.Session(profile_name=profile)
                    creds = session.get_credentials()
                    if creds:
                        return AWSCredentials(
                            access_key_id=creds.access_key,
                            secret_access_key=creds.secret_key,
                            session_token=creds.token,
                            region=region,
                            profile_name=profile
                        )
                except Exception:
                    pass
        
        # Return credentials if we have them
        if access_key_id and secret_access_key:
            return AWSCredentials(
                access_key_id=access_key_id,
                secret_access_key=secret_access_key,
                session_token=session_token,
                region=region,
                profile_name=profile
            )
        
        return None
    
    def is_available(self) -> bool:
        """Check if AWS credentials or config file exists."""
        return self.credentials_path.exists() or self.config_path.exists()
    
    def list_profiles(self) -> list[str]:
        """List available AWS profiles from both credentials and config files."""
        profiles = set()
        
        # Get profiles from credentials file
        if self.credentials_path.exists():
            credentials = configparser.ConfigParser()
            credentials.read(self.credentials_path)
            profiles.update(credentials.sections())
        
        # Get profiles from config file
        if self.config_path.exists():
            config = configparser.ConfigParser()
            config.read(self.config_path)
            for section in config.sections():
                # Handle both 'profile <name>' and '<name>' formats
                if section.startswith("profile "):
                    profiles.add(section[8:])  # Remove 'profile ' prefix
                elif section == "default":
                    profiles.add(section)
        
        return sorted(list(profiles))


class ConfigFileProvider(CredentialProvider):
    """Provider for custom config file credentials."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("aws_config.yml")
    
    def get_credentials(self, profile: Optional[str] = None) -> Optional[AWSCredentials]:
        """Get credentials from custom config file."""
        if not self.config_path.exists():
            return None
        
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        if not config:
            return None
        
        # Get profile
        profile = profile or config.get("default_profile", "default")
        profiles = config.get("profiles", {})
        
        if profile not in profiles:
            return None
        
        profile_config = profiles[profile]
        
        # Check if credentials are encrypted
        if profile_config.get("encrypted"):
            # Would need to implement decryption logic
            return None
        
        return AWSCredentials(
            access_key_id=profile_config.get("access_key_id"),
            secret_access_key=profile_config.get("secret_access_key"),
            session_token=profile_config.get("session_token"),
            region=profile_config.get("region", "us-east-1"),
            profile_name=profile
        )
    
    def is_available(self) -> bool:
        """Check if config file exists."""
        return self.config_path.exists()


class KeyringProvider(CredentialProvider):
    """Provider for credentials stored in system keyring."""
    
    SERVICE_NAME = "aws-agent"
    
    def get_credentials(self, profile: Optional[str] = None) -> Optional[AWSCredentials]:
        """Get credentials from system keyring."""
        profile = profile or "default"
        
        try:
            # Try to get credentials from keyring
            creds_json = keyring.get_password(self.SERVICE_NAME, profile)
            if not creds_json:
                return None
            
            creds = json.loads(creds_json)
            return AWSCredentials(
                access_key_id=creds["access_key_id"],
                secret_access_key=creds["secret_access_key"],
                session_token=creds.get("session_token"),
                region=creds.get("region", "us-east-1"),
                profile_name=profile
            )
        except Exception:
            return None
    
    def is_available(self) -> bool:
        """Check if keyring is available."""
        try:
            # Test keyring availability
            keyring.get_password("test", "test")
            return True
        except Exception:
            return False
    
    def store_credentials(self, profile: str, credentials: AWSCredentials) -> bool:
        """Store credentials in keyring."""
        try:
            creds_dict = {
                "access_key_id": credentials.access_key_id,
                "secret_access_key": credentials.secret_access_key,
                "session_token": credentials.session_token,
                "region": credentials.region
            }
            keyring.set_password(self.SERVICE_NAME, profile, json.dumps(creds_dict))
            return True
        except Exception:
            return False


class IAMRoleProvider(CredentialProvider):
    """Provider for IAM role credentials (EC2/Lambda)."""
    
    def get_credentials(self, profile: Optional[str] = None) -> Optional[AWSCredentials]:
        """Get credentials from IAM role."""
        try:
            # Use boto3 to get credentials from instance metadata
            session = boto3.Session()
            credentials = session.get_credentials()
            
            if not credentials:
                return None
            
            return AWSCredentials(
                access_key_id=credentials.access_key,
                secret_access_key=credentials.secret_key,
                session_token=credentials.token,
                region=session.region_name or "us-east-1",
                profile_name="iam-role"
            )
        except Exception:
            return None
    
    def is_available(self) -> bool:
        """Check if running on EC2/Lambda with IAM role."""
        try:
            import urllib.request
            # Check if instance metadata service is available
            response = urllib.request.urlopen(
                "http://169.254.169.254/latest/meta-data/",
                timeout=1
            )
            return response.status == 200
        except Exception:
            return False