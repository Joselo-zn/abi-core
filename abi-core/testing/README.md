# ABI Testing Suite

This directory contains all tests for the ABI (Agent-Based Infrastructure) system, organized in a clear and maintainable structure.

## Directory Structure

```
testing/
├── __init__.py                 # Testing package initialization
├── conftest.py                 # Pytest configuration and shared fixtures
├── test_config.py              # Test configuration and path setup
├── run_tests.py                # Main test runner script
├── README.md                   # This file
├── guardial/                   # Guardian agent tests
│   ├── __init__.py
│   ├── test_integration_suite.py
│   ├── test_mcp_integration.py
│   ├── test_policy_system.py
│   ├── test_emergency_response.py
│   ├── test_emergency_monitoring.py
│   ├── test_dashboard_alerting.py
│   └── test_docker_deployment.py
├── integration/                # Cross-agent integration tests
│   └── __init__.py
└── unit/                       # Unit tests for individual components
    └── __init__.py
```

## Running Tests

### Using the Test Runner

```bash
# Run all tests
python testing/run_tests.py

# Run specific test suites
python testing/run_tests.py --guardial      # Guardian agent tests only
python testing/run_tests.py --integration   # Integration tests only
python testing/run_tests.py --unit          # Unit tests only

# Verbose output
python testing/run_tests.py --verbose
```

### Using Pytest Directly

```bash
# Run all tests
pytest testing/

# Run specific test categories
pytest testing/guardial/           # Guardian tests
pytest testing/integration/        # Integration tests
pytest testing/unit/              # Unit tests

# Run specific test files
pytest testing/guardial/test_policy_system.py

# Verbose output
pytest -v testing/
```

## Test Categories

### Guardian Agent Tests (`testing/guardial/`)

Tests specific to the Guardian agent including:

- **Policy System Tests** (`test_policy_system.py`)
  - Core policy generation and validation
  - Policy loading from multiple sources
  - Policy conflict resolution
  - Automatic policy regeneration

- **MCP Integration Tests** (`test_mcp_integration.py`)
  - MCP tool interface testing
  - Semantic signals processing
  - Error handling and graceful degradation
  - Performance and latency testing

- **Emergency Response Tests** (`test_emergency_response.py`)
  - Emergency shutdown procedures
  - Emergency mode operations
  - Administrative overrides
  - Event logging and integrity

- **Dashboard and Alerting Tests** (`test_dashboard_alerting.py`)
  - Dashboard functionality
  - Alert generation and delivery
  - Metrics collection and reporting

- **Docker Deployment Tests** (`test_docker_deployment.py`)
  - Container build and startup
  - Environment configuration
  - Service connectivity

- **Integration Suite** (`test_integration_suite.py`)
  - Comprehensive end-to-end testing
  - Multi-component integration
  - Full workflow validation

### Integration Tests (`testing/integration/`)

Cross-agent integration tests including:
- Multi-agent workflows
- MCP protocol integration
- A2A communication
- Semantic discovery
- End-to-end scenarios

### Unit Tests (`testing/unit/`)

Unit tests for individual components including:
- Agent implementations
- Policy engines
- Semantic layer components
- Utility functions
- Data models

## Test Configuration

### Environment Setup

Tests automatically configure the Python path to include the `abi-core` directory. Import ABI modules normally:

```python
from testing.test_config import TEST_CONFIG
from agents.guardial.agent.guardial_secure import AbiGuardianSecure
```

### Configuration Options

The `test_config.py` file provides common configuration:

```python
TEST_CONFIG = {
    "timeout": 30,
    "log_level": "INFO", 
    "mock_external_services": True,
    "test_data_dir": Path("testing/data"),
    "temp_dir": Path("testing/temp")
}
```

### Fixtures

Common fixtures are available in `conftest.py`:
- `event_loop`: Async event loop for tests
- `test_config`: Test configuration settings
- `mock_opa_server`: Mock OPA server
- `mock_mcp_server`: Mock MCP server

## Writing New Tests

### Test File Naming

- Use `test_` prefix for all test files
- Use descriptive names: `test_policy_validation.py`
- Group related tests in the same file

### Test Structure

```python
#!/usr/bin/env python3
"""
Test Description

Brief description of what this test file covers.
"""

import pytest
from testing.test_config import TEST_CONFIG

class TestClassName:
    """Test class description."""
    
    async def test_specific_functionality(self):
        """Test specific functionality."""
        # Test implementation
        assert True
        
    @pytest.mark.asyncio
    async def test_async_functionality(self):
        """Test async functionality."""
        # Async test implementation
        assert True
```

### Best Practices

1. **Use descriptive test names** that explain what is being tested
2. **Group related tests** in classes
3. **Use fixtures** for common setup/teardown
4. **Mock external dependencies** when appropriate
5. **Test both success and failure cases**
6. **Include performance tests** for critical paths
7. **Document complex test scenarios**

## Continuous Integration

The test suite is designed to run in CI/CD environments:

```bash
# CI command
python testing/run_tests.py --verbose
```

Exit codes:
- `0`: All tests passed
- `1`: One or more tests failed

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure `testing/test_config.py` is imported to set up paths
2. **Async Test Issues**: Use `@pytest.mark.asyncio` for async tests
3. **Mock Setup**: Check that external services are properly mocked
4. **Path Issues**: Verify that the abi-core directory is in the Python path

### Debug Mode

Run tests with verbose output and debug logging:

```bash
python testing/run_tests.py --verbose
pytest -v -s testing/
```

## Contributing

When adding new tests:

1. Place tests in the appropriate category directory
2. Follow the naming conventions
3. Update this README if adding new test categories
4. Ensure tests pass in isolation and as part of the full suite
5. Add appropriate documentation and comments