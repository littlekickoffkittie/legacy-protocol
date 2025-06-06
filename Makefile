.PHONY: install test lint format clean build docs

# Installation
install:
	pip install -e ".[dev]"

# Testing
test:
	pytest --cov=legacy_coordinate \
		   --cov=legacy_utxo \
		   --cov=legacy_transaction \
		   --cov=legacy_block \
		   --cov=legacy_blockchain \
		   --cov-report=term-missing

test-fast:
	pytest -x --ff

# Code Quality
lint:
	flake8 legacy_coordinate legacy_utxo legacy_transaction legacy_block legacy_blockchain
	mypy legacy_coordinate legacy_utxo legacy_transaction legacy_block legacy_blockchain
	black --check legacy_coordinate legacy_utxo legacy_transaction legacy_block legacy_blockchain

format:
	black legacy_coordinate legacy_utxo legacy_transaction legacy_block legacy_blockchain

# Cleanup
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf **/__pycache__/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/

# Build
build:
	python setup.py sdist bdist_wheel

# Documentation
docs:
	sphinx-build -b html docs/source/ docs/build/html

# Development
dev-setup: install
	pre-commit install

# Docker
docker-build:
	docker build -t legacy-protocol .

docker-run:
	docker run -p 8000:8000 legacy-protocol

# Database
db-init:
	python -m legacy_blockchain.db.init

db-reset: db-clean db-init

db-clean:
	rm -rf data/db/*

# Node
run-node:
	python -m legacy_blockchain.node

run-testnet:
	python -m legacy_blockchain.node --testnet

# Help
help:
	@echo "Available commands:"
	@echo "  make install      Install package and dependencies"
	@echo "  make test        Run tests with coverage"
	@echo "  make test-fast   Run tests quickly (stop on first failure)"
	@echo "  make lint        Run linters (flake8, mypy, black)"
	@echo "  make format      Format code with black"
	@echo "  make clean       Clean build artifacts"
	@echo "  make build       Build package"
	@echo "  make docs        Build documentation"
	@echo "  make dev-setup   Setup development environment"
	@echo "  make docker-build Build Docker image"
	@echo "  make docker-run   Run Docker container"
	@echo "  make db-init      Initialize database"
	@echo "  make db-reset     Reset database"
	@echo "  make run-node     Run node"
	@echo "  make run-testnet  Run testnet node"

# Default
.DEFAULT_GOAL := help
