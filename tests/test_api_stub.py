
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
        "voice": "piper-es-ES-mls-medium",
        "format": "wav"
    }
    
    r = client.post("/synthesize", json=payload, headers={"X-API-Key": settings.API_KEY})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/wav")
    content = r.content
    assert content[:4] == b"RIFF"
    with wave.open(io.BytesIO(content), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 22050
        assert wf.getnframes() > 0

def test_synthesize_with_numbers():
    payload = {
        "text": "Tengo 123 manzanas",
        "voice": "piper-es-ES-mls-medium",
        "format": "wav"
    }
    r = client.post("/synthesize", json=payload, headers={"X-API-Key": settings.API_KEY})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/wav")
    assert r.content[:4] == b"RIFF"

def test_synthesize_with_prosody_rate():
    payload = {
        "text": "Hola mundo de prueba",
        "voice": "piper-es-ES-mls-medium",
        "format": "wav",
        "speaking_rate": 1.5
    }
    r = client.post("/synthesize", json=payload, headers={"X-API-Key": settings.API_KEY})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/wav")
    assert r.content[:4] == b"RIFF"

def test_synthesize_with_emotion():
    payload = {
        "text": "Hola esto es una prueba emocionada",
        "voice": "piper-es-ES-mls-medium",
        "format": "wav",
        "emotion": "happy"
    }
    r = client.post("/synthesize", json=payload, headers={"X-API-Key": settings.API_KEY})
    assert r.status_code == 200
    assert r.content[:4] == b"RIFF"
    