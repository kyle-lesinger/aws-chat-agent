# AWS Agent

A specialized AWS agent built with LangChain and LangGraph for comprehensive AWS operations. This agent provides an intelligent interface for managing AWS services with natural language commands.

## Features

- 🤖 **Intelligent AWS Operations**: Natural language interface for AWS services
- 🔐 **Secure Credential Management**: Support for multiple AWS credential sources
- 📁 **S3 File Operations**: Upload, download, list, and manage S3 objects
- 💬 **Interactive Chat Interface**: Real-time WebSocket-based chat with command history
- 🚀 **Built with LangChain/LangGraph**: Modern agentic architecture
- 📊 **Multi-profile Support**: Switch between different AWS profiles seamlessly
- 🎯 **NASA Logo Integration**: Customizable branding support

## Installation

### Prerequisites
- Python 3.8 or higher
- AWS CLI configured (optional, but recommended)
- OpenAI API key

### Standard Installation

1. Clone the repository:
```bash
git clone https://github.com/kyle-lesinger/aws-chat-agent.git
cd aws_agent
```

2. Install in development mode:
```bash
pip install -e .
```

### Alternative Installation Methods

#### Using pip from GitHub:
```bash
pip install git+https://github.com/kyle-lesinger/aws-chat-agent.git
```

#### Using Poetry:
```bash
poetry install
```

### Making it Executable

#### Option 1: Using Python Module (Recommended)
```bash
# Run the chat server
python -m aws_agent.chat

# Make an alias for convenience
echo 'alias aws-chat="python -m aws_agent.chat"' >> ~/.bashrc
# or for zsh users
echo 'alias aws-chat="python -m aws_agent.chat"' >> ~/.zshrc

# Reload your shell
source ~/.bashrc  # or source ~/.zshrc

# Now you can run
aws-chat
```

#### Option 2: Create Executable Script
```bash
# Create a shell script
cat > ~/bin/aws-agent-chat << 'EOF'
#!/bin/bash
cd /path/to/aws_agent
python -m aws_agent.chat "$@"
EOF

# Make it executable
chmod +x ~/bin/aws-agent-chat

# Ensure ~/bin is in your PATH
export PATH="$HOME/bin:$PATH"  # Add to ~/.bashrc or ~/.zshrc

# Now run from anywhere
aws-agent-chat
```

#### Option 3: Using the CLI Command
```bash
# After pip install, the aws-agent command should be available
aws-agent --help

# Start the chat server
aws-agent server

# If not available, ensure your Python scripts directory is in PATH
export PATH="$HOME/.local/bin:$PATH"  # Add to ~/.bashrc or ~/.zshrc
```

## Configuration

### 1. OpenAI API Key (REQUIRED)

The agent requires an OpenAI API key to function. Set it up using one of these methods:

```bash
# Method 1: Environment variable (recommended)
export OPENAI_API_KEY="sk-your-api-key-here"

# Method 2: .env file
echo "OPENAI_API_KEY=sk-your-api-key-here" > .env

# Method 3: Pass directly to the agent
aws-agent chat --api-key "sk-your-api-key-here" "List S3 buckets"
```

### 2. AWS Credentials

The agent reads AWS credentials from multiple sources in this order:
1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. AWS credentials file (`~/.aws/credentials`)
3. AWS config file (`~/.aws/config`)
4. IAM roles (when running on EC2/Lambda)
5. Custom configuration file (`aws_config.yml`)

Example AWS credentials setup:
```bash
# Option 1: Use AWS CLI
aws configure

# Option 2: Manual setup
mkdir -p ~/.aws
cat > ~/.aws/credentials << EOF
[default]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY

[prod]
aws_access_key_id = PROD_ACCESS_KEY
aws_secret_access_key = PROD_SECRET_KEY
EOF

cat > ~/.aws/config << EOF
[default]
region = us-east-1

[profile prod]
region = us-west-2
role_arn = arn:aws:iam::123456789012:role/MyRole
source_profile = default
EOF
```

## Usage

### Web Interface (Recommended)

1. Start the chat server using any of these methods:
```bash
# Method 1: Python module
python -m aws_agent.chat

# Method 2: If you created an alias
aws-chat

# Method 3: Using the CLI command
aws-agent server

# Method 4: If you created the shell script
aws-agent-chat
```

2. Open your browser to `http://localhost:8000`

3. Select your AWS profile from the dropdown

4. Start chatting with natural language commands

### Command Line Interface

