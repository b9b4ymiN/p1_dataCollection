# Contributing to Phase 1 Data Collection

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

## How to Contribute

### Reporting Bugs

Before creating bug reports, please check existing issues. When creating a bug report, include:

- **Clear title and description**
- **Steps to reproduce**
- **Expected vs actual behavior**
- **Screenshots** (if applicable)
- **Environment details** (Python version, OS, etc.)
- **Error messages** and stack traces

### Suggesting Enhancements

Enhancement suggestions are welcome! Include:

- **Use case**: Why is this enhancement needed?
- **Proposed solution**: How should it work?
- **Alternatives considered**: Other approaches you've thought about
- **Additional context**: Any other relevant information

### Pull Requests

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Make your changes**
4. **Write tests** for your changes
5. **Run the test suite** (`pytest`)
6. **Update documentation** if needed
7. **Commit your changes** (`git commit -m 'Add amazing feature'`)
8. **Push to your fork** (`git push origin feature/amazing-feature`)
9. **Open a Pull Request**

## Development Setup

### Prerequisites

- Python 3.9+
- PostgreSQL 14+ with TimescaleDB
- Redis 6+
- Docker (optional, for containerized development)

### Installation

```bash
# Clone the repository
git clone https://github.com/b9b4ymiN/p1_dataCollection.git
cd p1_dataCollection

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
# Edit .env with your configuration

# Initialize database
python scripts/init_database.py
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific test file
pytest tests/test_error_tracker.py

# Run with verbose output
pytest -v
```

### Code Style

We use automated tools to maintain code quality:

```bash
# Format code with black
black data_collector/ data_quality/ utils/ scripts/

# Sort imports with isort
isort data_collector/ data_quality/ utils/ scripts/

# Check code style with flake8
flake8 data_collector/ data_quality/ utils/ scripts/

# Type checking with mypy
mypy data_collector/ data_quality/ utils/
```

### Pre-commit Hooks

We use pre-commit hooks to ensure code quality:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

## Project Structure

```
p1_dataCollection/
├── data_collector/       # Data collection modules
│   ├── binance_client.py
│   ├── hardened_binance_client.py
│   ├── optimized_collector.py
│   └── ...
├── data_quality/         # Data validation
│   └── validator.py
├── utils/                # Utility modules
│   ├── error_tracker.py
│   ├── circuit_breaker.py
│   └── ...
├── scripts/              # Executable scripts
│   ├── init_database.py
│   ├── optimized_collection.py
│   └── ...
├── schemas/              # Database schemas
│   └── create_tables.sql
├── tests/                # Test files
│   ├── test_error_tracker.py
│   └── ...
├── logs/                 # Log files
└── config.yaml           # Configuration
```

## Coding Standards

### Python Style

- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use type hints where appropriate
- Maximum line length: 100 characters
- Use docstrings for all public functions/classes

### Naming Conventions

- **Functions/variables**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private members**: `_leading_underscore`

### Documentation

- Add docstrings to all public functions and classes
- Include parameter types and return types
- Provide usage examples for complex functionality
- Update README.md if adding new features

### Example Function Documentation

```python
def fetch_ohlcv(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    Fetch OHLCV data from Binance.

    Args:
        symbol: Trading pair (e.g., 'SOL/USDT')
        timeframe: Candlestick interval ('5m', '1h', etc.)

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume

    Raises:
        ValueError: If symbol or timeframe is invalid
        ConnectionError: If API request fails

    Example:
        >>> df = fetch_ohlcv('SOL/USDT', '5m')
        >>> print(df.head())
    """
    pass
```

## Testing Guidelines

### Writing Tests

- Write tests for all new features
- Maintain test coverage above 80%
- Use descriptive test names
- Test edge cases and error conditions
- Use fixtures for common setup

### Test Structure

```python
import pytest

class TestMyFeature:
    """Tests for my feature"""

    def setup_method(self):
        """Setup for each test"""
        self.fixture_data = ...

    def test_normal_case(self):
        """Test normal operation"""
        assert my_function() == expected_result

    def test_edge_case(self):
        """Test edge case"""
        assert my_function(edge_input) == edge_result

    def test_error_handling(self):
        """Test error handling"""
        with pytest.raises(ValueError):
            my_function(invalid_input)
```

## Git Workflow

### Commit Messages

Follow conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Example:**
```
feat(collector): add support for futures perpetual data

- Implement perpetual futures data collection
- Add error handling for perpetual contracts
- Update documentation with usage examples

Closes #123
```

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation
- `refactor/description` - Code refactoring

## Release Process

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create release tag
4. Build and test Docker images
5. Deploy to staging
6. Run integration tests
7. Deploy to production

## Performance Considerations

- Profile code for performance bottlenecks
- Use async/await for I/O-bound operations
- Implement caching where appropriate
- Monitor memory usage for large datasets
- Use batch operations for database writes

## Security Considerations

- Never commit sensitive data (API keys, passwords)
- Use environment variables for configuration
- Validate all external input
- Follow security best practices in SECURITY.md
- Run security scans before releasing

## Getting Help

- **Documentation**: Check README.md, PERFORMANCE.md, ERROR_HARDENING.md
- **Issues**: Search existing issues before creating new ones
- **Discussions**: Use GitHub Discussions for questions
- **Email**: Contact maintainers for sensitive issues

## Recognition

Contributors will be acknowledged in:
- GitHub contributors page
- Release notes
- Project documentation (if significant contribution)

Thank you for contributing to Phase 1 Data Collection! 🚀
