PYTHON ?= python2.7
VENV   ?= venv
BIN     = $(VENV)/bin

.PHONY: install test coverage seed run clean docker-build docker-test docker-run

$(BIN)/python:
	$(PYTHON) -m virtualenv $(VENV)

install: $(BIN)/python
	$(BIN)/pip install -r requirements.txt -r requirements-dev.txt

test:
	$(BIN)/nosetests tests

coverage:
	$(BIN)/nosetests tests --with-coverage --cover-package=orderdesk --cover-erase

seed:
	$(BIN)/python manage.py seed --if-empty

run: seed
	$(BIN)/python manage.py runserver

clean:
	find . -name '*.pyc' -delete
	rm -f orderdesk.db .coverage

docker-build:
	docker build -t orderdesk .

docker-test: docker-build
	docker run --rm orderdesk nosetests tests

docker-run: docker-build
	docker run --rm -p 5050:5000 -v orderdesk-data:/data orderdesk
