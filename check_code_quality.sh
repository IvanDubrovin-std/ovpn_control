#!/bin/bash
# Code quality check script

set -e

echo "🔍 Running code quality checks..."

# 1. Black formatting
echo "📝 Checking code formatting with Black..."
black --check ovpn_app/ ovpn_project/ || {
    echo "❌ Code formatting issues found. Run 'black ovpn_app/ ovpn_project/' to fix."
    exit 1
}

# 2. isort imports
echo "📦 Checking import sorting with isort..."
isort --check-only ovpn_app/ ovpn_project/ || {
    echo "❌ Import sorting issues found. Run 'isort ovpn_app/ ovpn_project/' to fix."
    exit 1
}

# 3. Flake8 linting
echo "🔎 Running Flake8 linting..."
flake8 ovpn_app/ ovpn_project/ || {
    echo "❌ Linting issues found."
    exit 1
}

# 4. MyPy type checking
echo "🎯 Running MyPy type checking..."
mypy ovpn_app/ ovpn_project/ --ignore-missing-imports || {
    echo "⚠️  Type checking issues found (warnings only)."
}

# 5. Django checks
echo "🔧 Running Django system checks..."
python manage.py check || {
    echo "❌ Django system check failed."
    exit 1
}

# 6. Run tests
echo "🧪 Running tests..."
pytest || {
    echo "❌ Tests failed."
    exit 1
}

echo "✅ All checks passed!"
