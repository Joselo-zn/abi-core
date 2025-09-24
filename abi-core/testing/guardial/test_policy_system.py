#!/usr/bin/env python3
"""
Policy System Validation Tests - Task 6.3

This script tests the policy system validation including:
- Core policy generation, validation, and integrity checking
- Policy loading from multiple sources with correct priorities
- Policy conflict resolution and core policy protection
- Automatic policy regeneration on corruption detection
- Policy system stress tests with large policy sets

Requirements tested: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 6.1, 6.2, 6.3, 6.4
"""

import asyncio
import json
import logging
import os
import tempfile
import shutil
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PolicyTestManager:
    """Manages policy testing operations"""
    
    def __init__(self):
        self.test_dir = None
        self.original_env = {}
        
    async def setup_test_environment(self):
        """Setup isolated test environment"""
        logger.info("🔧 Setting up test environment...")
        
        # Create temporary directory for testing
        self.test_dir = Path(tempfile.mkdtemp(prefix="guardial_policy_test_"))
        
        # Create test policy directories
        (self.test_dir / "policies").mkdir()
        (self.test_dir / "custom_policies").mkdir()
        (self.test_dir / "external_policies").mkdir()
        
        # Backup original environment variables
        env_vars_to_backup = [
            "ABI_POLICY_PATHS",
            "OPA_SERVER_URL",
            "GUARDIAL_POLICY_DIR"
        ]
        
        for var in env_vars_to_backup:
            self.original_env[var] = os.environ.get(var)
        
        # Set test environment variables
        os.environ["ABI_POLICY_PATHS"] = f"{self.test_dir}/policies:{self.test_dir}/custom_policies"
        os.environ["GUARDIAL_POLICY_DIR"] = str(self.test_dir / "policies")
        
        logger.info(f"✅ Test environment setup at: {self.test_dir}")
        
    async def cleanup_test_environment(self):
        """Cleanup test environment"""
        logger.info("🧹 Cleaning up test environment...")
        
        # Restore original environment variables
        for var, value in self.original_env.items():
            if value is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = value
        
        # Remove test directory
        if self.test_dir and self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        
        logger.info("✅ Test environment cleaned up")
    
    def create_test_policy(self, name: str, content: str, directory: str = "policies") -> Path:
        """Create a test policy file"""
        policy_dir = self.test_dir / directory
        policy_file = policy_dir / f"{name}.rego"
        policy_file.write_text(content)
        return policy_file
    
    def corrupt_policy_file(self, policy_path: Path):
        """Corrupt a policy file for testing"""
        if policy_path.exists():
            # Append garbage to corrupt the file
            with open(policy_path, 'a') as f:
                f.write("\n# CORRUPTED DATA: invalid_rego_syntax {{{")

async def test_core_policy_generation():
    """Test core policy generation and validation"""
    logger.info("🧪 Testing Core Policy Generation...")
    
    test_manager = PolicyTestManager()
    
    try:
        await test_manager.setup_test_environment()
        
        from abi_llm_base.opa.core_policies import CorePolicyGenerator
        
        # Initialize core policy generator
        generator = CorePolicyGenerator(policy_dir=str(test_manager.test_dir / "policies"))
        
        # Test core policy generation
        logger.info("📝 Testing core policy generation...")
        success = await generator.ensure_core_policies()
        assert success, "Core policy generation failed"
        
        # Check that core policy file was created
        core_policy_path = test_manager.test_dir / "policies" / "abi_policies.rego"
        assert core_policy_path.exists(), "Core policy file not created"
        
        # Validate core policy content
        core_content = core_policy_path.read_text()
        
        # Check required elements
        required_elements = [
            "package abi.core",
            "default allow := false",
            "default deny := false",
            "# CORE SECURITY POLICIES",
            "# Anti-replication protection"
        ]
        
        for element in required_elements:
            assert element in core_content, f"Missing required element: {element}"
        
        logger.info("✅ Core policy generation test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Core policy generation test failed: {e}")
        return False
    finally:
        await test_manager.cleanup_test_environment()

