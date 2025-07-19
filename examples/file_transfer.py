"""File transfer examples for AWS Agent."""

import asyncio
from pathlib import Path
from aws_agent import AWSAgent, AWSCredentialManager


async def transfer_examples():
    """Demonstrate various file transfer scenarios."""
    
    # Initialize agent
    credential_manager = AWSCredentialManager()
    agent = AWSAgent(credential_manager=credential_manager)
    
    print("AWS Agent File Transfer Examples")
    print("=" * 50)
    
    # Example 1: Upload single file
    print("\n1. Upload single file:")
    response = await agent.arun(
        "Upload /tmp/report.pdf to s3://my-documents/reports/2024/report.pdf"
    )
    print(response)
    
    # Example 2: Download single file
    print("\n2. Download single file:")
    response = await agent.arun(
        "Download s3://my-documents/reports/2024/report.pdf to ./downloads/"
    )
    print(response)
    
    # Example 3: Upload directory
    print("\n3. Upload entire directory:")
    response = await agent.arun(
        "Upload all files from ./data/ to s3://my-bucket/backup/data/ recursively"
    )
    print(response)
    
    # Example 4: Download with pattern
    print("\n4. Download files matching pattern:")
    response = await agent.arun(
        "Download all CSV files from s3://my-data/exports/ to ./csv-files/"
    )
    print(response)
    
    # Example 5: S3 to S3 copy
    print("\n5. Copy between S3 buckets:")
    response = await agent.arun(
        "Copy s3://source-bucket/data/ to s3://backup-bucket/archive/2024/"
    )
    print(response)
    
    # Example 6: Complex transfer with natural language
    print("\n6. Natural language transfer:")
    response = await agent.arun(
        "I need to backup all log files from the last week in ./logs/ to "
        "s3://backup-bucket/logs/week-52/"
    )
    print(response)


async def batch_transfer_example():
    """Example of batch file transfers."""
    
    credential_manager = AWSCredentialManager()
    agent = AWSAgent(credential_manager=credential_manager)
    
    print("\nBatch Transfer Example")
    print("=" * 50)
    
    # Define transfers
    transfers = [
        "Upload ./images/photo1.jpg to s3://media-bucket/photos/",
        "Upload ./images/photo2.jpg to s3://media-bucket/photos/",
        "Upload ./documents/contract.pdf to s3://secure-bucket/contracts/",
        "Download s3://data-bucket/exports/report.xlsx to ./reports/"
    ]
    
    # Execute transfers
    for transfer_cmd in transfers:
        print(f"\nExecuting: {transfer_cmd}")
        response = await agent.arun(transfer_cmd)
        print(f"Result: {response}")


def create_test_files():
    """Create test files for examples."""
    test_dir = Path("./test_files")
    test_dir.mkdir(exist_ok=True)
    
    # Create test files
    (test_dir / "file1.txt").write_text("Test file 1")
    (test_dir / "file2.csv").write_text("col1,col2\ndata1,data2")
    (test_dir / "file3.log").write_text("Log entry 1\nLog entry 2")
    
    # Create subdirectory
    sub_dir = test_dir / "subdir"
    sub_dir.mkdir(exist_ok=True)
    (sub_dir / "nested.txt").write_text("Nested file")
    
    print("Created test files in ./test_files/")


if __name__ == "__main__":
    # Create test files
    create_test_files()
    
    # Run transfer examples
    asyncio.run(transfer_examples())
    
    # Run batch example
    asyncio.run(batch_transfer_example())