include mbproj.mk

test: ## Run the plugin verification suite
	@python3 skills/mbproj-scaffold/tests/brownfield_check.py

.PHONY: test