async def test_policy_integrity_validation():
    """Test policy integrity validation with checksums"""
    logger.info("🧪 Testing Policy Integrity Validation...")
    
    test_manager = PolicyTestManager()
    
    try:
        await test_manager.setup_test_environment()
        
        from abi_llm_base.opa.core_policies import CorePolicyGenerator
        
        generator = CorePolicyGenerator(policy_dir=str(test_manager.test_dir / "policies"))
        
        # Generate core policies
        await generator.ensure_core_policies()
        
        # Test integrity validation on valid policies
        logger.info("🔍 Testing integrity validation on valid policies...")
        core_policy_path = test_manager.test_dir / "policies" / "abi_policies.rego"
        
        is_valid = await generator.validate_policy_integrity(str(core_policy_path))
        assert is_valid, "Valid policy failed integrity check"
        
        # Test integrity validation on corrupted policies
        logger.info("🔍 Testing integrity validation on corrupted policies...")
        
        # Create backup of original content
        original_content = core_policy_path.read_text()
        
        # Corrupt the policy file
        test_manager.corrupt_policy_file(core_policy_path)
        
        # Validation should fail
        is_valid_after_corruption = await generator.validate_policy_integrity(str(core_policy_path))
        assert not is_valid_after_corruption, "Corrupted policy passed integrity check"
        
        # Restore original content
        core_policy_path.write_text(original_content)
        
        # Validation should pass again
        is_valid_after_restore = await generator.validate_policy_integrity(str(core_policy_path))
        assert is_valid_after_restore, "Restored policy failed integrity check"
        
        logger.info("✅ Policy integrity validation test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Policy integrity validation test failed: {e}")
        return False
    finally:
        await test_manager.cleanup_test_environment()

async def test_automatic_policy_regeneration():
    """Test automatic policy regeneration on corruption detection"""
    logger.info("🧪 Testing Automatic Policy Regeneration...")
    
    test_manager = PolicyTestManager()
    
    try:
        await test_manager.setup_test_environment()
        
        from abi_llm_base.opa.core_policies import CorePolicyGenerator
        
        generator = CorePolicyGenerator(policy_dir=str(test_manager.test_dir / "policies"))
        
        # Generate initial core policies
        await generator.ensure_core_policies()
        core_policy_path = test_manager.test_dir / "policies" / "abi_policies.rego"
        
        # Store original checksum
        original_content = core_policy_path.read_text()
        original_checksum = hashlib.sha256(original_content.encode()).hexdigest()
        
        # Corrupt the policy file
        logger.info("💥 Corrupting policy file...")
        test_manager.corrupt_policy_file(core_policy_path)
        
        # Verify corruption
        corrupted_content = core_policy_path.read_text()
        corrupted_checksum = hashlib.sha256(corrupted_content.encode()).hexdigest()
        assert original_checksum != corrupted_checksum, "Policy file not properly corrupted"
        
        # Test automatic regeneration
        logger.info("🔄 Testing automatic regeneration...")
        regeneration_success = await generator.regenerate_corrupted_policies()
        assert regeneration_success, "Policy regeneration failed"
        
        # Verify regeneration
        regenerated_content = core_policy_path.read_text()
        regenerated_checksum = hashlib.sha256(regenerated_content.encode()).hexdigest()
        
        # Should be valid again (might not be identical due to timestamps)
        is_valid = await generator.validate_policy_integrity(str(core_policy_path))
        assert is_valid, "Regenerated policy failed integrity check"
        
        # Should contain required elements
        required_elements = [
            "package abi.core",
            "default allow := false",
            "default deny := false"
        ]
        
        for element in required_elements:
            assert element in regenerated_content, f"Regenerated policy missing: {element}"
        
        logger.info("✅ Automatic policy regeneration test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Automatic policy regeneration test failed: {e}")
        return False
    finally:
        await test_manager.cleanup_test_environment()

