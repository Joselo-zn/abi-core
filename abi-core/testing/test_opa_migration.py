#!/usr/bin/env python3
"""
OPA Migration Test

This test verifies that the OPA migration was successful and all imports work correctly.
"""

import pytest
import sys
from pathlib import Path

# Add the abi-core directory to Python path
abi_core_path = Path(__file__).parent.parent
sys.path.insert(0, str(abi_core_path))

class TestOPAMigration:
    """Test OPA migration success."""
    
    def test_new_opa_imports(self):
        """Test that new OPA imports work correctly."""
        try:
            # Test new import paths
            from abi_llm_base.opa.config import get_opa_config
            from abi_llm_base.opa.policy_loader import PolicyLoader
            from abi_llm_base.opa.policy_loader_v2 import PolicyLoaderV2
            from abi_llm_base.opa.core_policies import CorePolicyGenerator
            
            # Verify classes can be instantiated
            config = get_opa_config()
            assert config is not None
            
            loader = PolicyLoader()
            assert loader is not None
            
            loader_v2 = PolicyLoaderV2()
            assert loader_v2 is not None
            
            generator = CorePolicyGenerator()
            assert generator is not None
            
        except ImportError as e:
            pytest.fail(f"Failed to import OPA modules: {e}")
    
    def test_old_imports_fail(self):
        """Test that old import paths no longer work."""
        with pytest.raises(ImportError):
            from opa.config import get_opa_config
    
    def test_opa_directory_structure(self):
        """Test that OPA directory has correct structure."""
        opa_dir = Path("agents/abi-llm-base/opa")
        
        # Check directory exists
        assert opa_dir.exists(), "OPA directory not found"
        
        # Check required files exist
        required_files = [
            "__init__.py",
            "config.py", 
            "core_policies.py",
            "policy_loader.py",
            "policy_loader_v2.py",
            "opa.yaml",
            "custom_policies.rego"
        ]
        
        for file in required_files:
            file_path = opa_dir / file
            assert file_path.exists(), f"Required file not found: {file}"
    
    def test_configuration_loading(self):
        """Test that OPA configuration loads from new location."""
        from abi_llm_base.opa.config import get_opa_config
        
        config = get_opa_config()
        
        # Should have default configuration
        assert config.get('opa.url') is not None
        assert config.get('policies.base_path') == './opa'
    
    def test_policy_loading_paths(self):
        """Test that policy loader uses new default paths."""
        from abi_llm_base.opa.policy_loader_v2 import PolicyLoaderV2
        
        loader = PolicyLoaderV2()
        
        # Should use new default path
        assert loader.base_policy_path == "./opa"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])