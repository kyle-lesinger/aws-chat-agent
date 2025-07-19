"""AWS profile management examples."""

from aws_agent import AWSAgent, AWSCredentialManager
from aws_agent.credentials.providers import AWSCredentials, KeyringProvider
import asyncio


def list_profiles_example():
    """List all available AWS profiles."""
    print("Available AWS Profiles")
    print("=" * 50)
    
    credential_manager = AWSCredentialManager()
    profiles = credential_manager.list_profiles()
    
    for profile in profiles:
        # Validate each profile
        if credential_manager.validate_credentials(profile):
            status = "✓ Valid"
            account_info = credential_manager.get_account_info(profile)
            if account_info:
                status += f" (Account: {account_info['account_id']})"
        else:
            status = "✗ Invalid"
        
        print(f"{profile}: {status}")


async def profile_switching_example():
    """Demonstrate switching between profiles."""
    print("\nProfile Switching Example")
    print("=" * 50)
    
    credential_manager = AWSCredentialManager()
    agent = AWSAgent(credential_manager=credential_manager)
    
    # Get current profile
    current = agent.get_current_profile()
    print(f"Current profile: {current}")
    
    # List buckets with default profile
    response = await agent.arun("List my S3 buckets")
    print(f"\nBuckets in {current} profile:")
    print(response)
    
    # Switch to another profile if available
    profiles = agent.get_available_profiles()
    if len(profiles) > 1:
        # Find a different profile
        other_profile = next(p for p in profiles if p != current)
        
        print(f"\nSwitching to profile: {other_profile}")
        agent.set_profile(other_profile)
        
        response = await agent.arun("List my S3 buckets")
        print(f"\nBuckets in {other_profile} profile:")
        print(response)


def store_credentials_securely():
    """Example of storing credentials securely in keyring."""
    print("\nSecure Credential Storage Example")
    print("=" * 50)
    
    keyring_provider = KeyringProvider()
    
    if not keyring_provider.is_available():
        print("Keyring is not available on this system")
        return
    
    # Example credentials (DO NOT use real credentials in code!)
    test_creds = AWSCredentials(
        access_key_id="EXAMPLE_ACCESS_KEY",
        secret_access_key="EXAMPLE_SECRET_KEY",
        region="us-east-1",
        profile_name="test-secure"
    )
    
    # Store in keyring
    success = keyring_provider.store_credentials("test-secure", test_creds)
    if success:
        print("✓ Credentials stored securely in system keyring")
        
        # Retrieve to verify
        retrieved = keyring_provider.get_credentials("test-secure")
        if retrieved:
            print(f"✓ Retrieved profile: {retrieved.profile_name}")
            print(f"  Region: {retrieved.region}")
    else:
        print("✗ Failed to store credentials")


async def multi_profile_operations():
    """Perform operations across multiple profiles."""
    print("\nMulti-Profile Operations Example")
    print("=" * 50)
    
    credential_manager = AWSCredentialManager()
    
    profiles = credential_manager.list_profiles()
    if len(profiles) < 2:
        print("Need at least 2 profiles for this example")
        return
    
    # Create agents for different profiles
    agents = {}
    for profile in profiles[:2]:  # Use first 2 profiles
        agent = AWSAgent(
            credential_manager=credential_manager,
            profile=profile
        )
        agents[profile] = agent
    
    # List buckets in each profile
    for profile, agent in agents.items():
        print(f"\nProfile: {profile}")
        response = await agent.arun("Count my S3 buckets")
        print(response)


def create_config_file_example():
    """Example of creating a config file."""
    print("\nConfig File Example")
    print("=" * 50)
    
    config_content = """# AWS Agent Configuration
default_profile: development

profiles:
  development:
    use_aws_profile: true
    aws_profile_name: dev
    region: us-east-1
    
  staging:
    access_key_id: ${AWS_STAGING_ACCESS_KEY}
    secret_access_key: ${AWS_STAGING_SECRET_KEY}
    region: us-west-2
    
  production:
    use_aws_profile: true
    aws_profile_name: prod
    region: eu-west-1

agent:
  model: gpt-4-turbo-preview
  temperature: 0
"""
    
    print("Example configuration:")
    print(config_content)
    
    # Save to example file
    with open("example_config.yml", "w") as f:
        f.write(config_content)
    
    print("\nSaved to example_config.yml")
    print("To use: aws-agent --config example_config.yml chat 'List buckets'")


if __name__ == "__main__":
    # List profiles
    list_profiles_example()
    
    # Profile switching
    asyncio.run(profile_switching_example())
    
    # Secure storage
    store_credentials_securely()
    
    # Multi-profile operations
    asyncio.run(multi_profile_operations())
    
    # Config file
    create_config_file_example()