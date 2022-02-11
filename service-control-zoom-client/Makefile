# Need this so we can use source to activate virtual environment.
SHELL := /bin/bash

SERVICE_CONTROL_DEPS := data
OTHER_DEPS := bobbey-reese-tools service-control
ALL_DEPS := $(OTHER_DEPS) $(foreach dep,$(SERVICE_CONTROL_DEPS),service-control-$(dep))
VENV_DIR := venv
VENV_ACTIVATE := source $(VENV_DIR)/bin/activate

.PHONY: clean
clean:
	rm -rf .pytest_cache

.PHONY: test
test: $(VENV_DIR)
	$(VENV_ACTIVATE) && python3 -m pytest -r sf -v

.PHONY: test-failed
test-failed: $(VENV_DIR)
	$(VENV_ACTIVATE) && python3 -m pytest -r sf -v --lf

$(VENV_DIR): setup.cfg
	# Do not create new venv if it already exists, but delete it if it did not exist before and did not create without
	# error.
	([ -d $(VENV_DIR) ] || python3 -m venv $(VENV_DIR) || (rm -rf $(VENV_DIR) && false))
	$(VENV_ACTIVATE) && python3 -m pip install wheel
	$(VENV_ACTIVATE) && for i in $(ALL_DEPS); do \
  		cd ../$$i && python3 -m pip install -e .; \
  	done
	$(VENV_ACTIVATE) && python3 -m pip install -e .[test]  || (rm -rf $(VENV_DIR) && false)
	for i in $(ALL_DEPS); do \
  		rm -rf ../$$i/src/*.egg-info; \
  	done
	touch $(VENV_DIR)
	rm -rf src/*.egg-info
