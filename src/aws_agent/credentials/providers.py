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
import logging
from datetime import datetime, timedelta, timezone
import getpass
import sys

logger = logging.getLogger(__name__)


class MFARequiredException(Exception):
    """Exception raised when MFA is required but no callback is provided."""
    def __init__(self, profile: str, mfa_device: str):
        self.profile = profile
        self.mfa_device = mfa_device
        super().__init__(f"MFA required for profile '{profile}' with device '{mfa_device}'")


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
        # Skip environment credentials for MFA profiles
        if profile and profile in STSProvider.MFA_PROFILES:
            logger.info(f"EnvironmentProvider skipping MFA profile '{profile}'")
            return None
            
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
        self._encryption = None
    
    def _get_encryption(self):
        """Lazy load encryption module to avoid circular imports."""
        if self._encryption is None:
            from .encryption import credential_encryption
            self._encryption = credential_encryption
        return self._encryption
    
    def get_credentials(self, profile: Optional[str] = None) -> Optional[AWSCredentials]:
        """Get credentials from custom config file."""
        if not self.config_path.exists():
            return None
        
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
            return None
        
        if not config:
            return None
        
        # Get profile
        profile = profile or config.get("default_profile", "default")
        profiles = config.get("profiles", {})
        
        if profile not in profiles:
            return None
        
        profile_config = profiles[profile]
        
        # Decrypt profile config if it contains encrypted fields
        try:
            encryption = self._get_encryption()
            profile_config = encryption.decrypt_dict(profile_config)
        except Exception as e:
            logger.warning(f"Failed to decrypt credentials: {e}")
            # Continue with unencrypted values
        
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
    
    def list_profiles(self) -> list[str]:
        """List available profiles from config file."""
        profiles = []
        
        if not self.config_path.exists():
            return profiles
            
        try:
            import yaml
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                
            if config and isinstance(config, dict):
                # Check for profiles under 'profiles' key
                if "profiles" in config and isinstance(config["profiles"], dict):
                    profiles.extend(config["profiles"].keys())
                # Also check root level for profile-like entries
                else:
                    # Look for keys that might be profiles (exclude known config keys)
                    excluded_keys = {'default_profile', 'version', 'settings'}
                    for key in config.keys():
                        if key not in excluded_keys and isinstance(config[key], dict):
                            # Check if it looks like a profile (has credentials or role info)
                            entry = config[key]
                            if any(k in entry for k in ['access_key_id', 'role_arn', 'aws_profile_name', 'use_aws_profile']):
                                profiles.append(key)
                                
        except Exception as e:
            logger.warning(f"Error reading config file {self.config_path}: {e}")
            
        return profiles


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


