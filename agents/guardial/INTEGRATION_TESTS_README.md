# Guardial Integration Tests

This directory contains comprehensive integration tests for the Guardial Agent, validating all aspects of the system from MCP integration to emergency procedures.

## Test Structure

### Task 6.1: MCP Integration Tests (`test_mcp_integration.py`)
Tests the complete MCP flow for guardial.evaluate including:
- ✅ End-to-end MCP tool interface testing
- ✅ Semantic signals integration with policy evaluation
- ✅ GuardialInputV1 processing and GuardialResponse generation
- ✅ Error handling and graceful degradation scenarios
- ✅ Performance tests for evaluation latency and throughput

**Requirements Tested:** 2.1, 2.2, 2.3, 2.4, 4.1, 4.2, 4.3, 4.6

### Task 6.2: Docker Deployment Tests (`test_docker_deployment.py`)
Tests Docker container deployment and startup procedures:
- ✅ Docker container build and startup with corrected main.py
- ✅ Security initialization and policy loading on startup
- ✅ OPA server integration and connectivity
- ✅ Environment variable configuration and policy paths
- ✅ Deployment smoke tests for production readiness

**Requirements Tested:** 1.1, 1.2, 1.3

### Task 6.3: Policy System Validation (`test_policy_system.py`)
Tests the policy system validation including:
- ✅ Core policy generation, validation, and integrity checking
- ✅ Policy loading from multiple sources with correct priorities
- ✅ Policy conflict resolution and core policy protection
- ✅ Automatic policy regeneration on corruption detection
- ✅ Policy system stress tests with large policy sets

**Requirements Tested:** 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 6.1, 6.2, 6.3, 6.4

### Task 6.4: Emergency Procedures and Monitoring (`test_emergency_monitoring.py`)
Tests emergency procedures and monitoring capabilities:
- ✅ Emergency shutdown procedures and system response
- ✅ Audit logging and compliance trace generation
- ✅ Monitoring metrics collection and alerting thresholds
- ✅ Security event detection and response automation
- ✅ Disaster recovery and system restoration tests

**Requirements Tested:** 5.1, 5.2, 5.3, 5.4, 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.3, 8.4

## Running the Tests

### Complete Test Suite
Run all integration tests with the main test runner:

```bash
cd abi-core/agents/guardial
python test_integration_suite.py
```

### Skip Docker Tests
If Docker is not available, skip Docker-specific tests:

```bash
python test_integration_suite.py --skip-docker
```

### Individual Test Modules
Run specific test modules independently:

```bash
# MCP Integration Tests
python test_mcp_integration.py

# Docker Deployment Tests (requires Docker)
python test_docker_deployment.py

# Policy System Validation Tests
python test_policy_system.py

# Emergency Procedures and Monitoring Tests
python test_emergency_monitoring.py
```

## Test Reports

### Console Output
All tests provide detailed console output with:
- ✅ Real-time test progress and results
- 📊 Performance metrics and timing
- 🎯 Requirements validation status
- 🚀 System readiness assessment

### JSON Report
Detailed JSON report is generated at:
- `guardial_integration_test_report.json`

### Log Files
Comprehensive logs are saved to:
- `integration_test_results.log`

## Test Environment

### Prerequisites
- Python 3.8+
- Required Python packages (see requirements.txt)
- Docker (optional, for Docker deployment tests)
- OPA server (automatically started for Docker tests)

### Test Isolation
- Tests use temporary directories for isolation
- Original environment variables are preserved and restored
- No permanent changes to the system

### Mock Dependencies
Tests include mock implementations for:
- External HTTP services
- File system operations
- Network connectivity issues

## Performance Benchmarks

### Expected Performance Metrics
- **MCP Evaluation Latency:** < 1000ms average, < 2000ms P95
- **Policy Loading:** < 30s for 100 policies
- **Emergency Shutdown:** < 10s
- **System Restoration:** < 15s
- **Throughput:** > 5 evaluations/second

