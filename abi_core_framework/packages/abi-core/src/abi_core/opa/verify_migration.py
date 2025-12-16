#!/usr/bin/env python3
"""
OPA Migration Verification Script

This script verifies that the OPA files have been successfully moved and 
all dependencies have been updated correctly.
"""

import os
import sys
from pathlib import Path

def verify_opa_migration():
    """Verify the OPA migration was successful"""
    print("🔍 Verifying OPA Migration...")
    
    # Check if new opa directory exists
    opa_dir = Path("./opa")
    if not opa_dir.exists():
        print("❌ OPA directory not found at ./opa")
        return False
    
    print("✅ OPA directory found")
    
    # Check required files
    required_files = [
        "opa.yaml",
        "custom_policies.rego", 
        "config.py",
        "core_policies.py",
        "policy_loader.py",
        "policy_loader_v2.py",
        "__init__.py"
    ]
    
    missing_files = []
    for file in required_files:
        file_path = opa_dir / file
        if not file_path.exists():
            missing_files.append(file)
        else:
            print(f"✅ Found {file}")
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    
    # Test imports
    print("\n🧪 Testing imports...")
    try:
        # Add current directory to path for testing
        sys.path.insert(0, str(Path.cwd()))
        
        from abi_core.opa.config import get_opa_config
        print("✅ Successfully imported opa.config")
        
        from abi_core.opa.policy_loader import PolicyLoader
        print("✅ Successfully imported opa.policy_loader")
        
        from abi_core.opa.policy_loader_v2 import PolicyLoaderV2
        print("✅ Successfully imported opa.policy_loader_v2")
        
        from abi_core.opa.core_policies import CorePolicyGenerator
        print("✅ Successfully imported opa.core_policies")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    
    # Test configuration loading
    print("\n⚙️ Testing configuration...")
    try:
        config = get_opa_config()
        print("✅ Configuration loaded successfully")
        
        # Test that it looks for opa.yaml in the right place
        opa_url = config.get('opa.url')
        if opa_url:
            print(f"✅ OPA URL configured: {opa_url}")
        else:
            print("⚠️ OPA URL not configured")
            
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False
    
    print("\n🎉 OPA Migration Verification Complete!")
    return True

if __name__ == "__main__":
    success = verify_opa_migration()
    sys.exit(0 if success else 1)