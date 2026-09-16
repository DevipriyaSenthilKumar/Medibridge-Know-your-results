"""Server-side neural text-to-speech (edge-tts with gTTS fallback).

Browser speechSynthesis is unreliable: for Hindi/Tamil it needs an OS voice
installed, otherwise it silently skips Devanagari/Tamil script and only reads
digits. Synthesizing on the server means every browser and OS gets the same
professional female voice:

  en -> en-IN-NeerjaNeural   hi -> hi-IN-SwaraNeural
  ta -> ta-IN-PallaviNeural

If the Microsoft Edge endpoint is unreachable (network/region flakiness) we
fall back to Google Translate TTS (gTTS), so speech still works offline-ish.

Audio is cached on disk keyed by (language, text); repeating a section is
instant and costs no extra network round-trips.
"""
import asyncio
import hashlib
import logging
import os
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

_EDGE_VOICES = {
    "en": "en-IN-NeerjaNeural",
    "hi": "hi-IN-SwaraNeural",
    "ta": "ta-IN-PallaviNeural",
}

_GTTS_LANGS = {"en": "en", "hi": "hi", "ta": "ta"}

_CACHE_DIR = Path(__file__).resolve().parent.parent / "tts_cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

_MAX_TEXT_CHARS = 6000


class TTSUnavailable(Exception):
    """Raised when no working TTS provider is available."""


def _load_edge_tts():
    try:
        import edge_tts  # type: ignore

        return edge_tts
    except Exception as exc:  # pragma: no cover - depends on environment
        _LOGGER.warning("edge-tts not importable: %s", exc)
        return None


def _load_gtts():
    try:
        from gtts import gTTS  # type: ignore

        return gTTS
    except Exception as exc:  # pragma: no cover - depends on environment
        _LOGGER.warning("gTTS not importable: %s", exc)
        return None


async def _synthesize_edge(edge, text: str, voice: str, tmp_path: Path) -> bool:
    try:
        communicate = edge.Communicate(text, voice=voice, rate="+0%", pitch="+0Hz")
        await communicate.save(str(tmp_path))
    except Exception as exc:
        _LOGGER.warning("edge-tts synthesis failed for %s: %s", voice, exc)
        return False
    return tmp_path.exists() and tmp_path.stat().st_size > 0


async def _synthesize_gtts(gtts, text: str, lang_code: str, tmp_path: Path) -> bool:
    def _run() -> None:
        gtts(text=text, lang=lang_code, slow=False).save(str(tmp_path))

    try:
        await asyncio.to_thread(_run)
    except Exception as exc:  # noqa: BLE001 - any failure means fall back
        _LOGGER.warning("gTTS synthesis failed for %s: %s", lang_code, exc)
        return False
    return tmp_path.exists() and tmp_path.stat().st_size > 0


async def synthesize_speech(text: str, language: str = "en") -> Path:
    """Synthesize ``text`` to an MP3 file and return its cached path."""
    text = (text or "").strip()
    if not text:
        raise ValueError("No text provided for synthesis")
    if len(text) > _MAX_TEXT_CHARS:
        text = text[:_MAX_TEXT_CHARS]

    digest = hashlib.sha256(f"{language}:{text}".encode("utf-8")).hexdigest()[:24]
    out_path = _CACHE_DIR / f"{digest}.mp3"
    if out_path.exists():
        return out_path

    tmp_path = _CACHE_DIR / f"{digest}.tmp.mp3"
    if tmp_path.exists():
        tmp_path.unlink()

    edge = _load_edge_tts()
    if edge is not None:
        voice = _EDGE_VOICES.get(language, _EDGE_VOICES["en"])
        if await _synthesize_edge(edge, text, voice, tmp_path):
            _commit(tmp_path, out_path, "edge-tts", voice)
            return out_path
        if tmp_path.exists():
            tmp_path.unlink()

    gtts = _load_gtts()
    if gtts is not None:
        lang_code = _GTTS_LANGS.get(language, _GTTS_LANGS["en"])
        if await _synthesize_gtts(gtts, text, lang_code, tmp_path):
            _commit(tmp_path, out_path, "gTTS", f"lang-{lang_code}")
            return out_path
        if tmp_path.exists():
            tmp_path.unlink()

    raise TTSUnavailable(
        "Neither edge-tts nor gTTS could synthesize audio. Check your internet connection."
    )


def _commit(tmp: Path, out: Path, provider: str, voice: str) -> None:
    os.replace(tmp, out)
    _LOGGER.info(
        "TTS synthesized %s bytes via %s (%s) -> %s",
        out.stat().st_size,
        provider,
        voice,
        out.name,
    )