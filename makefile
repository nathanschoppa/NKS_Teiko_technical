# ── Teiko Technical Assessment ─────────────────────────────────────────────────
# Author: Nathaniel Schoppa
# Date: JULY 02 2026
# Usage:
#   setup   — install dependencies
#   pipeline       — initialize database, load data, create results
#   dashboard      — launch the dashboard
#   test      	   — run the test suite
#   clean          — remove generated database and log files

setup:
	pip install -r requirements.txt

pipeline:
	python load_data.py
	python generate_outputs.py

dashboard:
	python teiko_display.py

test:
	pytest tests/ -v --tb=short

clean:
	rm -f teiko.db
	rm -f teiko.log

.PHONY: setup pipeline dashboard test clean
