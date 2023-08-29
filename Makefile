up:
	mkdir -p ./tmp/geodata
	docker compose -p dagster-dev -f docker/docker-compose.dev.yml run --rm --name backend_dev_container -p 3000:3000 dagster zsh
down:
	docker compose -p dagster-dev -f docker/docker-compose.dev.yml down
dev:
	cd /code/antarcticmap && pip install -e ".[dev]" && dagster dev -h 0.0.0.0