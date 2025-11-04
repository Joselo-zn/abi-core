"""
Test Configuration and Path Setup

This module sets up the Python path and provides common configuration
for all ABI tests.
"""

import sys
from pathlib import Path

# Add abi-core directory to Python path
ABI_CORE_PATH = Path(__file__).parent.parent
sys.path.insert(0, str(ABI_CORE_PATH))

# Test configuration
TEST_CONFIG = {
    "timeout": 30,
    "log_level": "INFO",
    "mock_external_services": True,
    "test_data_dir": Path(__file__).parent / "data",
    "temp_dir": Path(__file__).parent / "temp"
}

# Ensure test directories exist
TEST_CONFIG["test_data_dir"].mkdir(exist_ok=True)
TEST_CONFIG["temp_dir"].mkdir(exist_ok=True)