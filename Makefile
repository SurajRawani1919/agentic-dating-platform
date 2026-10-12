PYTHON ?= backend/.venv/Scripts/python.exe
PIP ?= backend/.venv/Scripts/pip.exe

.PHONY: setup backend-install frontend-install seed run-api run-web test-backend test-frontend demo

setup: backend-install frontend-install seed

backend-install:
	cd backend && python -m venv .venv || true
	$(PIP) install -r backend/requirements.txt

frontend-install:
	cd frontend && npm install

seed:
	cd backend && ../$(PYTHON) -m app.seed_demo || .venv/Scripts/python.exe -m app.seed_demo

run-api:
	cd backend && .venv/Scripts/uvicorn.exe app.main:app --reload --host 0.0.0.0 --port 8000

run-web:
	cd frontend && npm run dev

test-backend:
	cd backend && .venv/Scripts/pytest.exe -q

test-frontend:
	cd frontend && npm test

demo: seed
	@echo "Open http://localhost:5173/demo after starting API + frontend"
