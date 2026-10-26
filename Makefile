.PHONY: up down logs build init-collection test lint clean
up:
	docker compose up -d --build
down:
	docker compose down
logs:
	docker compose logs -f backend
build:
	docker compose build
init-collection:
	docker compose exec backend python -c "import asyncio; from app.rag.retriever import ensure_collection; asyncio.run(ensure_collection())"
test:
	python -m pytest -q tests
lint:
	python -m compileall -q backend/app
clean:
	docker compose down -v
