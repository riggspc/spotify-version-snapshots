# Development Guide

This guide will help you get set up to develop `spotify-snapshot`.

## Prerequisites

- Python 3.12 or higher
- [Hatch](https://hatch.pypa.io/latest/install/) installed (`pip install hatch`)

## Development Environment Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/alichtman/spotify-snapshot.git
   cd spotify-snapshot
   ```

2. Create and activate a development environment:
   ```bash
   hatch shell
   ```

This will create a virtual environment with all development dependencies installed.

## Common Development Tasks

### Code Quality

```bash
# Format code with black
hatch run fmt

# Run all linters (black --check, flake8, mypy)
hatch run lint

# Run type checking only
hatch run typecheck
```

### Testing

(We have no tests)

```bash
# Run tests
hatch run test

# Run tests with coverage report
hatch run cov
```

### Building the Package

```bash
hatch build
```

### Local Development Installation

To install the package in development mode:

```bash
pip install -e .
```

## Bumping Version

`hatch` manages the versioning:

```bash
$ hatch version [ major / minor / patch ]
```

## Publishing

```bash
$ hatch publish
```
