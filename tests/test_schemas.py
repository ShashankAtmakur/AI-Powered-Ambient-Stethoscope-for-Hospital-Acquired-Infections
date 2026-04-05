from shared.schemas import PatientScenario, RoomEvent


def test_patient_scenarios_include_new_profiles() -> None:
    values = {scenario.value for scenario in PatientScenario}
    assert "normal" in values
    assert "deteriorating" in values
    assert "pneumonia_like" in values
    assert "uri_like" in values
    assert "sleep_apnea_like" in values


def test_room_event_defaults_are_privacy_safe() -> None:
    event = RoomEvent(room_id="312A")
    assert event.cough_detected is False
    assert event.coughs_per_min >= 0.0
    assert event.spo2_pct <= 100.0
    assert event.temperature_c >= 35.0
    assert event.anomaly_label == "normal"
