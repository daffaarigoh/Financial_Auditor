.PHONY: help install install-dev test run clean

help:
	@echo "Available commands:"
	@echo "  make install      Install production dependencies"
	@echo "  make install-dev  Install development & testing dependencies"
	@echo "  make test         Run pytest test suite"
	@echo "  make run          Start FastAPI backend server"
	@echo "  make clean        Clean cache and test artifacts"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

test:
	pytest tests/ -v

run:
	python server.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .coverage htmlcov 2>/dev/null || true
