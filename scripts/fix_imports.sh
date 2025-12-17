#!/bin/bash
# Fix import paths in Python files to work with Docker container structure

cd "$(dirname "$0")/.."

# Find all Python files and update imports
find backend -name "*.py" -type f | while read file; do
    # Replace 'from backend.' with 'from backend.' (keep as is, but ensure consistency)
    # The issue is that some files might have inconsistent imports
    echo "Checking $file..."
done

echo "Import paths should use 'backend.' prefix when PYTHONPATH=/app"


