import re
from typing import Callable
from num2words import num2words

_number_re = re.compile(r"(?<![\w\d])(\d+)(?![\w\d])")


def normalize_numbers_es(text: str, converter: Callable[[int], str] | None = None) -> str:
    """Convierte números enteros aislados a palabras en español.
    123 -> ciento veintitrés.
    Mantiene formato original para números muy grandes > 10**12.
    """
    if not text or not any(ch.isdigit() for ch in text):
        return text
    conv = converter or (lambda n: num2words(n, lang='es'))

    def _rep(m: re.Match) -> str:
        raw = m.group(1)
        try:
            n = int(raw)
        except ValueError:
            return raw
        if n > 10**12:  # evita textos gigantescos
            return raw
        try:
            w = conv(n)
            return w.replace('-', ' ')
        except Exception:
            return raw
    return _number_re.sub(_rep, text)
