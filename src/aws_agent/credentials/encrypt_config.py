#!/usr/bin/env python3
"""Utility to encrypt AWS credentials in config files."""

import sys
import yaml
import argparse
from pathlib import Path
from .encryption import credential_encryption


def encrypt_config_file(config_path: Path, output_path: Optional[Path] = None):
    """Encrypt sensitive fields in a config file.
    
    Args:
        config_path: Path to config file to encrypt
        output_path: Output path (defaults to overwriting input file)
    """
    # Read config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    if not config:
        print("Empty config file")
        return
    
    # Encrypt profiles
    if 'profiles' in config:
        for profile_name, profile_config in config['profiles'].items():
            config['profiles'][profile_name] = credential_encryption.encrypt_dict(profile_config)
            print(f"Encrypted profile: {profile_name}")
    
    # Write encrypted config
    output_path = output_path or config_path
    with open(output_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    print(f"Encrypted config written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Encrypt AWS credentials in config files")
    parser.add_argument('config_file', help="Path to config file")
    parser.add_argument('-o', '--output', help="Output path (default: overwrite input)")
    parser.add_argument('-k', '--key', help="Encryption key (default: from environment)")
    
    args = parser.parse_args()
    
    config_path = Path(args.config_file)
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    
    # Set encryption key if provided
    if args.key:
        import os
        os.environ['AWS_AGENT_ENCRYPTION_KEY'] = args.key
    
    output_path = Path(args.output) if args.output else None
    
    try:
        encrypt_config_file(config_path, output_path)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()