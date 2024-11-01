.PHONY: install  ## Install the package, dependencies
install:
	uv sync --frozen
	uv pip compile pyproject.toml -o requirements.txt

.PHONY: format  # Format the code
format:
	uv run ruff format
	uv run ruff check --fix

.PHONY: lint  # Lint the code
lint:
	uv run ruff check
	uv run ruff format --check --diff

.PHONY: typecheck  # Typecheck the code
typecheck:
	uv run pyright


.PHONY: test  # Run the tests
test:
	uv run pytest

run:
	uv run python -m main

.PHONY: all  # Run all the commands
all: format lint typecheck run
