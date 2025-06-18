lint:
	@uv run ruff check

format:
	@uv run ruff format

bump-major:
	@uv version --bump major

bump-minor:
	@uv version --bump minor

bump-patch:
	@uv version --bump patch