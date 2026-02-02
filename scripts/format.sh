#!/bin/bash
# Format all Python files in the project

set -e

echo "Running black formatter..."
black app tests

echo "Running isort for import sorting..."
isort app tests

echo "Running ruff for linting fixes..."
ruff check app tests --fix || true

echo "Done! All files formatted."
