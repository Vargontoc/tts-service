import json
from typing import Dict, Optional, Tuple

DEFAULT_EMOTIONS: Dict[str, Tuple[float, float, float]] = {
    # emotion: (speaking_rate, pitch_shift, energy)
    "neutral": (1.0, 0.0, 1.0),
    "happy": (1.1, 2.0, 1.1),
    "sad": (0.9, -1.5, 0.9),
    "angry": (1.15, 1.5, 1.2),
    "calm": (0.95, -0.5, 0.95)
}


def load_custom_emotions(raw: str) -> Dict[str, Tuple[float, float, float]]:
    if not raw.strip():
        return {}
    if raw.strip().startswith('{'):
        try:
            data = json.loads(raw)
            out: Dict[str, Tuple[float, float, float]] = {}
            for k, v in data.items():
                if isinstance(v, (list, tuple)) and len(v) == 3:
                    out[k.lower()] = (float(v[0]), float(v[1]), float(v[2]))
            return out
        except Exception:
            return {}
    # CSV: emotion=rate,pitch,energy;emotion2=...
    parts = [p for p in raw.split(';') if p.strip()]
    out: Dict[str, Tuple[float, float, float]] = {}
    for p in parts:
        if '=' not in p:
            continue
        name, vals = p.split('=', 1)
        comps = [x.strip() for x in vals.split(',') if x.strip()]
        if len(comps) != 3:
            continue
        try:
            out[name.lower().strip()] = (float(comps[0]), float(comps[1]), float(comps[2]))
        except ValueError:
            continue
    return out


def resolve_emotion(emotion: Optional[str], custom: Dict[str, Tuple[float, float, float]]):
    if not emotion:
        return None
    e = emotion.lower()
    if e in custom:
        return custom[e]
    if e in DEFAULT_EMOTIONS:
        return DEFAULT_EMOTIONS[e]
    return None
