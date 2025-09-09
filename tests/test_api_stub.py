
import io
import wave
from fastapi.testclient import TestClient
from src.tts_service.api import app
from src.tts_service.config import settings

client = TestClient(app)
def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

def test_voices_requires_api_key():
    r = client.get("/voices")
    assert r.status_code == 401

def test_voices_ok():
    r = client.get("/voices", headers={"X-API-Key": settings.API_KEY})
    assert r.status_code == 200
    data = r.json()
    assert "voices" in data and isinstance(data["voices"], list)
    
def test_synthesize_wav_ok():
    payload = {
        "text": "Hola mundo",
        "voice": "stub-es-Es-1",
        "format": "wav",
        "sample_rate" : 16000,
        "duration_sec" : 0.3,
        "freq_hz" : 440.0
    }
    
    r = client.post("/synthesize", json=payload, headers={"X-API-Key": settings.API_KEY})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/wav")
    content = r.content
    assert content[:4] == b"RIFF"
    with wave.open(io.BytesIO(content), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() > 0
    