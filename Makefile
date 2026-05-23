.PHONY: up down logs shell migrate test test-unit test-int lint fmt seed backup soak

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f web scheduler

shell:
	docker compose exec web python web/manage.py shell

migrate:
	docker compose exec web python web/manage.py migrate

createsuperuser:
	docker compose exec web python web/manage.py createsuperuser

# tests
test: test-unit test-int

test-unit:
	pytest tests/unit/ -v

test-int:
	docker compose exec web pytest tests/integration/ -v

# lint
lint:
	ruff check .

fmt:
	ruff format .

# seed problems
seed:
	docker compose exec web python web/manage.py import_problems web/data/problems/

# manual backup trigger (cron handles daily)
backup:
	docker compose exec pgdump /backup/pg_dump.sh

# soak harness — Step 11
# usage: make soak USER=admin PASS=...
# override defaults with: SESSIONS=4 DURATION=15 START_INDEX=1
SESSIONS ?= 5
DURATION ?= 60
START_INDEX ?= 0
soak:
	@if [ -z "$(USER)" ] || [ -z "$(PASS)" ]; then \
		echo "usage: make soak USER=<interviewer> PASS=<password>"; exit 1; fi
	python tests/soak/run_5x60_with_chaos.py \
		--base-url http://localhost:8000 \
		--interviewer-user $(USER) --interviewer-pass $(PASS) \
		--sessions $(SESSIONS) --session-duration-min $(DURATION) \
		--start-index $(START_INDEX)
