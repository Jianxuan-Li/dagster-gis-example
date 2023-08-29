dev:
	docker compose -p dagster-dev -f docker/docker-compose.dev.yml run --name backend_dev_container -p 3000:3000 dagster zsh