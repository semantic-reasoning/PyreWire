# Contributing to PyreWire

We appreciate your interest in contributing to PyreWire! This guide explains how to get involved. For a project overview, see [README.md](README.md).

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md). We expect all contributors to uphold it in every interaction.

## How to Report Bugs

Use the **Bug Report** issue template when filing a bug:

- Open an issue using the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.yml)
- Include steps to reproduce, expected behavior, and actual behavior
- Attach relevant logs or tracebacks when possible

**Security vulnerabilities:** Do not open a public issue. Instead, follow our [Security Policy](SECURITY.md) for responsible disclosure.

## How to Suggest Features

Use the **Feature Request** issue template to propose new functionality:

- Open an issue using the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.yml)
- Explain your use case clearly — what problem does this solve?
- Consider alternatives you've already evaluated

## Development Setup

```bash
git clone https://github.com/gazgiz/PyreWire.git
cd PyreWire
pip install -e ".[dev]"
```

**Requirements:** Python 3.10+. See [pyproject.toml](pyproject.toml) for the full list of dev dependencies.

## Coding Standards

All code must pass the following tools before submission:

| Tool | Config |
|------|--------|
| **black** | line length 100 (see `pyproject.toml`) |
| **isort** | black profile (see `pyproject.toml`) |
| **flake8** | standard rules |
| **mypy** | type hints required for all public APIs (Python 3.10+ syntax) |

Run them all at once:

```bash
black . && isort . && flake8 . && mypy .
```

## Running Tests

```bash
pytest --cov=pyrewire
```

- Aim for **80%+ coverage**
- Include both unit and integration tests
- See [pyproject.toml](pyproject.toml) for test configuration

## Pull Request Process

1. Fork the repository and create a feature branch from `main`
2. Make your changes, keeping commits focused (see below)
3. Ensure all tests pass and linting is clean
4. Fill out the [pull request template](.github/PULL_REQUEST_TEMPLATE.md)
5. At least one approval is required before merge

## Commit Message Conventions

- Use imperative mood: "Add feature" not "Added feature"
- Start with a concise summary line
- Keep commits atomic — one logical change per commit

**Example:**
```
Add security policy for vulnerability reporting
```

## License

PyreWire is dual-licensed under **Apache-2.0 OR GPL-3.0-or-later**. By submitting a pull request, you agree to license your contribution under the same dual-license terms.
