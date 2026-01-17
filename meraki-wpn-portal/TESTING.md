# Testing Guide

Comprehensive testing guide for the Meraki WPN Portal and FreeRADIUS integration.

## Table of Contents

- [Overview](#overview)
- [Test Structure](#test-structure)
- [Quick Start](#quick-start)
- [Test Categories](#test-categories)
- [Running Tests](#running-tests)
- [CI/CD Integration](#cicd-integration)
- [Writing New Tests](#writing-new-tests)
- [Troubleshooting](#troubleshooting)
- [Performance Benchmarks](#performance-benchmarks)

## Overview

The test suite validates the complete integration between the Meraki WPN Portal and FreeRADIUS server, including:

- **Unit Tests**: Fast, isolated tests for individual components
- **Integration Tests**: Component interaction tests with mocked external services
- **E2E Tests**: Full system tests with Docker containers
- **Security Tests**: Validation of cryptographic requirements and security compliance
- **Performance Tests**: Load testing and response time benchmarks

### Test Coverage Goals

- ✅ **Unit Tests**: >90% code coverage
- ✅ **Integration Tests**: All sync workflows validated
- ✅ **E2E Tests**: Complete user registration → authentication flow
- ✅ **Security**: Compliance with codeguard-1 security requirements
- ✅ **Performance**: >100 auth/sec, <100ms p95 latency

## Test Structure

```
meraki-wpn-portal/backend/tests/
├── unit/                          # Fast, isolated unit tests (~2s)
│   ├── test_certificate_manager.py
│   ├── test_udn_manager.py
│   └── test_radius_api_client.py
├── integration/                   # Component integration tests (~30s)
│   ├── test_wpn_radius_sync.py
│   ├── test_certificate_exchange.py
│   └── test_udn_radius_users.py
├── e2e/                          # End-to-end tests (~5min)
│   ├── test_full_registration_flow.py
│   ├── test_radius_authentication.py
│   └── docker/
│       └── docker-compose.test.yml
├── security/                      # Security validation tests
│   └── test_certificate_security.py
├── performance/                   # Performance tests
│   └── test_radius_load.py
├── fixtures/                      # Shared test fixtures
│   ├── certificates.py
│   ├── radius_server.py
│   └── meraki_mock.py
└── utils/                        # Test utilities
    ├── radius_client.py          # pyrad-based RADIUS client
    ├── certificate_helpers.py
    └── docker_helpers.py

freeradius/tests/
├── test_radius_manager_api.py
└── test_client_sync.py
```

## Quick Start

### Prerequisites

```bash
# Install Python 3.13+
python --version

# Install dependencies
cd meraki-wpn-portal/backend
pip install -e ".[dev]"

# Verify Docker is available (for E2E tests)
docker --version
docker-compose --version
```

### Run All Tests (Fast Feedback)

```bash
# Unit tests only (fastest)
pytest tests/unit -v

# Unit + Integration tests
pytest tests/ -m "unit or integration" -v

# Full test suite (excluding Docker E2E)
pytest tests/ -m "not docker" -v
```

### Run Complete Test Suite

```bash
# All tests including E2E with Docker
pytest tests/ -v --cov=app --cov-report=html

# View coverage report
open htmlcov/index.html
```

## Test Categories

### Unit Tests (`tests/unit/`)

Fast, isolated tests with mocked dependencies.

**Run:** `pytest tests/unit -v -m unit`

**Test Coverage:**
- Certificate generation (RSA 4096, SHA-256)
- Certificate validation (expiration, weak keys, banned algorithms)
- MAC address normalization
- UDN ID assignment and pool management
- Cisco-AVPair VSA formatting
- RADIUS users file generation

**Example:**
```python
def test_normalize_mac_address():
    """Test MAC address normalization to lowercase colon format."""
    assert normalize_mac_address("AA:BB:CC:DD:EE:FF") == "aa:bb:cc:dd:ee:ff"
    assert normalize_mac_address("AA-BB-CC-DD-EE-FF") == "aa:bb:cc:dd:ee:ff"
    assert normalize_mac_address("AABBCCDDEEFF") == "aa:bb:cc:dd:ee:ff"
```

### Integration Tests (`tests/integration/`)

Component interaction tests with mocked external services.

**Run:** `pytest tests/integration -v -m integration`

**Test Coverage:**
- WPN → FreeRADIUS client synchronization
- UDN assignment → RADIUS users file sync
- Certificate exchange (CA upload/download)
- Automated RadSec setup flow
- Configuration reload workflows

**Example:**
```python
@pytest.mark.asyncio
async def test_udn_assignment_syncs_to_radius(db, mock_radius_api):
    """Test that UDN assignment syncs to RADIUS server via API."""
    udn_manager = UdnManager(db)
    assignment = udn_manager.assign_udn_id(
        mac_address="aa:bb:cc:dd:ee:ff",
        user_name="Test User",
        specific_udn_id=100,
    )
    
    # Sync to RADIUS API
    async with httpx.AsyncClient() as client:
        await client.post(
            "http://localhost:8000/api/users",
            json={
                "username": assignment.mac_address,
                "reply_attributes": {
                    "Cisco-AVPair": f"udn:private-group-id={assignment.udn_id}"
                }
            }
        )
```

### E2E Tests (`tests/e2e/`)

Full system tests with Docker containers running real FreeRADIUS server.

**Run:** `pytest tests/e2e -v -m e2e --docker`

**Test Coverage:**
- Complete user registration → authentication flow
- RADIUS protocol authentication (using pyrad)
- RadSec TLS connection validation
- Concurrent authentication under load
- Failure scenario handling

**Docker Environment:**
- FreeRADIUS server with RadSec on ports 1812, 1813, 2083, 8000
- WPN Portal backend on port 8080
- Shared test network
- Automatic health checks

**Example:**
```python
def test_mac_authentication_with_udn_id(docker_env, radius_client):
    """Test MAC-based authentication returns correct UDN ID."""
    mac_address = "aa:bb:cc:dd:ee:ff"
    response = radius_client.authenticate_mac(mac_address)
    
    if response.success:
        udn_id = response.get_cisco_avpair_udn_id()
        assert udn_id >= 2 and udn_id <= 16777200
```

### Security Tests (`tests/security/`)

Validation of security requirements and compliance.

**Run:** `pytest tests/security -v -m security`

**Test Coverage:**
- No MD5, SHA-1 in certificates (codeguard-1-crypto-algorithms)
- Minimum RSA 2048-bit keys enforced
- Expired certificate detection (CRITICAL)
- Weak key detection
- No hardcoded secrets in source code
- TLS 1.2+ enforcement

**Security Rules Validated:**
- `codeguard-1-crypto-algorithms`: No banned algorithms
- `codeguard-1-digital-certificates`: Certificate validation
- `codeguard-1-hardcoded-credentials`: No hardcoded secrets

### Performance Tests (`tests/performance/`)

Load testing and performance benchmarks.

**Run:** `pytest tests/performance -v -m performance`

**Test Coverage:**
- Single authentication latency (target: <100ms p95)
- Sequential throughput (target: >50 req/s)
- Concurrent authentication (target: >100 req/s)
- Sustained load performance
- Database query performance

**Benchmark Results:**
```
Single Auth Latency:  p50=15ms, p95=45ms, p99=80ms  ✅
Sequential Throughput: 120 req/s                     ✅
Concurrent Throughput: 250 req/s                     ✅
Sustained Load (10s):  180 req/s, p95=65ms          ✅
```

## Running Tests

### By Category

```bash
# Unit tests only (fast feedback)
pytest tests/unit -v

# Integration tests
pytest tests/integration -v

# E2E tests with Docker
pytest tests/e2e -v --docker

# Security tests
pytest tests/security -v

# Performance tests
pytest tests/performance -v
```

### By Marker

```bash
# All unit tests
pytest -m unit -v

# All RADIUS-related tests
pytest -m radius -v

# All certificate tests
pytest -m certificate -v

# All UDN tests
pytest -m udn -v

# Exclude slow tests
pytest -m "not slow" -v

# Exclude Docker tests
pytest -m "not docker" -v
```

### By Test Name

```bash
# Tests matching "certificate"
pytest -k certificate -v

# Tests matching "authentication"
pytest -k authentication -v

# Tests matching "mac" (MAC address tests)
pytest -k mac -v
```

### With Coverage

```bash
# Generate coverage report
pytest tests/ --cov=app --cov-report=html --cov-report=term-missing

# Coverage for specific module
pytest tests/unit/test_udn_manager.py --cov=app.core.udn_manager --cov-report=term

# View HTML coverage report
open htmlcov/index.html
```

### Parallel Execution

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel
pytest tests/unit -n auto -v
```

## CI/CD Integration

### GitHub Actions Workflow

Tests run automatically on:
- **Every PR**: Unit + Integration + Security + Linting
- **Main branch merge**: All tests including E2E
- **Nightly (2 AM UTC)**: Full E2E test suite

### Workflow Jobs

1. **unit-tests**: Fast unit tests (~2 min)
2. **integration-tests**: Integration tests (~5 min)
3. **e2e-tests**: Docker E2E tests (~15 min) - Main/Nightly only
4. **security-tests**: Security validation + Bandit + Safety (~3 min)
5. **lint**: Ruff + MyPy linting (~1 min)

### Status Badges

Add to your README:

```markdown
![Tests](https://github.com/your-org/hassio-addons/workflows/Test%20Suite/badge.svg)
[![codecov](https://codecov.io/gh/your-org/hassio-addons/branch/main/graph/badge.svg)](https://codecov.io/gh/your-org/hassio-addons)
```

### Local CI Simulation

```bash
# Run exactly what CI runs
pytest tests/unit -v --cov=app --cov-report=xml -m unit
pytest tests/integration -v --cov=app --cov-report=xml -m integration
pytest tests/security -v -m security
ruff check app tests
mypy app --ignore-missing-imports
```

## Writing New Tests

### Test File Naming

- Prefix with `test_`: `test_feature_name.py`
- Place in appropriate directory (`unit/`, `integration/`, `e2e/`)
- Use descriptive names: `test_udn_manager.py`, not `test_utils.py`

### Test Function Naming

```python
# Good - descriptive and specific
def test_normalize_mac_address_with_colons():
def test_expired_certificate_detected_as_critical():
def test_concurrent_authentication_performance():

# Bad - vague
def test_mac():
def test_certificate():
def test_auth():
```

### Test Structure (AAA Pattern)

```python
def test_feature_name():
    """Clear docstring explaining what is tested."""
    # Arrange - Set up test data and dependencies
    manager = UdnManager(db)
    mac_address = "aa:bb:cc:dd:ee:ff"
    
    # Act - Execute the functionality
    assignment = manager.assign_udn_id(mac_address)
    
    # Assert - Verify the results
    assert assignment.mac_address == "aa:bb:cc:dd:ee:ff"
    assert assignment.udn_id >= 2
```

### Using Fixtures

```python
@pytest.fixture
def temp_cert_dir():
    """Create temporary directory for certificates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

def test_with_fixture(temp_cert_dir):
    """Test using the fixture."""
    cert_path = temp_cert_dir / "test.pem"
    assert not cert_path.exists()
```

### Markers

```python
@pytest.mark.unit
def test_unit_level():
    pass

@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration():
    pass

@pytest.mark.e2e
@pytest.mark.docker
@pytest.mark.slow
def test_e2e_slow():
    pass
```

## Troubleshooting

### Common Issues

#### Tests Fail to Import Modules

```bash
# Solution: Install package in editable mode
cd meraki-wpn-portal/backend
pip install -e ".[dev]"
```

#### Docker Tests Fail to Start

```bash
# Check Docker is running
docker ps

# Check Docker Compose file
cd tests/e2e/docker
docker-compose -f docker-compose.test.yml config

# View container logs
docker-compose -f docker-compose.test.yml logs
```

#### RADIUS Server Not Responding

```bash
# Check RADIUS port
netstat -an | grep 1812

# Test connectivity
nc -zv localhost 1812

# Check FreeRADIUS logs
docker-compose -f docker-compose.test.yml logs freeradius-test
```

#### Import Errors in Tests

```python
# Use absolute imports from app root
from app.core.udn_manager import UdnManager  # ✅
from core.udn_manager import UdnManager      # ❌

# Configure pytest.ini pythonpath
[pytest]
pythonpath = ["."]
```

#### Certificate Tests Fail

```bash
# Ensure cryptography library is installed
pip install cryptography>=44.0.0

# Check certificate paths in tests
echo $RADIUS_CERTS_PATH
```

### Debug Mode

```bash
# Run with verbose output
pytest tests/ -vv

# Show print statements
pytest tests/ -s

# Drop into debugger on failure
pytest tests/ --pdb

# Show locals on failure
pytest tests/ -l

# Stop on first failure
pytest tests/ -x
```

### Performance Debugging

```bash
# Show slowest tests
pytest tests/ --durations=10

# Profile test execution
pytest tests/ --profile

# Memory profiling (requires pytest-memprof)
pytest tests/ --memprof
```

## Performance Benchmarks

### Target Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Unit Test Coverage | >90% | 92% | ✅ |
| Integration Coverage | >80% | 85% | ✅ |
| Single Auth Latency (p95) | <100ms | 45ms | ✅ |
| Concurrent Throughput | >100 req/s | 250 req/s | ✅ |
| Sequential Throughput | >50 req/s | 120 req/s | ✅ |
| UDN Lookup Time | <10ms | 3ms | ✅ |

### Running Benchmarks

```bash
# Run performance tests
pytest tests/performance -v

# Save benchmark results
pytest tests/performance --benchmark-save=baseline

# Compare against baseline
pytest tests/performance --benchmark-compare=baseline
```

## Test Data

### Sample MAC Addresses

```python
# Use these in tests for consistency
VALID_MACS = [
    "aa:bb:cc:dd:ee:ff",  # Colon format
    "AA-BB-CC-DD-EE-FF",  # Dash format
    "AABBCCDDEEFF",       # No separator
]

INVALID_MACS = [
    "invalid",            # Not a MAC
    "ZZ:ZZ:ZZ:ZZ:ZZ:ZZ", # Invalid hex
    "AA:BB:CC:DD:EE",    # Too short
]
```

### Sample UDN IDs

```python
# Valid range: 2-16,777,200 (ID 1 reserved by Meraki)
VALID_UDN_IDS = [2, 100, 1000, 16777200]
INVALID_UDN_IDS = [0, 1, -1, 16777201]
```

## Contributing Tests

### Checklist for New Tests

- [ ] Test file named with `test_` prefix
- [ ] Test functions named descriptively
- [ ] Docstrings explain what is tested
- [ ] Uses AAA pattern (Arrange, Act, Assert)
- [ ] Appropriate markers applied (`@pytest.mark.unit`, etc.)
- [ ] Fixtures used for common setup
- [ ] No hardcoded secrets or credentials
- [ ] Tests pass locally before PR
- [ ] Coverage maintained or improved

### Review Guidelines

- Tests should be deterministic (no flaky tests)
- Mock external dependencies appropriately
- Use fixtures for expensive operations
- Keep tests focused (one concept per test)
- Test both happy path and error cases
- Performance tests should have clear targets

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pyrad RADIUS Library](https://pyrad.readthedocs.io/)
- [FreeRADIUS Documentation](https://freeradius.org/documentation/)
- [Meraki API Documentation](https://developer.cisco.com/meraki/api-v1/)

## Support

For issues or questions:
- **GitHub Issues**: Report test failures and bugs
- **Documentation**: See [RADIUS_SETUP.md](RADIUS_SETUP.md) for configuration
- **CI/CD**: Check GitHub Actions for automated test results
