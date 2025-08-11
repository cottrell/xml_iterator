# Test Suite

This directory contains the test suite for xml_iterator using pytest.

## Running Tests

### Install test dependencies
```bash
pip install -e ".[test]"
```

### Run all tests
```bash
pytest
```

### Run specific test categories
```bash
# Basic functionality tests
pytest tests/test_basic.py

# xmltodict compatibility tests
pytest tests/test_xmltodict.py

# Performance tests (marked as slow)
pytest tests/test_performance.py

# Skip slow tests
pytest -m "not slow"

# Run performance benchmarks (not tests)
make benchmark
```

### Run with coverage
```bash
pip install pytest-cov
pytest --cov=xml_iterator --cov-report=html
```

## Test Structure

- **test_basic.py**: Core functionality tests
  - Basic XML parsing
  - Edge counting
  - Streaming behavior
  - Encoding handling
  - Deep nesting
  - Malformed XML handling

- **test_xmltodict.py**: Compatibility tests with xmltodict library
  - Exact result comparisons
  - 100% compatibility with xmltodict

- **test_performance.py**: Performance regression tests
  - Throughput thresholds
  - Memory efficiency with early termination
  - Protection limits functionality  
  - Tests marked with `@pytest.mark.slow`

## Test Configuration

Configuration is in `pytest.ini`:
- Tests are auto-discovered in the `tests/` directory
- Custom markers are defined for slow tests
- Verbose output with short tracebacks by default