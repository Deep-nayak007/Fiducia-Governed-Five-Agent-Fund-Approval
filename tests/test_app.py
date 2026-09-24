from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _widget(elements, label):
    return next(element for element in elements if element.label == label)


def test_data_scenario_resets_identity_and_repairs_missing_sharpe():
    app = AppTest.from_file(APP_PATH, default_timeout=20).run()

    _widget(app.selectbox, "Scenario").select("CONFX")
    app.run()
    _widget(app.selectbox, "Scenario").select("DATA")
    app.run()

    asset_class = _widget(app.selectbox, "Asset class")
    assert asset_class.value == "US Equity Index"
    assert asset_class.disabled is True
    assert _widget(app.text_input, "Sharpe ratio").value == ""

    _widget(app.button, "Run governed approval").click()
    app.run(timeout=20)

    state = app.session_state["workflow"]
    assert state["retries"] == 1
    assert state["fund"]["sharpe_ratio"] == 1.01
    assert state["conflicts"] == []
    assert state["recommendation"] == "APPROVE_WITH_CONDITIONS"
    assert state["completed_agents"] == [
        "analyst",
        "compliance",
        "governance",
        "finance",
        "decision_owner",
    ]
    assert not app.exception


def test_custom_identity_mismatch_remains_fail_closed_and_explained():
    app = AppTest.from_file(APP_PATH, default_timeout=20).run()
    _widget(app.selectbox, "Scenario").select("DATA")
    app.run()

    _widget(app.checkbox, "Lock seeded identity").uncheck()
    app.run()
    _widget(app.selectbox, "Asset class").select("International Equity")
    _widget(app.button, "Run governed approval").click()
    app.run(timeout=20)

    state = app.session_state["workflow"]
    assert state["recommendation"] == "ESCALATE"
    assert state["retries"] == 2
    assert state["fund"]["sharpe_ratio"] is None
    assert any("identity mismatch on asset_class" in item for item in state["conflicts"])
    assert any("Seed identity was modified" in warning.value for warning in app.warning)
    assert not app.exception
