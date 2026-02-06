COMPOSE=docker-compose

.PHONY: help up down restart logs clean shell

help:
	@echo "Usage:"
	@echo "  make up       Start the app (build if needed)"
	@echo "  make down     Stop the app"
	@echo "  make restart  Restart only the Flask app (fast update)"
	@echo "  make logs     View logs (follow mode)"
	@echo "  make clean    Stop and REMOVE DATABASE (Reset everything)"
	@echo "  make shell    Enter the web container shell"

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart web

logs:
	$(COMPOSE) logs -f

shell:
	$(COMPOSE) exec web bash