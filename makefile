init:
    python load_cell.py

run:
    python app.py

test:
    pytest tests/

all: init run