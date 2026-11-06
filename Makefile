.PHONY: eval deps

deps:
	pip3 install --user -r backend/requirements.txt -r backend/requirements-dev.txt

eval: deps
	PYTHONPATH=. python3 -m pytest -q evals
