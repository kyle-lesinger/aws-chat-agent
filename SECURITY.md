# Security Best Practices

## API Key Management

### NEVER commit sensitive data to Git!

This repository uses several methods to keep your API keys and credentials secure:

### 1. Environment Variables (Recommended)

Set your OpenAI API key as an environment variable:

```bash
export OPENAI_API_KEY="sk-your-api-key-here"
```

For permanent setup, add to your shell profile:
- **bash**: `~/.bashrc` or `~/.bash_profile`
- **zsh**: `~/.zshrc`

### 2. Local .env File

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your API key:
   ```
   OPENAI_API_KEY=sk-your-api-key-here
   ```

3. The `.env` file is gitignored and will never be committed.

### 3. Configuration File

1. Copy `aws_config.yml.example` to `aws_config.yml`:
   ```bash
   cp aws_config.yml.example aws_config.yml
   ```

2. Edit `aws_config.yml` and add your credentials.

3. The `aws_config.yml` file is gitignored and will never be committed.

## Additional Security Options

### 4. AWS Secrets Manager

For production use, consider storing your API key in AWS Secrets Manager:

```python
import boto3
import json

def get_openai_api_key():
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId='openai-api-key')
    return json.loads(response['SecretString'])['api_key']
```

### 5. HashiCorp Vault

For enterprise environments, use HashiCorp Vault:

```bash
vault kv put secret/openai api_key="sk-your-api-key-here"
```

### 6. System Keychain/Keyring

The agent already supports system keyring for AWS credentials. This can be extended for OpenAI keys.

## Git Security Checklist

Before committing:

- [ ] Check `git status` - ensure no sensitive files are staged
- [ ] Review `.gitignore` includes all credential files
- [ ] Never commit files containing:
  - API keys
  - AWS credentials
  - Private keys
  - Passwords
  - Tokens

## If You Accidentally Commit Secrets

1. **Immediately revoke the exposed credentials**
2. Remove from history:
   ```bash
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch PATH-TO-YOUR-FILE" \
     --prune-empty --tag-name-filter cat -- --all
   ```
3. Force push to remote (coordinate with team)
4. Generate new credentials

## AWS Credentials Security

The agent reads AWS credentials from:
1. Environment variables
2. `~/.aws/credentials` (standard AWS CLI location)
3. `~/.aws/config` (standard AWS CLI location)
4. IAM roles (when running on EC2/Lambda)

Never store AWS credentials in code or config files that might be committed.