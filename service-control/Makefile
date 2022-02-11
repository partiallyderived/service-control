# Need this so we can use source to activate virtual environment.
SHELL := /bin/bash

VENV_DIR := venv
VENV_ACTIVATE := source $(VENV_DIR)/bin/activate

.PHONY: clean
clean:
	rm -rf .pytest_cache

.PHONY: test
test: $(VENV_DIR)
	$(VENV_ACTIVATE) && python3 -m pytest test/ -r sf -v

.PHONY: test-failed
test-failed: $(VENV_DIR)
	$(VENV_ACTIVATE) && python3 -m pytest test/ -r sf -v --lf

$(VENV_DIR): setup.cfg
	# Do not create new venv if it already exists, but delete it if it did not exist before and did not create without
	# error.
	([ -d $(VENV_DIR) ] || python3 -m venv $(VENV_DIR) || (rm -rf $(VENV_DIR) && false))
	$(VENV_ACTIVATE) && cd ../bobbey-reese-tools && python3 -m pip install -e .
	$(VENV_ACTIVATE) && python3 -m pip install -e .[test]  || (rm -rf $(VENV_DIR) && false)
	touch $(VENV_DIR)
	rm -rf src/service_control.egg-info
