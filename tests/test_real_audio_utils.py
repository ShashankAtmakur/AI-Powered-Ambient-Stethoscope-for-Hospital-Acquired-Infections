from edge_ml.real_audio import _parse_optional_float, _resolve_path


def test_parse_optional_float_handles_blank_and_numbers() -> None:
    assert _parse_optional_float("") is None
    assert _parse_optional_float("  ") is None
    assert _parse_optional_float("1.25") == 1.25
    assert _parse_optional_float(None) is None


def test_resolve_path_with_base_dir(tmp_path) -> None:
    resolved = _resolve_path("audio.wav", str(tmp_path))
    assert str(tmp_path) in resolved
    assert resolved.endswith("audio.wav")
