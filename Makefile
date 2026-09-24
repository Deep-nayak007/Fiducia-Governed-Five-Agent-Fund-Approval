.PHONY: setup run demo test deck smoke-agentcore

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt

run:
	.venv/bin/streamlit run app.py

demo:
	.venv/bin/python scripts/run_demo.py --scenario all

test:
	.venv/bin/pytest

deck:
	.venv/bin/python scripts/generate_pitch_deck.py

smoke-agentcore:
	.venv/bin/python scripts/smoke_agentcore.py
