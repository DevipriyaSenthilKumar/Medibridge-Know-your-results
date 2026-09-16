import asyncio
import io
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image, ImageFilter, ImageOps

from config import get_settings

logger = logging.getLogger(__name__)

_tesseract_available: Optional[bool] = None
_resolved_tesseract_cmd: Optional[str] = None

WINDOWS_TESSERACT_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)


class OCRError(Exception):
    """Raised when text cannot be extracted from an uploaded image."""


def _resolve_tesseract_cmd() -> Optional[str]:
    global _resolved_tesseract_cmd
    if _resolved_tesseract_cmd is not None:
        return _resolved_tesseract_cmd or None

    settings = get_settings()
    candidates: list[str] = []

    if settings.tesseract_cmd:
        candidates.append(settings.tesseract_cmd)

    env_cmd = os.environ.get("TESSERACT_CMD", "")
    if env_cmd:
        candidates.append(env_cmd)

    path_cmd = shutil.which("tesseract")
    if path_cmd:
        candidates.append(path_cmd)

    candidates.extend(WINDOWS_TESSERACT_PATHS)

    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            _resolved_tesseract_cmd = candidate
            logger.info("Using Tesseract at: %s", candidate)
            return candidate

    _resolved_tesseract_cmd = ""
    return None


_tesseract_version_ok: Optional[bool] = None


def _run_tesseract_version(cmd: str) -> bool:
    global _tesseract_version_ok
    if _tesseract_version_ok is not None:
        return _tesseract_version_ok
    try:
        result = subprocess.run(
            [cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        _tesseract_version_ok = result.returncode == 0
    except Exception:
        _tesseract_version_ok = False
    return _tesseract_version_ok


def is_tesseract_available() -> bool:
    global _tesseract_available
    if _tesseract_available is not None:
        return _tesseract_available

    cmd = _resolve_tesseract_cmd()
    if not cmd:
        _tesseract_available = False
        return False

    _tesseract_available = _run_tesseract_version(cmd)
    return _tesseract_available


def _preprocess_image(image: Image.Image) -> Image.Image:
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    width, height = image.size
    if width < 1600:
        scale = 1600 / width
        image = image.resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)
    return image.convert("L")


def _preprocess_image_enhanced(image: Image.Image, binarize_threshold: Optional[int] = None) -> Image.Image:
    """More aggressive pass for low-quality/blurry images: strong upscale + contrast."""
    width, height = image.size
    if width < 2200:
        scale = 2200 / width
        image = image.resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)
    gray = image.convert("L")
    ImageOps.autocontrast(gray).convert("L")
    gray = gray.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    # Binarize to help OCR read low-contrast text. Threshold varies by pass.
    try:
        t = binarize_threshold if binarize_threshold is not None else 140
        return gray.point(lambda p: 255 if p > t else 0)
    except Exception:
        return gray


def _ocr_with_tesseract(image: Image.Image, cmd: str, psm: str = "3") -> str:
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            image.save(tmp.name, format="PNG")
            tmp_path = tmp.name

        result = subprocess.run(
            [cmd, tmp_path, "stdout", "-l", "eng", "--psm", psm],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )

        if result.returncode != 0:
            raise OCRError(result.stderr.strip() or "Tesseract failed to read the image.")

        return result.stdout.strip()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _alnum_score(line: str) -> int:
    return sum(1 for ch in line if ch.isalnum())


def _merge_ocr_variants(variants: list[str]) -> str:
    """Union merge across OCR passes, dropping near-duplicate lines.

    Different passes (PSM modes / thresholds) read the same report with
    slightly different line splits, so index-aligned merging loses rows.
    Instead we keep a unique, normalized line core per line and, when the
    same core appears in several passes, prefer the variant with the highest
    alphanumeric yield. Junk lines that survive are filtered downstream by
    the biomarker extractor (admin filters + recognition + plausibility).
    """
    if not variants:
        return ""
    if len(variants) == 1:
        return variants[0].strip()

    seen_cores: dict[str, tuple[str, int]] = {}
    for variant in variants:
        for line in variant.splitlines():
            core = re.sub(r"[^a-z0-9]+", "", line.strip().lower())
            if not core:
                continue
            cleaned = line.rstrip()
            junk = sum(
                1 for ch in cleaned if not ch.isalnum() and ch not in " .-–—%/^(),:"
            )
            prev, prev_junk = seen_cores.get(core, (None, None))
            if prev is None or junk < prev_junk or (junk == prev_junk and len(cleaned) > len(prev)):
                seen_cores[core] = (cleaned, junk)

    return "\n".join(cleaned for cleaned, _ in seen_cores.values())


async def extract_text_from_image(raw_bytes: bytes) -> str:
    try:
        image = Image.open(io.BytesIO(raw_bytes))
        image = _preprocess_image(image)
    except Exception as exc:
        raise OCRError(f"Invalid or corrupted image file: {exc}") from exc

    cmd = _resolve_tesseract_cmd()
    if not cmd or not _run_tesseract_version(cmd):
        raise OCRError(
            "Tesseract OCR is not installed. "
            "Download: https://github.com/UB-Mannheim/tesseract/wiki "
            "Then add to backend/.env:\n"
            "TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
        )

    # Preprocess all variant images up-front (cheap PIL ops), then run every
    # Tesseract pass CONCURRENTLY — wall time is ~ the slowest single pass,
    # while the union merge keeps every row any pass managed to read.
    # Passes: normal psm3 (default layout) + psm6 (single-block/table layout,
    # reads rows the sparse-mode misses on low-quality scans) + psm3 on a
    # binarized (140) variant which recovers strict table cells (e.g. the
    # decimal in "PCV 40.1" that the plain image misreads as "401").
    pass_specs: list[tuple[object, str]] = [
        (image, "3"),
        (image, "6"),
        (_preprocess_image_enhanced(image, binarize_threshold=140), "3"),
    ]

    results = await asyncio.gather(
        *(
            asyncio.to_thread(_ocr_with_tesseract, img, cmd, psm)
            for img, psm in pass_specs
        ),
        return_exceptions=True,
    )
    texts: list[str] = []
    for res in results:
        if isinstance(res, OCRError):
            raise res
        if isinstance(res, Exception):
            logger.exception("Tesseract OCR pass failed: %s", res)
            raise OCRError(f"OCR failed to read the image: {res}")
        texts.append(res)

    cleaned = _merge_ocr_variants(texts)

    if cleaned:
        logger.info("OCR completed via Tesseract (%d characters, %d passes)", len(cleaned), len(texts))
        return cleaned

    raise OCRError(
        "Could not read any text from this image. "
        "Please upload a clear, well-lit photo of a text-based lab report."
    )
