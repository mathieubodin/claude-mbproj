include mbproj.mk

publish: ## Push the prepared release, then refresh and verify installed copies
	@scripts/release.sh publish

release: lint test ## Prepare a release locally and stop (VERSION=X.Y.Z); pushes nothing
	@scripts/release.sh prepare "$(VERSION)"

release-abort: ## Undo a prepared release that has not been published
	@scripts/release.sh abort

test: ## Run the plugin verification suite
	@python3 skills/mbproj-scaffold/tests/brownfield_check.py
	@python3 skills/mbproj-scaffold/tests/docs_consistency.py

.PHONY: publish release release-abort test
