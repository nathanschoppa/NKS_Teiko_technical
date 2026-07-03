# ── Teiko Technical Assessment ─────────────────────────────────────────────────
# Author: Nathaniel Schoppa
# Date: JULY 02 2026
# Usage:
#   make install   — install dependencies
#   make init      — initialize database and load data
#   make run       — launch the dashboard
#   make test      — run the test suite
#   make all       — install, init, and run
#   make clean     — remove generated database and log files

# ── Configuration ───────────────────────────────────────────────────────────────
PYTHON    = python
PIP       = pip
DB_FILE   = teiko.db
LOG_FILE  = teiko.log
DATA_FILE = cell-count.csv

# ── Targets ─────────────────────────────────────────────────────────────────────

# Install all dependencies from requirements.txt
install:
	$(PIP) install -r requirements.txt

# Initialize the database and load data from CSV
# Skips loading if the database already exists
init:
	@echo "Initializing database..."
	@if [ -f $(DB_FILE) ]; then \
		echo "Database already exists at $(DB_FILE) — re-running load (duplicates will be skipped)."; \
	fi
	$(PYTHON) load_cell.py
	@echo "Database ready."

# Launch the Dash dashboard
run:
	@echo "Starting Teiko dashboard at http://localhost:8050"
	$(PYTHON) teiko_display.py

# Run the test suite with verbose output
test:
	@echo "Running tests..."
	pytest tests/ -v --tb=short

# Install, initialize, and run — full setup from scratch
all: install init run

# Remove generated files — does not affect source code or CSV
clean:
	@echo "Cleaning generated files..."
	@rm -f $(DB_FILE)
	@rm -f $(LOG_FILE)
	@echo "Clean complete."

# Declare non-file targets
.PHONY: install init run test all clean
