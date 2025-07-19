"""Setup script for AWS Agent."""

from setuptools import setup, find_packages

# Read long description from README
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="aws-agent",
    version="0.1.0",
    author="AWS Agent Team",
    author_email="agent@example.com",
    description="Specialized AWS agent built with LangChain/LangGraph for comprehensive AWS operations",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/aws-agent",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
    install_requires=[
        "langchain>=0.1.0",
        "langgraph>=0.0.26",
        "langchain-openai>=0.0.5",
        "langchain-community>=0.0.10",
        "boto3>=1.34.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "python-dotenv>=1.0.0",
        "pyyaml>=6.0",
        "asyncio>=3.4.3",
        "aiofiles>=23.0.0",
        "fastapi>=0.109.0",
        "uvicorn>=0.27.0",
        "websockets>=12.0",
        "httpx>=0.25.0",
        "rich>=13.0.0",
        "click>=8.1.0",
        "keyring>=24.0.0",
        "cryptography>=41.0.0",
    ],
    entry_points={
        "console_scripts": [
            "aws-agent=aws_agent.cli:main",
        ],
    },
)