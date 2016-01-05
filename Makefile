# Python Project Makefile - Clinton James
# For more information on creating packages for PyPI see the writeup at
# http://peterdowns.com/posts/first-time-with-pypi.html
#
# Python settings
ifndef TRAVIS
	PYTHON_MAJOR := 2
	PYTHON_MINOR := 7
	# We assume there is an 'env' directory which 'make env' will build
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
FLAKE8 := $(BIN)/flake8
PEP257 := $(BIN)/pep257
COVERAGE := $(BIN)/coverage

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
.PHONY: env .virtualenv depends .depends-ci .depends-dev

env: .virtualenv $(EGG_INFO)
$(EGG_INFO): Makefile setup.py
	$(PIP) install -e .
	touch $(EGG_INFO)  # flag to indicate package is installed

.virtualenv: $(PIP) #requirements.txt
$(PIP):
	$(SYS_VIRTUALENV) --python $(SYS_PYTHON) $(ENV)
	@echo "Created virtual environment"

#requirements.txt:
#	$(PIP) install --upgrade -r requirements.txt


depends: .depends-ci .depends-dev

.depends-ci: env Makefile $(DEPENDS_CI)
$(DEPENDS_CI): Makefile tests/requirements.txt
	$(PIP) install --upgrade flake8 pep257
	$(PIP) install -r tests/requirements.txt
	touch $(DEPENDS_CI)  # flag to indicate dependencies are installed

.depends-dev: env Makefile $(DEPENDS_DEV)
$(DEPENDS_DEV): Makefile
#	$(PIP) install --upgrade wheel  # pygments wheel
	touch $(DEPENDS_DEV)  # flag to indicate dependencies are installed

# Static Analysis ############################################################
.PHONY: check flake8 pep257

check: flake8 pep257

PEP8_IGNORED := E501,E123,D104,D203

flake8: .depends-ci
	$(FLAKE8) $(PACKAGE) tests --ignore=$(PEP8_IGNORED)

pep257: .depends-ci
	$(PEP257) $(PACKAGE) tests --ignore=$(PEP8_IGNORED)

# Testing ####################################################################
.PHONY: test pdb coverage
PYTESTER := $(BIN)/py.test

PYTESTER_OPTS := --cov $(PACKAGE) \
			   --cov-report term-missing \
			   --cov-report html 

test: .depends-ci
	$(PYTESTER) tests/*.py $(PYTESTER_OPTS)

pdb: .depends-ci
	$(PYTESTER) tests/*.py $(PYTESTER_OPTS) -x --pdb

coverage: test
	$(COVERAGE) html
	$(OPEN) htmlcov/index.html

# Cleanup ####################################################################
.PHONY: clean clean-env clean-all .clean-build .clean-test .clean-dist

clean: .clean-dist .clean-test .clean-build
	rm -rf $(ALL)

clean-env: clean
	rm -rf $(ENV)
	rm -rf .cache

clean-all: clean clean-env

.clean-build:
	find tests -name '*.pyc' -delete
	find -name $(PACKAGE)c -delete
	find tests -name '__pycache__' -delete
	rm -rf $(EGG_INFO)

.clean-test:
	rm -rf .coverage
	rm -rf htmlcov
	rm -f test.log

.clean-dist:
	rm -rf dist build

# Release ####################################################################
.PHONY: authors register dist upload .git-no-changes

authors:
	@echo -e "Authors\n=======\n\nA huge thanks to all of our contributors:\n\n" > AUTHORS.md
	git log --raw | grep "^Author: " | cut -d ' ' -f2- | cut -d '<' -f1 | sed 's/^/- /' | sort | uniq >> AUTHORS.md

.PHONY: register
register: 
	$(PYTHON) setup.py register -r pypi

.PHONY: dist
dist: test
	$(PYTHON) setup.py sdist
	$(PYTHON) setup.py bdist_wheel

.PHONY: upload
upload: .git-no-changes register
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
.PHONY: develop install download
# Is this section really needed?

develop:
	$(SYS_PYTHON) setup.py develop

install:
	$(SYS_PYTHON) setup.py install

download:
	$(PIP) install $(PROJECT)