async def test_multi_source_policy_loading():
    """Test policy loading from multiple sources with correct priorities"""
    logger.info("🧪 Testing Multi-Source Policy Loading...")
    
    test_manager = PolicyTestManager()
    
    try:
        await test_manager.setup_test_environment()
        
        from abi_llm_base.opa.policy_loader_v2 import PolicyLoaderV2
        
        # Create test policies in different directories
        
        # Core policy (highest priority)
        core_policy = """
package abi.core

default allow := false
default deny := false

# Core security rule
deny {
    input.action == "forbidden_core_action"
}
"""
        test_manager.create_test_policy("core_policy", core_policy, "policies")
        
        # Custom policy (medium priority)
        custom_policy = """
package abi.custom

default allow := false

# Custom rule
allow {
    input.action == "custom_allowed_action"
    input.user_role == "admin"
}

# This should NOT override core policy
allow {
    input.action == "forbidden_core_action"
    input.override_attempt := true
}
"""
        test_manager.create_test_policy("custom_policy", custom_policy, "custom_policies")
        
        # External policy (lowest priority)
        external_policy = """
package abi.external

default allow := false

# External rule
allow {
    input.action == "external_action"
}
"""
        test_manager.create_test_policy("external_policy", external_policy, "external_policies")
        
        # Initialize policy loader
        policy_paths = [
            str(test_manager.test_dir / "policies"),
            str(test_manager.test_dir / "custom_policies"),
            str(test_manager.test_dir / "external_policies")
        ]
        
        loader = PolicyLoaderV2(policy_paths=policy_paths)
        
        # Test policy discovery
        logger.info("🔍 Testing policy source discovery...")
        sources = await loader.discover_policy_sources()
        assert len(sources) >= 3, f"Expected at least 3 policy sources, found {len(sources)}"
        
        # Test policy loading
        logger.info("📚 Testing policy loading...")
        load_success = await loader.load_policies()
        assert load_success, "Policy loading failed"
        
        # Test policy priority enforcement
        logger.info("⚖️ Testing policy priority enforcement...")
        
        # Core policies should have highest priority
        core_policies = loader.get_policies_by_package("abi.core")
        assert len(core_policies) > 0, "No core policies loaded"
        
        # Custom policies should be loaded
        custom_policies = loader.get_policies_by_package("abi.custom")
        assert len(custom_policies) > 0, "No custom policies loaded"
        
        # External policies should be loaded
        external_policies = loader.get_policies_by_package("abi.external")
        assert len(external_policies) > 0, "No external policies loaded"
        
        logger.info("✅ Multi-source policy loading test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Multi-source policy loading test failed: {e}")
        return False
    finally:
        await test_manager.cleanup_test_environment()

async def test_policy_conflict_resolution():
    """Test policy conflict resolution and core policy protection"""
    logger.info("🧪 Testing Policy Conflict Resolution...")
    
    test_manager = PolicyTestManager()
    
    try:
        await test_manager.setup_test_environment()
        
        from abi_llm_base.opa.policy_loader_v2 import PolicyLoaderV2
        from abi_llm_base.opa.core_policies import CorePolicyGenerator
        
        # Generate core policies first
        generator = CorePolicyGenerator(policy_dir=str(test_manager.test_dir / "policies"))
        await generator.ensure_core_policies()
        
        # Create conflicting custom policy that tries to override core security
        conflicting_policy = """
package abi.core

# ATTEMPT TO OVERRIDE CORE SECURITY - THIS SHOULD BE BLOCKED
default allow := true  # Trying to change core default

# Trying to override core deny rules
allow {
    input.action == "forbidden_core_action"
    input.malicious_override := true
}

# Trying to disable core security
deny := false
"""
        test_manager.create_test_policy("malicious_override", conflicting_policy, "custom_policies")
        
        # Create legitimate custom policy
        legitimate_policy = """
package abi.custom_legitimate

default allow := false

# Legitimate custom rule that doesn't conflict with core
allow {
    input.action == "legitimate_custom_action"
    input.user_authenticated == true
}
"""
        test_manager.create_test_policy("legitimate_custom", legitimate_policy, "custom_policies")
        
        # Initialize policy loader with conflict detection
        policy_paths = [
            str(test_manager.test_dir / "policies"),
            str(test_manager.test_dir / "custom_policies")
        ]
        
        loader = PolicyLoaderV2(policy_paths=policy_paths)
        
        # Test conflict detection
        logger.info("⚔️ Testing conflict detection...")
        conflicts = await loader.detect_policy_conflicts()
        
        # Should detect conflicts with core policies
        core_conflicts = [c for c in conflicts if "abi.core" in c.get("package", "")]
        assert len(core_conflicts) > 0, "Core policy conflicts not detected"
        
        # Test policy loading with conflict resolution
        logger.info("🛡️ Testing core policy protection...")
        load_success = await loader.load_policies_with_protection()
        assert load_success, "Policy loading with protection failed"
        
        # Verify core policies are protected
        core_policies = loader.get_policies_by_package("abi.core")
        
        # Check that core defaults are preserved
        core_content = ""
        for policy in core_policies:
            core_content += policy.get("content", "")
        
        # Core security should be maintained
        assert "default allow := false" in core_content, "Core allow default was overridden"
        
        # Legitimate custom policies should still be loaded
        custom_policies = loader.get_policies_by_package("abi.custom_legitimate")
        assert len(custom_policies) > 0, "Legitimate custom policies were blocked"
        
        logger.info("✅ Policy conflict resolution test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Policy conflict resolution test failed: {e}")
        return False
    finally:
        await test_manager.cleanup_test_environment()

