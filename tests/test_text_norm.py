from tts_service.utils.text_norm import normalize_numbers_es

def test_normalize_numbers_basic():
    assert normalize_numbers_es("Tengo 2 perros y 15 gatos") != "Tengo 2 perros y 15 gatos"
    out = normalize_numbers_es("Tengo 2 perros y 15 gatos")
    assert "dos" in out and "quince" in out
