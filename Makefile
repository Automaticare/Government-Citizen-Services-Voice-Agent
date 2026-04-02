# Requires: make (install via `choco install make` or `winget install GnuWin32.Make`)
# On Windows without make, use the commands directly.

.PHONY: install test test-live deploy deploy-dry clean

install:
	python -m venv .venv
	.venv/Scripts/pip install -r requirements.txt

test:
	python -m pytest tests/ -v

test-live:
	python -m pytest tests/ -v -s -k "Live or IntentDetection"

deploy: test
	python -m agent.deploy

deploy-dry:
	python -m agent.deploy --dry-run

clean:
	python -c "import shutil, pathlib; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')]"
	python -c "import shutil, pathlib; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('.pytest_cache')]"