class STSProvider(CredentialProvider):
    """Provider for temporary credentials using AWS STS with MFA support."""
    
    # List of profiles that require MFA
    MFA_PROFILES = ["veda-smce", "smce-veda", "ghgc-smce", "aq", "uah-veda"]
    
    def __init__(self, base_provider: Optional[CredentialProvider] = None, mfa_callback=None):
        """Initialize STS provider.
        
        Args:
            base_provider: Provider to get base credentials from (defaults to ProfileProvider)
            mfa_callback: Callback function to get MFA code (defaults to getpass)
        """
        self.base_provider = base_provider or ProfileProvider()
        self._credentials_cache: Dict[str, Dict] = {}
        self._cache_file = Path.home() / ".aws" / "aws_agent_sts_cache.json"
        self._mfa_callback = mfa_callback
        self._load_cache()
    
    def _load_cache(self):
        """Load credentials cache from file."""
        if self._cache_file.exists():
            try:
                with open(self._cache_file, 'r') as f:
                    self._credentials_cache = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load STS cache: {e}")
                self._credentials_cache = {}
    
    def _save_cache(self):
        """Save credentials cache to file."""
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cache_file, 'w') as f:
                json.dump(self._credentials_cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save STS cache: {e}")
    
    def _is_credential_valid(self, cached_creds: Dict) -> bool:
        """Check if cached credentials are valid.
        
        Credentials are considered valid if:
        - They exist and have not expired
        - They have at least 12 hours remaining before expiration
        """
        if not cached_creds:
            return False
        
        try:
            expiration = datetime.fromisoformat(cached_creds['expiration'].replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            time_remaining = expiration - now
            
            # Check if expired
            if time_remaining <= timedelta(0):
                return False
            
            # Check if less than 12 hours remaining
            if time_remaining < timedelta(hours=12):
                logger.info(f"Credentials expiring soon (in {time_remaining}), will refresh")
                return False
            
            return True
        except Exception as e:
            logger.warning(f"Failed to check credential validity: {e}")
            return False
    
    def _get_mfa_device(self, profile: str, base_creds: AWSCredentials) -> Optional[str]:
        """Get MFA device for the current user."""
        try:
            # Create STS client with base credentials
            sts_client = boto3.client(
                'sts',
                aws_access_key_id=base_creds.access_key_id,
                aws_secret_access_key=base_creds.secret_access_key,
                region_name=base_creds.region
            )
            
            # Get current user identity
            identity = sts_client.get_caller_identity()
            user_arn = identity['Arn']
            
            # Extract username from ARN
            if ':user/' in user_arn:
                username = user_arn.split(':user/')[-1]
            else:
                logger.warning(f"Could not extract username from ARN: {user_arn}")
                return None
            
            # Create IAM client
            iam_client = boto3.client(
                'iam',
                aws_access_key_id=base_creds.access_key_id,
                aws_secret_access_key=base_creds.secret_access_key,
                region_name=base_creds.region
            )
            
            # List MFA devices
            response = iam_client.list_mfa_devices(UserName=username)
            if response['MFADevices']:
                return response['MFADevices'][0]['SerialNumber']
            
            return None
        except Exception as e:
            logger.warning(f"Failed to get MFA device: {e}")
            return None
    
    def _prompt_mfa_code(self, profile: str, mfa_device: str) -> str:
        """Prompt user for MFA code."""
        logger.info(f"_prompt_mfa_code called: callback={self._mfa_callback is not None}, isatty={sys.stdin.isatty()}")
        
        if self._mfa_callback:
            # Use provided callback (e.g., for web interface)
            logger.info("Using MFA callback")
            return self._mfa_callback(profile, mfa_device)
        else:
            # Check if we're in a non-interactive context
            if not sys.stdin.isatty():
                logger.info("Not in terminal context, raising MFARequiredException")
                raise MFARequiredException(profile, mfa_device)
            # Fall back to terminal prompt
            logger.info("Using terminal prompt for MFA")
            return getpass.getpass("🔢 Enter your MFA code: ")
    
    def get_credentials(self, profile: Optional[str] = None) -> Optional[AWSCredentials]:
        """Get temporary credentials using STS."""
        profile = profile or "default"
        
        # Check if this profile requires MFA
        requires_mfa = profile in self.MFA_PROFILES
        
        # Log the profile being checked
        logger.info(f"STSProvider.get_credentials called for profile '{profile}', MFA required: {requires_mfa}")
        
        # Also check if the base provider is ConfigFileProvider and has MFA settings
        if isinstance(self.base_provider, ConfigFileProvider):
            try:
                config_path = self.base_provider.config_path
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)
                    if config and "profiles" in config and profile in config["profiles"]:
                        profile_config = config["profiles"][profile]
                        if profile_config.get("requires_mfa", False):
                            requires_mfa = True
            except Exception:
                pass
        
        # Check cache first
        cache_key = f"{profile}_sts"
        if cache_key in self._credentials_cache:
            cached = self._credentials_cache[cache_key]
            if self._is_credential_valid(cached):
                logger.info(f"Using cached STS credentials for profile '{profile}'")
                return AWSCredentials(
                    access_key_id=cached['access_key_id'],
                    secret_access_key=cached['secret_access_key'],
                    session_token=cached['session_token'],
                    region=cached.get('region', 'us-east-1'),
                    profile_name=profile
                )
        
        # Get base credentials
        logger.info(f"STSProvider: Getting base credentials for profile '{profile}' from {self.base_provider.__class__.__name__}")
        base_creds = self.base_provider.get_credentials(profile)
        if not base_creds:
            logger.error(f"STSProvider: No base credentials found for profile '{profile}'")
            return None
        logger.info(f"STSProvider: Got base credentials for profile '{profile}'")
        
        # If no MFA required, just return base credentials
        if not requires_mfa:
            logger.info(f"STSProvider: Profile '{profile}' does not require MFA, returning base credentials")
            return base_creds
        
        try:
            # Create STS client
            sts_client = boto3.client(
                'sts',
                aws_access_key_id=base_creds.access_key_id,
                aws_secret_access_key=base_creds.secret_access_key,
                region_name=base_creds.region
            )
            
            if requires_mfa:
                # Get MFA device
                mfa_device = self._get_mfa_device(profile, base_creds)
                if not mfa_device:
                    logger.error(f"No MFA device found for profile '{profile}'")
                    return base_creds  # Fall back to base credentials
                
                logger.info(f"🔐 MFA required for profile: {profile}")
                logger.info(f"📱 MFA device: {mfa_device}")
                
                # Prompt for MFA code
                logger.info(f"STSProvider: About to prompt for MFA code")
                try:
                    mfa_code = self._prompt_mfa_code(profile, mfa_device)
                except MFARequiredException:
                    # Re-raise MFA exception
                    raise
                except Exception as e:
                    logger.error(f"Error prompting for MFA: {e}")
                    raise MFARequiredException(profile, mfa_device)
                
                # Get session token with MFA
                response = sts_client.get_session_token(
                    DurationSeconds=43200,  # 12 hours
                    SerialNumber=mfa_device,
                    TokenCode=mfa_code
                )
            else:
                # Get session token without MFA
                response = sts_client.get_session_token(
                    DurationSeconds=43200  # 12 hours
                )
            
            # Extract credentials
            temp_creds = response['Credentials']
            
            # Cache the credentials
            self._credentials_cache[cache_key] = {
                'access_key_id': temp_creds['AccessKeyId'],
                'secret_access_key': temp_creds['SecretAccessKey'],
                'session_token': temp_creds['SessionToken'],
                'expiration': temp_creds['Expiration'].isoformat(),
                'region': base_creds.region
            }
            self._save_cache()
            
            logger.info(f"✅ Temporary credentials generated for profile '{profile}', expires: {temp_creds['Expiration']}")
            
            return AWSCredentials(
                access_key_id=temp_creds['AccessKeyId'],
                secret_access_key=temp_creds['SecretAccessKey'],
                session_token=temp_creds['SessionToken'],
                region=base_creds.region,
                profile_name=profile
            )
            
        except MFARequiredException:
            # Re-raise MFA exception to be handled by caller
            raise
        except Exception as e:
            logger.error(f"Failed to get STS credentials: {e}")
            # If MFA is required but we failed, don't fall back to base credentials
            if requires_mfa:
                logger.error(f"MFA required but failed to get temporary credentials")
                # Try to get MFA device for proper error
                mfa_device = self._get_mfa_device(profile, base_creds) or "unknown"
                raise MFARequiredException(profile, mfa_device)
            return base_creds  # Fall back to base credentials only for non-MFA profiles
    
    def is_available(self) -> bool:
        """Check if STS provider is available."""
        return self.base_provider.is_available()
    
    def should_handle_profile(self, profile: str) -> bool:
        """Check if this provider should handle the given profile."""
        # Check if profile is in MFA list
        if profile in self.MFA_PROFILES:
            return True
            
        # Check if ConfigFileProvider has MFA settings for this profile
        if isinstance(self.base_provider, ConfigFileProvider):
            try:
                config_path = self.base_provider.config_path
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)
                    if config and "profiles" in config and profile in config["profiles"]:
                        profile_config = config["profiles"][profile]
                        if profile_config.get("requires_mfa", False):
                            return True
            except Exception:
                pass
        
        return False
    
    def clear_cache(self, profile: Optional[str] = None):
        """Clear cached credentials."""
        if profile:
            cache_key = f"{profile}_sts"
            if cache_key in self._credentials_cache:
                del self._credentials_cache[cache_key]
                self._save_cache()
        else:
            self._credentials_cache.clear()
            self._save_cache()


class MFAAwareProfileProvider(ProfileProvider):
    """Profile provider that skips MFA-required profiles."""
    
    def get_credentials(self, profile: Optional[str] = None) -> Optional[AWSCredentials]:
        """Get credentials, but skip if profile requires MFA."""
        profile = profile or "default"
        
        # Skip MFA profiles - let STSProvider handle them
        if profile in STSProvider.MFA_PROFILES:
            logger.debug(f"MFAAwareProfileProvider skipping MFA profile '{profile}'")
            return None
            
        return super().get_credentials(profile)