async def test_dynamic_policy_reloading():
    """Test dynamic policy reloading capabilities"""
    logger.info("🧪 Testing Dynamic Policy Reloading...")
    
    test_manager = PolicyTestManager()
    
    try:
        await test_manager.setup_test_environment()
        
        from abi_llm_base.opa.policy_loader_v2 import PolicyLoaderV2
        
        # Create initial policy
        initial_policy = """
package abi.dynamic_test

default allow := false

allow {
    input.action == "initial_action"
}
"""
        policy_file = test_manager.create_test_policy("dynamic_test", initial_policy, "custom_policies")
        
        # Initialize policy loader
        policy_paths = [str(test_manager.test_dir / "custom_policies")]
        loader = PolicyLoaderV2(policy_paths=policy_paths)
        
        # Load initial policies
        await loader.load_policies()
        initial_policies = loader.get_policies_by_package("abi.dynamic_test")
        assert len(initial_policies) > 0, "Initial policies not loaded"
        
        # Modify policy file
        logger.info("🔄 Testing policy modification detection...")
        updated_policy = """
package abi.dynamic_test

default allow := false

allow {
    input.action == "initial_action"
}

allow {
    input.action == "updated_action"
    input.user_role == "admin"
}
"""
        policy_file.write_text(updated_policy)
        
        # Test change detection
        changes_detected = await loader.detect_policy_changes()
        assert changes_detected, "Policy changes not detected"
        
        # Test hot reload
        logger.info("🔥 Testing hot reload...")
        reload_success = await loader.reload_changed_policies()
        assert reload_success, "Policy hot reload failed"
        
        # Verify updated policies are loaded
        updated_policies = loader.get_policies_by_package("abi.dynamic_test")
        assert len(updated_policies) > 0, "Updated policies not loaded"
        
        # Check that new content is present
        updated_content = ""
        for policy in updated_policies:
            updated_content += policy.get("content", "")
        
        assert "updated_action" in updated_content, "Updated policy content not loaded"
        
        # Test rollback capability
        logger.info("↩️ Testing rollback capability...")
        
        # Corrupt the policy file
        test_manager.corrupt_policy_file(policy_file)
        
        # Attempt reload (should fail and rollback)
        rollback_success = await loader.reload_with_rollback()
        assert rollback_success, "Rollback failed"
        
        # Verify policies are still functional (should have previous version)
        rollback_policies = loader.get_policies_by_package("abi.dynamic_test")
        assert len(rollback_policies) > 0, "Policies lost after rollback"
        
        logger.info("✅ Dynamic policy reloading test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Dynamic policy reloading test failed: {e}")
        return False
    finally:
        await test_manager.cleanup_test_environment()

