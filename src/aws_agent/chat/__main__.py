"""Run the AWS Agent chat server."""

import logging
from .server import start_server


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


if __name__ == "__main__":
    start_server()