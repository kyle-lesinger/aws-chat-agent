"""Run the AWS Agent chat server."""

import logging
import sys
from .server import start_server


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


if __name__ == "__main__":
    # Check for --no-browser flag
    no_browser = '--no-browser' in sys.argv
    start_server(no_browser=no_browser)