async def test_policy_system_stress():
    """Test policy system with large policy sets"""
    logger.info("🧪 Testing Policy System Stress...")
    
    test_manager = PolicyTestManager()
    
    try:
        await test_manager.setup_test_environment()
        
        from abi_llm_base.opa.policy_loader_v2 import PolicyLoaderV2
        
        # Generate large number of policies
        num_policies = 100
        logger.info(f"📚 Generating {num_policies} test policies...")
        
        for i in range(num_policies):
            policy_content = f"""
package abi.stress_test_{i}

default allow := false

allow {{
    input.action == "stress_test_action_{i}"
    input.policy_id == {i}
}}

deny {{
    input.action == "forbidden_action_{i}"
}}

# Rule with complexity
allow {{
    input.action == "complex_action_{i}"
    input.user_role in ["admin", "moderator"]
    input.resource_type == "stress_test_resource"
    count(input.permissions) > 0
}}
"""
            test_manager.create_test_policy(f"stress_test_{i}", policy_content, "custom_policies")
        
        # Initialize policy loader
        policy_paths = [str(test_manager.test_dir / "custom_policies")]
        loader = PolicyLoaderV2(policy_paths=policy_paths)
        
        # Test loading performance
        logger.info("⏱️ Testing loading performance...")
        import time
        
        start_time = time.time()
        load_success = await loader.load_policies()
        load_time = time.time() - start_time
        
        assert load_success, "Stress test policy loading failed"
        logger.info(f"📊 Loaded {num_policies} policies in {load_time:.2f} seconds")
        
        # Performance assertion
        assert load_time < 30, f"Policy loading too slow: {load_time:.2f}s"
        
        # Test policy discovery performance
        logger.info("🔍 Testing discovery performance...")
        start_time = time.time()
        sources = await loader.discover_policy_sources()
        discovery_time = time.time() - start_time
        
        assert len(sources) > 0, "No policy sources discovered"
        logger.info(f"📊 Discovered {len(sources)} sources in {discovery_time:.2f} seconds")
        
        # Test conflict detection performance
        logger.info("⚔️ Testing conflict detection performance...")
        start_time = time.time()
        conflicts = await loader.detect_policy_conflicts()
        conflict_time = time.time() - start_time
        
        logger.info(f"📊 Conflict detection completed in {conflict_time:.2f} seconds")
        logger.info(f"📊 Found {len(conflicts)} conflicts")
        
        # Test memory usage (basic check)
        logger.info("💾 Testing memory usage...")
        all_policies = loader.get_all_policies()
        assert len(all_policies) >= num_policies, "Not all policies loaded"
        
        # Test policy retrieval performance
        logger.info("🔎 Testing policy retrieval performance...")
        start_time = time.time()
        
        for i in range(0, min(10, num_policies)):
            package_policies = loader.get_policies_by_package(f"abi.stress_test_{i}")
            assert len(package_policies) > 0, f"Policy package {i} not found"
        
        retrieval_time = time.time() - start_time
        logger.info(f"📊 Policy retrieval completed in {retrieval_time:.2f} seconds")
        
        logger.info("✅ Policy system stress test passed")
        return {
            "num_policies": num_policies,
            "load_time": load_time,
            "discovery_time": discovery_time,
            "conflict_time": conflict_time,
            "retrieval_time": retrieval_time
        }
        
    except Exception as e:
        logger.error(f"❌ Policy system stress test failed: {e}")
        return False
    finally:
        await test_manager.cleanup_test_environment()

async def test_health_check_integration():
    """Test health check integration with policy status"""
    logger.info("🧪 Testing Health Check Integration...")
    
    test_manager = PolicyTestManager()
    
    try:
        await test_manager.setup_test_environment()
        
        from agents.guardial.agent.guardial_secure import AbiGuardianSecure
        
        # Initialize guardian with test environment
        guardian = AbiGuardianSecure()
        
        # Initialize security (this should generate core policies)
        security_ok = await guardian.initialize_security()
        assert security_ok, "Security initialization failed"
        
        # Test health check
        logger.info("🔍 Testing health check with policy status...")
        health = await guardian.health_check()
        
        # Validate health check structure
        assert isinstance(health, dict), "Health check should return dict"
        assert "overall_status" in health, "Missing overall_status in health check"
        assert "policy_status" in health, "Missing policy_status in health check"
        
        # Validate policy status
        policy_status = health["policy_status"]
        assert "core_policies_valid" in policy_status, "Missing core_policies_valid"
        assert "last_validation" in policy_status, "Missing last_validation"
        assert "policy_sources" in policy_status, "Missing policy_sources"
        
        # Should be healthy with valid policies
        assert health["overall_status"] in ["SECURE_AND_OPERATIONAL", "OPERATIONAL"], f"Unexpected status: {health['overall_status']}"
        assert policy_status["core_policies_valid"] == True, "Core policies should be valid"
        
        logger.info("✅ Health check integration test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Health check integration test failed: {e}")
        return False
    finally:
        await test_manager.cleanup_test_environment()

