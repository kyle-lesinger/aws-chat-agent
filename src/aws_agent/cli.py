"""Command-line interface for AWS Agent."""

import click
import asyncio
import json
from pathlib import Path
from typing import Optional
import logging

from .core.agent import AWSAgent
from .credentials.manager import AWSCredentialManager
from .chat.server import start_server


logger = logging.getLogger(__name__)


@click.group()
@click.option('--debug', is_flag=True, help='Enable debug logging')
def main(debug: bool):
    """AWS Agent - Intelligent AWS operations with natural language."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


@main.command()
@click.argument('message')
@click.option('--profile', '-p', default=None, help='AWS profile to use')
@click.option('--config', '-c', type=Path, default=None, help='Config file path')
def chat(message: str, profile: Optional[str], config: Optional[Path]):
    """Send a single message to the AWS Agent."""
    try:
        # Create agent
        credential_manager = AWSCredentialManager(config_path=config)
        agent = AWSAgent(
            credential_manager=credential_manager,
            profile=profile
        )
        
        # Run the message
        response = asyncio.run(agent.arun(message))
        click.echo(response)
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Exit(1)


@main.command()
@click.option('--host', '-h', default='0.0.0.0', help='Server host')
@click.option('--port', '-p', default=8000, type=int, help='Server port')
@click.option('--reload', is_flag=True, help='Enable auto-reload')
def server(host: str, port: int, reload: bool):
    """Start the AWS Agent chat server."""
    click.echo(f"Starting AWS Agent Chat Server on {host}:{port}")
    start_server(host=host, port=port, reload=reload)


@main.command()
@click.argument('source')
@click.argument('destination')
@click.option('--profile', '-p', default=None, help='AWS profile to use')
@click.option('--recursive', '-r', is_flag=True, help='Transfer recursively')
@click.option('--pattern', default=None, help='File pattern to match')
def transfer(source: str, destination: str, profile: Optional[str], 
            recursive: bool, pattern: Optional[str]):
    """Transfer files between local and S3."""
    try:
        # Create agent
        credential_manager = AWSCredentialManager()
        agent = AWSAgent(
            credential_manager=credential_manager,
            profile=profile
        )
        
        # Build transfer message
        message = f"Transfer files from {source} to {destination}"
        if recursive:
            message += " recursively"
        if pattern:
            message += f" matching pattern {pattern}"
        
        # Run the transfer
        response = asyncio.run(agent.arun(message))
        click.echo(response)
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Exit(1)


@main.command()
@click.option('--config', '-c', type=Path, default=None, help='Config file path')
def profiles(config: Optional[Path]):
    """List available AWS profiles."""
    try:
        credential_manager = AWSCredentialManager(config_path=config)
        profiles = credential_manager.list_profiles()
        
        if profiles:
            click.echo("Available AWS profiles:")
            for profile in profiles:
                # Check if profile has valid credentials
                if credential_manager.validate_credentials(profile):
                    status = "✓"
                else:
                    status = "✗"
                click.echo(f"  {status} {profile}")
        else:
            click.echo("No AWS profiles found")
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Exit(1)


@main.command()
@click.argument('profile')
@click.option('--config', '-c', type=Path, default=None, help='Config file path')
def validate(profile: str, config: Optional[Path]):
    """Validate AWS credentials for a profile."""
    try:
        credential_manager = AWSCredentialManager(config_path=config)
        
        if credential_manager.validate_credentials(profile):
            account_info = credential_manager.get_account_info(profile)
            click.echo(f"✓ Profile '{profile}' is valid")
            if account_info:
                click.echo(f"  Account ID: {account_info['account_id']}")
                click.echo(f"  ARN: {account_info['arn']}")
        else:
            click.echo(f"✗ Profile '{profile}' has invalid credentials", err=True)
            raise click.Exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Exit(1)


@main.command()
def config_template():
    """Generate a config file template."""
    template = """# AWS Agent Configuration
default_profile: default

profiles:
  default:
    access_key_id: YOUR_ACCESS_KEY
    secret_access_key: YOUR_SECRET_KEY
    region: us-east-1
    
  production:
    access_key_id: PROD_ACCESS_KEY
    secret_access_key: PROD_SECRET_KEY
    region: us-west-2
    
  development:
    # Use AWS profile from ~/.aws/credentials
    use_aws_profile: true
    aws_profile_name: dev
    region: eu-west-1

# Agent settings
agent:
  model: gpt-4-turbo-preview
  temperature: 0
  max_retries: 3
  
# S3 settings
s3:
  default_bucket: my-default-bucket
  multipart_threshold: 100MB
  multipart_chunksize: 10MB
"""
    click.echo(template)


if __name__ == "__main__":
    main()