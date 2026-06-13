.PHONY: install up down logs server frontend test ingest ingest-status feedback

FOLDER ?= fixtures/ingestion
JOB_ID ?=

install:
	pip install -r requirements.txt

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

server:
	python -m core.mcp_fabric.server

frontend:
	cd frontend && python app.py

test:
	pytest -q

ingest:
	python janus_ingest.py --folder $(FOLDER) --recursive

ingest-status:
	python janus_ingest.py --status $(JOB_ID)

feedback:
	python feedback_cli.py
