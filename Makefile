DOCKER_COMPOSE_FILE ?= docker-compose.dev.yaml
DOCKER_COMPOSE_ARGS ?= -f ${DOCKER_COMPOSE_FILE}

all: service-build service-up

service-build:
	docker compose ${DOCKER_COMPOSE_ARGS} build

service-up:
	docker compose ${DOCKER_COMPOSE_ARGS} up -d --remove-orphans

service-down:
	docker compose ${DOCKER_COMPOSE_ARGS} down