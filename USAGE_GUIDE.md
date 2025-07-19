# AWS Agent Usage Guide

This guide provides detailed instructions for using the AWS Agent to perform various AWS operations through natural language commands.

## Table of Contents

1. [Installation](#installation)
2. [Configuration](#configuration)
3. [Basic Usage](#basic-usage)
4. [Chat Interface](#chat-interface)
5. [Command Line Interface](#command-line-interface)
6. [AWS Operations](#aws-operations)
7. [File Transfers](#file-transfers)
8. [Extending the Agent](#extending-the-agent)

## Installation

### Prerequisites

- Python 3.9 or higher
- AWS credentials configured
- OpenAI API key (for GPT-4 model)

### Install from Source

```bash
# Clone the repository
cd /path/to/aws_agent

# Install in development mode
pip install -e .

# Or install with dev dependencies
pip install -e ".[dev]"
```

## Configuration

### 1. AWS Credentials

The agent supports multiple credential sources:

#### Environment Variables
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

#### AWS Profile (~/.aws/credentials)
```ini
[default]
aws_access_key_id = your_access_key
aws_secret_access_key = your_secret_key

[production]
aws_access_key_id = prod_access_key
aws_secret_access_key = prod_secret_key
```

#### Custom Config File
```bash
# Copy template
cp config/aws_config_template.yml aws_config.yml

# Edit with your credentials
vim aws_config.yml
```

### 2. OpenAI Configuration

Set your OpenAI API key:
```bash
export OPENAI_API_KEY=your_openai_api_key
```

## Basic Usage

### Quick Start

```bash
# Send a single command
aws-agent chat "List all my S3 buckets"

# Start the chat server
aws-agent server

# List available profiles
aws-agent profiles

# Validate credentials
aws-agent validate production
```

## Chat Interface

### Starting the Chat Server

```bash
# Start with defaults
aws-agent server

# Custom host and port
aws-agent server --host 127.0.0.1 --port 3000

# Enable auto-reload for development
aws-agent server --reload
```

### Using the Web Interface

1. Open http://localhost:8000 in your browser
2. Select your AWS profile from the dropdown
3. Type natural language commands in the chat box

### Example Commands

```
"List all S3 buckets"
"Show me EC2 instances in us-west-2"
"Upload /path/to/file.txt to my-bucket"
"Download s3://my-bucket/data.csv to ./downloads/"
"Create a new S3 bucket called my-new-bucket"
```

## Command Line Interface

### Single Commands

```bash
# Basic usage
aws-agent chat "What S3 buckets do I have?"

# Specify profile
aws-agent chat "List EC2 instances" --profile production

# Use custom config
aws-agent chat "Show Lambda functions" --config ~/my-config.yml
```

### File Transfers

```bash
# Upload file to S3
aws-agent transfer ./local/file.txt s3://my-bucket/file.txt

# Download from S3
aws-agent transfer s3://my-bucket/data/ ./local/data/ --recursive

# Transfer with pattern matching
aws-agent transfer ./logs/ s3://backup-bucket/logs/ --recursive --pattern "*.log"

# Using specific profile
aws-agent transfer ./data s3://prod-bucket/data --profile production
```

## AWS Operations

### S3 Operations

#### List Buckets
```
"List all my S3 buckets"
"Show S3 buckets in us-west-2"
```

#### List Objects
```
"List files in bucket my-bucket"
"Show objects in s3://my-bucket/data/"
"List CSV files in my-data-bucket"
```

#### Upload Files
```
"Upload file.txt to my-bucket"
"Upload /home/user/data.csv to s3://my-bucket/datasets/"
```

#### Download Files
```
"Download s3://my-bucket/file.txt"
"Download all files from s3://my-bucket/logs/ to ./backup/"
```

#### Create Buckets
```
"Create a new S3 bucket called my-new-bucket"
"Create bucket project-data in eu-west-1"
```

#### Delete Objects
```
"Delete file.txt from my-bucket"
"Remove s3://my-bucket/old-data/"
```

### EC2 Operations (Coming Soon)

```
"List all EC2 instances"
"Start instance i-1234567890abcdef0"
"Stop all instances tagged as development"
"Create a new t3.micro instance"
```

### Lambda Operations (Coming Soon)

```
"List all Lambda functions"
"Invoke function process-data"
"Deploy new Lambda function from ./code.zip"
"Update function configuration"
```

## File Transfers

### Upload Patterns

```bash
# Single file
aws-agent transfer ./file.txt s3://bucket/file.txt

# Directory (recursive)
aws-agent transfer ./data/ s3://bucket/data/ --recursive

# With pattern matching
aws-agent transfer ./logs/ s3://bucket/logs/ --recursive --pattern "*.log"

# Multiple files with pattern
aws-agent transfer ./images/ s3://bucket/imgs/ --recursive --pattern "*.jpg"
```

### Download Patterns

```bash
# Single file
aws-agent transfer s3://bucket/file.txt ./file.txt

# Entire prefix
aws-agent transfer s3://bucket/data/ ./local/data/ --recursive

# Specific file types
aws-agent transfer s3://bucket/docs/ ./docs/ --recursive --pattern "*.pdf"
```

### S3 to S3 Copy

```bash
# Copy between buckets
aws-agent transfer s3://source-bucket/data/ s3://dest-bucket/backup/ --recursive

# Copy with different profiles
aws-agent transfer s3://prod-bucket/data/ s3://dev-bucket/data/ --profile dev
```

## Extending the Agent

### Adding New AWS Services

1. Create a new tool module in `src/aws_agent/tools/`:

```python
# src/aws_agent/tools/dynamodb/list_tables.py
from langchain_core.tools import BaseTool
from ..base import AWSBaseTool

class ListDynamoDBTablesTool(AWSBaseTool):
    name = "list_dynamodb_tables"
    description = "List all DynamoDB tables"
    
    def _run(self, profile=None):
        client = self._get_client("dynamodb", profile)
        response = client.list_tables()
        return response["TableNames"]
```

2. Register the tool in `src/aws_agent/tools/__init__.py`

3. Update the agent's graph to handle the new service

### Custom LangChain Tools

You can add custom tools to the agent:

```python
from aws_agent import AWSAgent
from langchain_core.tools import tool

@tool
def custom_analysis(data: str) -> str:
    """Perform custom analysis on AWS data."""
    # Your custom logic here
    return f"Analysis complete: {data}"

# Create agent with custom tools
agent = AWSAgent(tools=[custom_analysis])
```

### Using Different LLMs

```python
from aws_agent import AWSAgent
from langchain_openai import ChatOpenAI
from langchain_community.llms import Ollama

# Use a different OpenAI model
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.5)
agent = AWSAgent(llm=llm)

# Use a local model with Ollama
llm = Ollama(model="llama2")
agent = AWSAgent(llm=llm)
```

## Best Practices

### Security

1. **Never commit credentials** - Use environment variables or AWS profiles
2. **Use IAM roles** when running on EC2/Lambda
3. **Rotate credentials regularly**
4. **Use least privilege** - Grant only necessary permissions

### Performance

1. **Use profiles** to avoid credential lookup overhead
2. **Batch operations** when possible
3. **Use patterns** to filter files during transfer
4. **Enable compression** for large transfers

### Error Handling

The agent provides detailed error messages:

```
# Permission errors
"Access denied. Check your AWS credentials and permissions."

# Resource not found
"Bucket not found. Error during listing S3 buckets: NoSuchBucket"

# Network issues
"Connection timeout. Check your internet connection and AWS region."
```

## Troubleshooting

### Common Issues

#### 1. Authentication Errors
```bash
# Validate credentials
aws-agent validate default

# Check which credentials are being used
aws-agent profiles
```

#### 2. Profile Not Found
```bash
# List available profiles
aws-agent profiles

# Check config file
cat ~/.aws/credentials
cat aws_config.yml
```

#### 3. Connection Issues
```bash
# Test with a simple operation
aws-agent chat "List S3 buckets" --profile default

# Enable debug logging
aws-agent --debug chat "Test connection"
```

### Debug Mode

Enable debug logging for detailed information:

```bash
# CLI debug mode
aws-agent --debug chat "Your command"

# Server debug mode
aws-agent --debug server

# Python logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Support

For issues and feature requests, please check:
- GitHub repository issues
- AWS Agent documentation
- AWS service documentation

Remember to never share your AWS credentials when seeking help!