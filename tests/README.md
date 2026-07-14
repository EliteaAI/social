# Social Plugin Tests

Unit tests for the social plugin, isolated from Pylon runtime.

## Quick Start

```bash
cd centry/pylon_main/plugins/social
python3 tests/run_tests.py -v
```

## Test Structure

```
tests/
├── run_tests.py          # Entry point - installs Pylon stubs before pytest
├── pytest.ini            # Pytest configuration
├── conftest.py           # Auto-markers based on directory
├── requirements-dev.txt  # Test dependencies
├── fixtures/
│   └── helpers.py        # Module loading utilities
└── unit/
    ├── test_image_utils.py     # sizeof_fmt, SUPPORTED_FORMATS
    └── test_pydantic_models.py # FeedbackModel validation
```

## Running Tests

```bash
# All tests
python3 tests/run_tests.py -v

# Unit tests only
python3 tests/run_tests.py -m unit -v

# Specific file
python3 tests/run_tests.py unit/test_image_utils.py -v
```

## Test Count

- **Unit tests**: 26 (image_utils, pydantic model validation)
