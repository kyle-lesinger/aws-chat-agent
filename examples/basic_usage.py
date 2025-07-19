"""Basic usage examples for AWS Agent."""

import asyncio
from aws_agent import AWSAgent, AWSCredentialManager


async def main():
    """Run basic AWS Agent examples."""
    
    # Initialize credential manager
    credential_manager = AWSCredentialManager()
    
    # Create agent
    agent = AWSAgent(credential_manager=credential_manager)
    
    print("AWS Agent Examples")
    print("=" * 50)
    
    # Example 1: List S3 buckets
    print("\n1. Listing S3 buckets:")
    response = await agent.arun("List all my S3 buckets")
    print(response)
    
    # Example 2: Get specific bucket contents
    print("\n2. List objects in a bucket:")
    response = await agent.arun("Show me what's in my-bucket")
    print(response)
    
    # Example 3: Upload a file
    print("\n3. Upload a file:")
    response = await agent.arun("Upload /tmp/test.txt to s3://my-bucket/test.txt")
    print(response)
    
    # Example 4: Download a file
    print("\n4. Download a file:")
    response = await agent.arun("Download s3://my-bucket/data.csv to ./downloads/")
    print(response)
    
    # Example 5: Switch profiles
    print("\n5. Switch AWS profile:")
    if "production" in agent.get_available_profiles():
        agent.set_profile("production")
        response = await agent.arun("What profile am I using now?")
        print(response)
    
    # Example 6: Get operation history
    print("\n6. Operation history:")
    history = agent.get_history()
    print(f"Performed {len(history)} operations")
    for op in history[-3:]:  # Show last 3 operations
        print(f"  - {op['service']}: {op['action']} ({'success' if op['success'] else 'failed'})")


def sync_example():
    """Synchronous usage example."""
    credential_manager = AWSCredentialManager()
    agent = AWSAgent(credential_manager=credential_manager)
    
    # Synchronous call
    response = agent.run("List my S3 buckets")
    print(response)


if __name__ == "__main__":
    # Run async examples
    asyncio.run(main())
    
    # Run sync example
    print("\n" + "=" * 50)
    print("Synchronous example:")
    sync_example()