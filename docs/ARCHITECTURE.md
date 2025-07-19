# AWS Agent Architecture

This document describes the architecture and design of the AWS Agent system.

## Overview

The AWS Agent is built using a modular, extensible architecture that leverages LangChain and LangGraph for intelligent natural language processing of AWS operations. The system is designed to be:

- **Extensible**: Easy to add new AWS services and operations
- **Secure**: Multiple credential management options with encryption support
- **Scalable**: Async-first design with WebSocket support
- **User-friendly**: Natural language interface with multiple interaction modes

## Core Components

### 1. Agent Core (`src/aws_agent/core/`)

The heart of the system, built on LangGraph:

- **`agent.py`**: Main `AWSAgent` class that orchestrates operations
- **`state.py`**: State management for agent conversations and operations
- **`graph.py`**: LangGraph workflow definition
- **`nodes.py`**: Graph nodes for routing, planning, execution, and response

```python
# Simplified flow
User Input → Route → Plan → Execute → Respond
                ↓        ↓       ↓
              Error ← Error ← Error
```

### 2. Credential Management (`src/aws_agent/credentials/`)

Secure, flexible credential handling:

- **`manager.py`**: Central `AWSCredentialManager` with provider chain
- **`providers.py`**: Multiple credential providers:
  - Environment variables
  - AWS profiles (~/.aws/credentials)
  - Custom config files (YAML)
  - System keyring (secure storage)
  - IAM roles (EC2/Lambda)

Provider precedence order:
1. Environment variables (fastest)
2. AWS profiles (most common)
3. Custom config file
4. System keyring
5. IAM roles (automatic on AWS)

### 3. Tools System (`src/aws_agent/tools/`)

LangChain tools for AWS operations:

```
tools/
├── s3/               # S3 operations
│   ├── base.py      # Base S3 tool class
│   ├── list_buckets.py
│   ├── list_objects.py
│   ├── upload_file.py
│   ├── download_file.py
│   ├── create_bucket.py
│   ├── delete_object.py
│   └── file_transfer.py  # Advanced transfers
├── ec2/              # EC2 operations (extensible)
└── lambda_tools/     # Lambda operations (extensible)
```

Each tool:
- Inherits from `BaseTool` (LangChain)
- Implements `_run()` and `_arun()` methods
- Uses Pydantic for input validation
- Handles errors gracefully

### 4. Chat Interface (`src/aws_agent/chat/`)

Real-time communication layer:

- **`server.py`**: FastAPI server with REST and WebSocket endpoints
- **`websocket.py`**: WebSocket message handling
- **`__main__.py`**: Standalone server runner

Features:
- WebSocket for real-time chat
- REST API for programmatic access
- Profile switching
- Operation history
- HTML interface included

### 5. CLI (`src/aws_agent/cli.py`)

Command-line interface using Click:

- `chat`: Single command execution
- `server`: Start chat server
- `transfer`: File transfer operations
- `profiles`: List AWS profiles
- `validate`: Validate credentials

## Data Flow

### 1. Natural Language Processing

```
User Input: "List all S3 buckets"
    ↓
Route Node: Identifies S3 operation
    ↓
Plan Node: Creates operation plan
    - Service: S3
    - Action: list_buckets
    - Parameters: {}
    ↓
Execute Node: Runs S3 tool
    - Tool: ListS3BucketsTool
    - Credentials: From manager
    - API Call: boto3.client('s3').list_buckets()
    ↓
Response Node: Formats result
    - Success message
    - Bucket list
    - Profile used
```

### 2. Credential Resolution

```
Agent Request for S3 Client
    ↓
CredentialManager.create_client('s3', profile)
    ↓
Get Credentials (profile='production')
    ↓
Try Providers in Order:
    1. Environment → Not found
    2. AWS Profile → Found!
    ↓
Create boto3 Session
    ↓
Return S3 Client
```

### 3. File Transfer Flow

```
Transfer Command: "Upload ./data to s3://bucket/data/"
    ↓
Parse Source/Destination
    ↓
Determine Transfer Type:
    - Local → S3: Upload
    - S3 → Local: Download  
    - S3 → S3: Copy
    ↓
List Files (with pattern matching)
    ↓
Execute Transfers (parallel when possible)
    ↓
Report Results
```

## Extension Points

### 1. Adding New AWS Services

Create a new tool module:

```python
# src/aws_agent/tools/dynamodb/list_tables.py
class ListDynamoDBTablesTool(S3BaseTool):
    name = "list_dynamodb_tables"
    description = "List DynamoDB tables"
    
    def _run(self, profile=None):
        client = self._get_client("dynamodb", profile)
        return client.list_tables()["TableNames"]
```

Register in `tools/__init__.py`:

```python
from .dynamodb import get_dynamodb_tools
tools.extend(get_dynamodb_tools(credential_manager))
```

### 2. Custom Credential Providers

Implement the `CredentialProvider` interface:

```python
class VaultProvider(CredentialProvider):
    def get_credentials(self, profile=None):
        # Fetch from HashiCorp Vault
        return AWSCredentials(...)
    
    def is_available(self):
        # Check if vault is accessible
        return vault_client.is_authenticated()
```

### 3. Custom LLMs

Replace the default OpenAI model:

```python
from langchain_community.llms import Bedrock

llm = Bedrock(
    model_id="anthropic.claude-v2",
    region_name="us-east-1"
)
agent = AWSAgent(llm=llm)
```

### 4. Custom Graph Nodes

Add new processing nodes:

```python
def audit_node(state: AgentState):
    """Log all AWS operations for compliance."""
    operation = state["context"]["planned_operation"]
    audit_log.record(operation)
    return state

# Add to graph
workflow.add_node("audit", audit_node)
workflow.add_edge("plan", "audit")
workflow.add_edge("audit", "execute")
```

## Security Considerations

### 1. Credential Security

- Never log credentials
- Use environment variables in production
- Encrypt credentials at rest
- Rotate credentials regularly
- Use IAM roles when possible

### 2. Network Security

- HTTPS for API endpoints
- WSS for secure WebSocket
- Validate all inputs
- Rate limiting
- CORS configuration

### 3. Operation Security

- Audit logging
- Permission validation
- Resource tagging
- Cost monitoring

## Performance Optimization

### 1. Caching

- Credential caching per profile
- boto3 client reuse
- LLM response caching (planned)

### 2. Async Operations

- Async AWS API calls
- Concurrent file transfers
- WebSocket for real-time updates

### 3. Resource Management

- Connection pooling
- Memory-efficient file streaming
- Lazy loading of providers

## Future Enhancements

1. **More AWS Services**
   - DynamoDB operations
   - CloudFormation management
   - IAM policy analysis

2. **Advanced Features**
   - Multi-region operations
   - Cost optimization suggestions
   - Security audit capabilities

3. **Integration**
   - GitHub Actions
   - Jenkins plugins
   - Terraform integration

4. **Intelligence**
   - Operation history learning
   - Predictive suggestions
   - Anomaly detection