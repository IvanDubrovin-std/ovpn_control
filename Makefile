.PHONY: help install install-dev format lint test coverage clean run migrate

help:
	@echo "Available commands:"
	@echo "  make install       - Install production dependencies"
	@echo "  make install-dev   - Install dev dependencies"
	@echo "  make format        - Format code with black and isort"
	@echo "  make lint          - Run linting (flake8, mypy)"
	@echo "  make test          - Run tests"
	@echo "  make coverage      - Run tests with coverage"
	@echo "  make clean         - Remove cache and temp files"
	@echo "  make run           - Run development server"
	@echo "  make migrate       - Run Django migrations"
	@echo "  make quality       - Run all quality checks"

install:
	pip install -r requirements.txt

install-dev: install
	pip install -r requirements-dev.txt
	pre-commit install

format:
	@echo "🎨 Formatting code..."
	black ovpn_app/ ovpn_project/
	isort ovpn_app/ ovpn_project/

lint:
	@echo "🔍 Running linters..."
	flake8 ovpn_app/ ovpn_project/
	mypy ovpn_app/ ovpn_project/ --ignore-missing-imports

test:
	@echo "🧪 Running tests..."
	pytest

coverage:
	@echo "📊 Running tests with coverage..."
	pytest --cov=ovpn_app --cov-report=term-missing --cov-report=html

clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage

run:
	@echo "🚀 Starting development server..."
	python manage.py runserver

migrate:
	@echo "🔄 Running migrations..."
	python manage.py makemigrations
	python manage.py migrate

quality: format lint test
	@echo "✅ All quality checks passed!"

check: lint test
	@echo "✅ All checks passed!"
