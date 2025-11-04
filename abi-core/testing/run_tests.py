#!/usr/bin/env python3
"""
ABI Test Runner

Main script to run all ABI tests with proper configuration and reporting.

Usage:
    python testing/run_tests.py                    # Run all tests
    python testing/run_tests.py --guardial         # Run only Guardian tests
    python testing/run_tests.py --integration      # Run only integration tests
    python testing/run_tests.py --unit             # Run only unit tests
    python testing/run_tests.py --verbose          # Verbose output
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add abi-core to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

async def run_guardial_tests():
    """Run Guardian agent tests."""
    logger.info("🛡️ Running Guardian Agent Tests...")
    
    # Import and run Guardian tests
    try:
        from testing.guardial.test_integration_suite import IntegrationTestSuite
        
        test_suite = IntegrationTestSuite()
        success = await test_suite.run_all_tests()
        
        if success:
            logger.info("✅ Guardian tests completed successfully")
        else:
            logger.error("❌ Guardian tests failed")
            
        return success
        
    except Exception as e:
        logger.error(f"❌ Error running Guardian tests: {e}")
        return False

async def run_integration_tests():
    """Run integration tests."""
    logger.info("🔗 Running Integration Tests...")
    
    # Placeholder for integration tests
    logger.info("✅ Integration tests completed (placeholder)")
    return True

async def run_unit_tests():
    """Run unit tests."""
    logger.info("🧪 Running Unit Tests...")
    
    # Placeholder for unit tests
    logger.info("✅ Unit tests completed (placeholder)")
    return True

async def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="ABI Test Runner")
    parser.add_argument("--guardial", action="store_true", help="Run Guardian tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("🚀 Starting ABI Test Suite")
    logger.info("=" * 60)
    
    results = []
    
    # Run specific test suites based on arguments
    if args.guardial:
        results.append(await run_guardial_tests())
    elif args.integration:
        results.append(await run_integration_tests())
    elif args.unit:
        results.append(await run_unit_tests())
    else:
        # Run all tests
        logger.info("🔄 Running all test suites...")
        results.append(await run_guardial_tests())
        results.append(await run_integration_tests())
        results.append(await run_unit_tests())
    
    # Summary
    logger.info("=" * 60)
    total_tests = len(results)
    passed_tests = sum(results)
    failed_tests = total_tests - passed_tests
    
    if failed_tests == 0:
        logger.info(f"✅ All {total_tests} test suites passed!")
        sys.exit(0)
    else:
        logger.error(f"❌ {failed_tests}/{total_tests} test suites failed")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())