from app.call_guard.analyzer import SCHEME_LABELS
from app.call_guard.scenarios import load_scenario
from app.eval import evaluate, run_conversation


def test_telecom_egov_scenario_reaches_high():
    r = run_conversation(load_scenario("scam_telecom_egov")["lines"])
    assert r["level"] == "high", r
    assert r["scheme"] == "telecom_egov"
    assert "telecom_egov" in SCHEME_LABELS


def test_relative_dtp_scenario_reaches_high():
    r = run_conversation(load_scenario("scam_relative_dtp")["lines"])
    assert r["level"] == "high", r
    assert r["scheme"] == "relative_in_trouble"


def test_existing_scenarios_keep_their_levels():
    assert run_conversation(load_scenario("scam_security_ru")["lines"])["scheme"] == "safe_account"
    assert run_conversation(load_scenario("scam_kz")["lines"])["level"] == "high"
    for name in ("normal_doctor", "normal_delivery", "normal_son"):
        assert run_conversation(load_scenario(name)["lines"])["level"] == "low", name


def test_evaluate_contract():
    res = evaluate()
    n, s = res["normal"], res["scam"]
    assert set(n) == {"total", "alarms_medium", "alarms_high", "rate"}
    assert set(s) == {"total", "detected_high", "detected_medium", "rate"}
    assert n["total"] >= 25 and s["total"] >= 10
    assert len(res["items"]) == n["total"] + s["total"]
    assert all(set(i) == {"title", "kind", "risk", "level"} for i in res["items"])
    assert n["rate"] == round((n["alarms_medium"] + n["alarms_high"]) / n["total"], 3)
    assert s["rate"] == round(s["detected_high"] / s["total"], 3)
