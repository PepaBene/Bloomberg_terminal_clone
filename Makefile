.PHONY: up down migrate seed ingest-edgar ingest-gleif ingest-figi test quality dev

up:
	docker compose up -d

down:
	docker compose down

migrate:
	alembic upgrade head

seed:
	python -m scripts.seed_reference

ingest-edgar:
	python -m scripts.ingest_edgar

ingest-gleif:
	python -m scripts.ingest_gleif

ingest-figi:
	python -m scripts.ingest_openfigi

test:
	pytest -v

quality:
	python -m scripts.run_quality_check

dev:
	uvicorn src.api.app:create_app --factory --reload --host 0.0.0.0 --port 8000
