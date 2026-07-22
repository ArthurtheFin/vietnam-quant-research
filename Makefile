.PHONY: check-notebooks test

# Structural check against src/ signature drift breaking notebooks
# (docs/reports/codebase_audit/NOTEBOOK_AUDIT_FULL.md NV3). Runs every
# notebook top-to-bottom in an isolated sandbox; never touches real project
# data. See scripts/check_notebooks.py for details/flags.
check-notebooks:
	python scripts/check_notebooks.py

test:
	pytest
