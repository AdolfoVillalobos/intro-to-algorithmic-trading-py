DOCKER_COMPOSE_FILE ?= docker-compose.dev.yaml
DOCKER_COMPOSE_ARGS ?= -f ${DOCKER_COMPOSE_FILE}

all: service-build service-up

install:
	pre-commit install --install-hooks

service-build:
	docker compose ${DOCKER_COMPOSE_ARGS} build

service-up:
	docker compose ${DOCKER_COMPOSE_ARGS} up -d --remove-orphans --force-recreate

service-down:
	docker compose ${DOCKER_COMPOSE_ARGS} down -v
