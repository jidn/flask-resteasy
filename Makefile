# Python Project Makefile - Clinton James
# For more information on creating packages for PyPI see the writeup at
# http://peterdowns.com/posts/first-time-with-pypi.html
#
# Python settings
ifndef TRAVIS
	PYTHON_MAJOR := 3
	PYTHON_MINOR := 4
	ENV := env
else
	# Use the virtualenv provided by Travis
	ENV = $(VIRTUAL_ENV)
endif

# System paths
# I haven't developed for windows for a long time, mileage may vary.
PLATFORM := $(shell python -c 'import sys; print(sys.platform)')
ifneq ($(findstring win32, $(PLATFORM)), )
	SYS_PYTHON_DIR := C:\\Python$(PYTHON_MAJOR)$(PYTHON_MINOR)
	SYS_PYTHON := $(SYS_PYTHON_DIR)\\python.exe
	SYS_VIRTUALENV := $(SYS_PYTHON_DIR)\\Scripts\\virtualenv.exe
	# https://bugs.launchpad.net/virtualenv/+bug/449537
	export TCL_LIBRARY=$(SYS_PYTHON_DIR)\\tcl\\tcl8.5
else
	SYS_PYTHON := python$(PYTHON_MAJOR)
	ifdef PYTHON_MINOR
		SYS_PYTHON := $(SYS_PYTHON).$(PYTHON_MINOR)
	endif
	SYS_VIRTUALENV := virtualenv
endif

# virtualenv paths
ifneq ($(findstring win32, $(PLATFORM)), )
	BIN := $(ENV)/Scripts
	OPEN := cmd /c start
else
	BIN := $(ENV)/bin
	ifneq ($(findstring cygwin, $(PLATFORM)), )
		OPEN := cygstart
	else
		OPEN := xdg-open
	endif
endif

# virtualenv executables
PYTHON := $(BIN)/python
PIP := $(BIN)/pip
PEP8 := $(BIN)/pep8
FLAKE8 := $(BIN)/flake8
PEP8RADIUS := $(BIN)/pep8radius
PEP257 := $(BIN)/pep257
PYTEST := $(BIN)/py.test
COVERAGE := $(BIN)/coverage
ACTIVATE := $(BIN)/activate

# Project settings
PROJECT := Flask-RESTeasy
PACKAGE := flask_resteasy.py
SOURCES := Makefile setup.py $(shell find $(PACKAGE) -name '*.py')
EGG_INFO := $(subst -,_,$(PROJECT)).egg-info

# Flags for PHONY targets
# Are environments/tools installed for continuous integration and development?
DEPENDS_CI := $(ENV)/.depends-ci
DEPENDS_DEV := $(ENV)/.depends-dev
ALL := $(ENV)/.all

# Main Targets ###############################################################

.PHONY: all
all: depends $(ALL)
$(ALL): $(SOURCES)
	$(MAKE) check
	touch $(ALL)  # flag to indicate all setup steps were successful

# Targets to run on Travis
.PHONY: ci
ci: test

# Environment Installation ###################################################

.PHONY: env
env: .virtualenv $(EGG_INFO)
$(EGG_INFO): Makefile setup.py
	$(PIP) install -e .
	touch $(EGG_INFO)  # flag to indicate package is installed

.ONY: .virtualenv
.virtualenv: $(PIP)
$(PIP):
	$(SYS_VIRTUALENV) --python $(SYS_PYTHON) $(ENV)

.PHONY: depends
depends: .depends-ci .depends-dev

.PHONY: .depends-ci
.depends-ci: env Makefile $(DEPENDS_CI)
$(DEPENDS_CI): Makefile tests/requirements.txt
	$(PIP) install --upgrade flake8 pep257
	$(PIP) install -r tests/requirements.txt
	touch $(DEPENDS_CI)  # flag to indicate dependencies are installed

.PHONY: .depends-dev
.depends-dev: env Makefile $(DEPENDS_DEV)
$(DEPENDS_DEV): Makefile
	$(PIP) install --upgrade wheel  # pep8radius pygments wheel
	touch $(DEPENDS_DEV)  # flag to indicate dependencies are installed

# Static Analysis ############################################################

.PHONY: check
check: flake8 pep257

PEP8_IGNORED := E501,E123

.PHONY: pep8
pep8: .depends-ci
	$(PEP8) $(PACKAGE) tests --ignore=$(PEP8_IGNORED)

.PHONY: flake8
flake8: .depends-ci
	$(FLAKE8) $(PACKAGE) tests --ignore=$(PEP8_IGNORED)

.PHONY: pep257
pep257: .depends-ci
	$(PEP257) $(PACKAGE)

.PHONY: fix
fix: .depends-dev
	$(PEP8RADIUS) --docformatter --in-place

# Testing ####################################################################

PYTEST_OPTS := --cov $(PACKAGE) \
			   --cov-report term-missing \
			   --cov-report html 

.PHONY: test
test: .depends-ci
	$(PYTEST) tests/*.py $(PYTEST_OPTS)

.PHONY: pdb
pdb: .depends-ci
	$(PYTEST) tests/*.py $(PYTEST_OPTS) -x --pdb

.PHONY: htmlcov
htmlcov: test
	$(COVERAGE) html
	$(OPEN) htmlcov/index.html

# Cleanup ####################################################################

.PHONY: clean
clean: .clean-dist .clean-test .clean-build
	rm -rf $(ALL)

.PHONY: clean-env
clean-env: clean
	rm -rf $(ENV)

.PHONY: clean-all
clean-all: clean clean-env

.PHONY: .clean-build
.clean-build:
	find tests -name '*.pyc' -delete
	find -name $(PACKAGE)c -delete
	find tests -name '__pycache__' -delete
	rm -rf $(EGG_INFO)

.PHONY: .clean-test
.clean-test:
	rm -rf .coverage
	rm -f test.log

.PHONY: .clean-dist
.clean-dist:
	rm -rf dist build

# Release ####################################################################

.PHONY: authors
authors:
	echo "Authors\n=======\n\nA huge thanks to all of our contributors:\n\n" > AUTHORS.md
	git log --raw | grep "^Author: " | cut -d ' ' -f2- | cut -d '<' -f1 | sed 's/^/- /' | sort | uniq >> AUTHORS.md

.PHONY: register
register: 
	$(PYTHON) setup.py register -r pypi

.PHONY: dist
dist: test
	$(PYTHON) setup.py sdist
	$(PYTHON) setup.py bdist_wheel

.PHONY: upload
upload: .git-no-changes doc register
	$(PYTHON) setup.py sdist upload -r pypi
	$(PYTHON) setup.py bdist_wheel upload -r pypi

.PHONY: .git-no-changes
.git-no-changes:
	@if git diff --name-only --exit-code;         \
	then                                          \
		echo Git working copy is clean...;        \
	else                                          \
		echo ERROR: Git working copy is dirty!;   \
		echo Commit your changes and try again.;  \
		exit -1;                                  \
	fi;

# System Installation ########################################################

.PHONY: develop
develop:
	$(SYS_PYTHON) setup.py develop

.PHONY: install
install:
	$(SYS_PYTHON) setup.py install

.PHONY: download
download:
	pip install $(PROJECT)
