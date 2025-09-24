#!/usr/bin/env python3
"""
Example Test File

This shows the proper structure for tests in the new testing directory.
"""

import pytest
from testing.test_config import TEST_CONFIG

class TestExample:
    """Example test class showing proper structure."""
    
    def test_basic_functionality(self):
        """Test basic functionality."""
        assert TEST_CONFIG["timeout"] == 30
        assert TEST_CONFIG["log_level"] == "INFO"
    
    @pytest.mark.asyncio
    async def test_async_functionality(self):
        """Test async functionality."""
        # Example async test
        await asyncio.sleep(0.1)
        assert True
    
    def test_with_fixture(self, test_config):
        """Test using pytest fixture."""
        assert test_config["test_mode"] is True

if __name__ == "__main__":
    # Allow running test file directly
    pytest.main([__file__, "-v"])