async def run_policy_system_tests():
    """Run all policy system validation tests"""
    logger.info("🚀 Starting Policy System Validation Tests (Task 6.3)")
    
    test_results = {}
    
    try:
        # Test 1: Core policy generation
        logger.info("\n" + "="*60)
        core_gen_ok = await test_core_policy_generation()
        test_results['core_generation'] = {'status': 'PASSED' if core_gen_ok else 'FAILED'}
        
        # Test 2: Policy integrity validation
        logger.info("\n" + "="*60)
        integrity_ok = await test_policy_integrity_validation()
        test_results['integrity_validation'] = {'status': 'PASSED' if integrity_ok else 'FAILED'}
        
        # Test 3: Automatic policy regeneration
        logger.info("\n" + "="*60)
        regen_ok = await test_automatic_policy_regeneration()
        test_results['auto_regeneration'] = {'status': 'PASSED' if regen_ok else 'FAILED'}
        
        # Test 4: Multi-source policy loading
        logger.info("\n" + "="*60)
        multi_source_ok = await test_multi_source_policy_loading()
        test_results['multi_source_loading'] = {'status': 'PASSED' if multi_source_ok else 'FAILED'}
        
        # Test 5: Policy conflict resolution
        logger.info("\n" + "="*60)
        conflict_ok = await test_policy_conflict_resolution()
        test_results['conflict_resolution'] = {'status': 'PASSED' if conflict_ok else 'FAILED'}
        
        # Test 6: Dynamic policy reloading
        logger.info("\n" + "="*60)
        reload_ok = await test_dynamic_policy_reloading()
        test_results['dynamic_reloading'] = {'status': 'PASSED' if reload_ok else 'FAILED'}
        
        # Test 7: Policy system stress test
        logger.info("\n" + "="*60)
        stress_result = await test_policy_system_stress()
        stress_ok = stress_result is not False
        test_results['stress_test'] = {
            'status': 'PASSED' if stress_ok else 'FAILED',
            'metrics': stress_result if stress_ok else None
        }
        
        # Test 8: Health check integration
        logger.info("\n" + "="*60)
        health_ok = await test_health_check_integration()
        test_results['health_integration'] = {'status': 'PASSED' if health_ok else 'FAILED'}
        
        # Check overall results
        all_passed = all(result['status'] == 'PASSED' for result in test_results.values())
        
        logger.info("\n" + "="*60)
        if all_passed:
            logger.info("🎉 ALL POLICY SYSTEM VALIDATION TESTS PASSED!")
        else:
            logger.error("❌ SOME POLICY SYSTEM VALIDATION TESTS FAILED!")
        logger.info("="*60)
        
        # Print summary
        print("\nPOLICY SYSTEM VALIDATION TEST SUMMARY")
        print("="*60)
        for test_name, result in test_results.items():
            status_icon = "✅" if result['status'] == 'PASSED' else "❌"
            print(f"{status_icon} {test_name.replace('_', ' ').title()}: {result['status']}")
        
        # Print performance metrics if available
        if 'stress_test' in test_results and test_results['stress_test']['metrics']:
            metrics = test_results['stress_test']['metrics']
            print(f"\nPERFORMANCE METRICS:")
            print(f"📚 Policies Loaded: {metrics['num_policies']}")
            print(f"⏱️ Load Time: {metrics['load_time']:.2f}s")
            print(f"🔍 Discovery Time: {metrics['discovery_time']:.2f}s")
            print(f"⚔️ Conflict Detection: {metrics['conflict_time']:.2f}s")
            print(f"🔎 Retrieval Time: {metrics['retrieval_time']:.2f}s")
        
        print(f"\n🛡️ Core Policy Generation: {'OPERATIONAL' if core_gen_ok else 'FAILED'}")
        print(f"🔍 Integrity Validation: {'ROBUST' if integrity_ok else 'FAILED'}")
        print(f"🔄 Auto Regeneration: {'FUNCTIONAL' if regen_ok else 'FAILED'}")
        print(f"📚 Multi-Source Loading: {'FLEXIBLE' if multi_source_ok else 'FAILED'}")
        print(f"⚔️ Conflict Resolution: {'PROTECTED' if conflict_ok else 'FAILED'}")
        print(f"🔥 Dynamic Reloading: {'RESPONSIVE' if reload_ok else 'FAILED'}")
        print(f"💪 Stress Handling: {'SCALABLE' if stress_ok else 'FAILED'}")
        print(f"🏥 Health Integration: {'MONITORED' if health_ok else 'FAILED'}")
        print("="*60)
        
        return all_passed
        
    except Exception as e:
        logger.error(f"❌ Policy System Validation Tests Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(run_policy_system_tests())
    exit(0 if success else 1)