### Stress Testing
- Tests with 100+ policies
- Concurrent evaluation scenarios
- High-load monitoring scenarios
- Large audit trail generation

## Security Validation

### Core Policy Protection
- ✅ Core policies cannot be overridden
- ✅ Policy integrity validation with checksums
- ✅ Automatic regeneration on corruption
- ✅ Conflict resolution prioritizes core policies

### Emergency Response
- ✅ Immediate shutdown capabilities
- ✅ Audit trail preservation during emergencies
- ✅ System restoration procedures
- ✅ Administrative override with full audit

### Compliance and Audit
- ✅ Immutable audit logging
- ✅ Cryptographic signatures for integrity
- ✅ Complete compliance trace generation
- ✅ Tamper detection and validation

## Troubleshooting

### Common Issues

#### Docker Tests Failing
```bash
# Check Docker availability
docker --version

# Ensure Docker daemon is running
sudo systemctl start docker

# Run with Docker skip flag if needed
python test_integration_suite.py --skip-docker
```

#### OPA Integration Issues
```bash
# Check OPA server connectivity
curl http://localhost:8181/health

# Verify policy files exist
ls -la policies/
```

#### Permission Issues
```bash
# Ensure proper permissions for test directories
chmod -R 755 /tmp/guardial_*_test_*
```

### Debug Mode
Enable debug logging for detailed troubleshooting:

```bash
export LOG_LEVEL=DEBUG
python test_integration_suite.py
```

## Test Coverage

### Requirements Coverage Matrix

| Requirement | Test Module | Status |
|-------------|-------------|--------|
| 1.1-1.3 | Docker Deployment | ✅ |
| 2.1-2.4 | MCP Integration | ✅ |
| 3.1-3.6 | Policy System | ✅ |
| 4.1-4.6 | MCP Integration | ✅ |
| 5.1-5.4 | Emergency Monitoring | ✅ |
| 6.1-6.4 | Policy System | ✅ |
| 7.1-7.4 | Emergency Monitoring | ✅ |
| 8.1-8.4 | Emergency Monitoring | ✅ |

### System Components Tested

- 🔧 **MCP Tool Interface:** Complete end-to-end testing
- 🛡️ **Policy Engine:** Core generation, validation, loading
- 🔍 **Semantic Integration:** Signal processing and evaluation
- 📋 **Audit System:** Logging, persistence, integrity
- 📊 **Monitoring:** Metrics collection, alerting, dashboards
- 🚨 **Emergency Response:** Shutdown, recovery, overrides
- 🐳 **Container Deployment:** Docker build, startup, health
- ⚙️ **Configuration:** Environment variables, policy paths

## Success Criteria

For the integration tests to pass, all of the following must be validated:

### Functional Requirements
- ✅ MCP tool interface responds correctly to all input scenarios
- ✅ Policy evaluation produces accurate decisions and scores
- ✅ Semantic signals are properly integrated into decisions
- ✅ Audit trails are complete and tamper-evident
- ✅ Emergency procedures execute within time limits
- ✅ System recovery restores full functionality

### Performance Requirements
- ✅ Evaluation latency meets performance targets
- ✅ System handles concurrent requests efficiently
- ✅ Policy loading scales to large policy sets
- ✅ Monitoring systems operate in real-time

### Security Requirements
- ✅ Core policies are protected from override attempts
- ✅ All security events are properly logged and audited
- ✅ Emergency shutdown prevents unauthorized operations
- ✅ System integrity is maintained throughout all operations

## Production Readiness

Upon successful completion of all integration tests, the Guardial Agent is validated as:

🎊 **PRODUCTION READY** 🎊

- ✨ All integration tests passed successfully
- 🛡️ Security systems validated and operational
- 🔧 MCP integration fully functional
- 📊 Monitoring and alerting systems active
- 🚨 Emergency procedures tested and ready
- 🐳 Container deployment validated
- 📋 Compliance and audit systems operational

The system is ready for deployment in production environments with confidence in its security, reliability, and performance characteristics.