```bash
# Interactive mode
aws-agent chat

# Single command
aws-agent chat "List all objects in bucket my-bucket"

# Specify profile
aws-agent chat --profile prod "Show S3 buckets"

# File operations
aws-agent transfer s3://bucket/file.txt ~/Downloads/
aws-agent upload ./local-file.txt s3://bucket/path/
```

### Common Operations

#### S3 Operations:
```bash
# List buckets
"list buckets"
"show all S3 buckets"

# List objects
"list objects in my-bucket"
"show files in bucket my-bucket/path/"

# Download files
"download s3://bucket/file.txt to ~/Downloads"
"save objects from bucket/path/ to ~/local-dir"

# Upload files
"upload file.txt to bucket my-bucket"
"copy local-file.txt to s3://bucket/path/"

# Delete objects
"delete file.txt from bucket my-bucket"
"remove s3://bucket/old-file.txt"
```

### Features

#### Command History
- Use UP/DOWN arrow keys to navigate through command history
- History is persisted across sessions
- Last 100 commands are saved

#### Help Section
- Click "Common Operations" in the web interface
- Shows clickable examples of common commands
- Examples auto-populate in the input field

#### Multi-Profile Support
- Switch between AWS profiles in real-time
- No need to restart the server
- Profile dropdown shows all available profiles

## Customization

### Logo Customization

To add your own logo:

1. Place your logo in `/static/images/`
2. Edit `/src/aws_agent/chat/server.py`
3. Update line 115 with your logo filename:
```html
<img src="/static/images/your-logo.png" alt="Your Logo" class="logo-img">
```

### Adding New AWS Services

See [CONTRIBUTING.md](CONTRIBUTING.md) for instructions on extending the agent with new AWS service support.

**⚠️ Security Note**: Never commit API keys or credentials to version control. See [SECURITY.md](SECURITY.md) for security best practices.

## Architecture

The AWS Agent is built with a modular architecture:

```
aws_agent/
├── core/               # Core agent logic
│   ├── agent.py       # Main agent implementation
│   ├── graph.py       # LangGraph workflow
│   └── simple_agent.py # Simplified agent with built-in tools
├── tools/             # AWS service tools
│   └── s3/           # S3-specific tools
│       ├── list_objects.py
│       ├── download_file.py
│       ├── upload_file.py
│       └── file_transfer.py
├── credentials/       # Credential management
│   ├── manager.py    # Main credential manager
│   └── providers.py  # Various credential providers
├── chat/             # Web interface
│   ├── server.py     # FastAPI server
│   └── websocket.py  # WebSocket handling
└── cli/              # Command-line interface
    └── main.py       # CLI entry point
```

### Key Components

- **Core Agent**: LangChain/LangGraph-based reasoning engine with GPT-3.5
- **Tool System**: Specialized tools for each AWS operation
- **Credential Manager**: Secure handling of multiple AWS credential sources
- **Chat Interface**: Real-time WebSocket communication with command history
- **CLI**: Command-line interface for quick operations

## Supported AWS Services

### Currently Supported
- ✅ **S3 (Storage)**: Full support for bucket and object operations
  - List buckets and objects
  - Upload/download files and directories
  - Delete objects
  - Create buckets
  - Bulk file transfers with pattern matching

### Planned Support
- 🔜 EC2 (Compute)
- 🔜 Lambda (Serverless)
- 🔜 DynamoDB (Database)
- 🔜 CloudFormation (Infrastructure)
- 🔜 IAM (Identity Management)

## Troubleshooting

### Common Issues

1. **"OpenAI API key not found"**
   ```bash
   export OPENAI_API_KEY="sk-your-key-here"
   ```

2. **"No AWS credentials found"**
   ```bash
   aws configure
   # or
   export AWS_ACCESS_KEY_ID="your-key"
   export AWS_SECRET_ACCESS_KEY="your-secret"
   ```

3. **"Port 8000 already in use"**
   ```bash
   # Use a different port
   python -m aws_agent.chat --port 8080
   ```

4. **"Module not found"**
   ```bash
   # Ensure you're in the project directory
   cd aws_agent
   pip install -e .
   ```

### Logging

Enable debug logging:
```bash
export AWS_AGENT_LOG_LEVEL=DEBUG
aws-agent chat
```

## Development

### Running Tests
```bash
pytest tests/
```

### Code Style
```bash
# Format code
black src/
# Check linting
flake8 src/
```

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Built with [LangChain](https://langchain.com/) and [LangGraph](https://github.com/langchain-ai/langgraph)
- Powered by OpenAI's GPT-3.5
- NASA logo integration for custom branding
