"""Extract clinical biomarkers and strip administrative lab-report metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Final

ADMIN_LINE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"^\s*(?:patient\s*name|name)\s*[:=]", re.I),
    re.compile(r"^\s*(?:age|sex|gender)\s*[:=]", re.I),
    re.compile(r"^\s*(?:uhid|patient\s*id|mrn|accession)\s*[:=]", re.I),
    re.compile(r"^\s*(?:ref\.?\s*by|referred\s*by|referring\s*doctor)\s*[:=]", re.I),
    re.compile(r"^\s*(?:sample\s*collected|specimen\s*collected|collection\s*(?:date|time))\s*[:=]", re.I),
    re.compile(r"^\s*(?:registered\s*on|registration\s*date)\s*[:=]", re.I),
    re.compile(r"^\s*(?:collected\s*on|received\s*on)\s*[:=]", re.I),
    re.compile(r"^\s*(?:reported\s*on|report\s*date|released\s*on)\s*[:=]", re.I),
    re.compile(r"^\s*(?:tat|turnaround\s*time)\s*[:=]", re.I),
    re.compile(r"^\s*(?:instrument|analyzer|equipment|method)\s*[:=]", re.I),
    re.compile(r"^\s*(?:lab(?:oratory)?\s*name|hospital|clinic|address)\s*[:=]", re.I),
    re.compile(r"^\s*(?:bill\s*no|invoice|barcode|qr\s*code)\s*[:=]", re.I),
    re.compile(r"^\s*(?:dob|date\s*of\s*birth)\s*[:=]", re.I),
    re.compile(r"^\s*(?:phone|mobile|email)\s*[:=]", re.I),
    # Colon-less OCR forms of the same headers ("Age 21 Years", "PID 555",
    # "Registered on: 02 PM" when the colon is dropped/mangled).
    re.compile(r"^\s*(?:age|sex|gender|dob)\b", re.I),
    re.compile(r"^\s*(?:uhid|patient\s*id|pid|mrn|accession)\b", re.I),
    re.compile(r"^\s*(?:registered|collected|reported|received|released|generated)\s+on\b", re.I),
    re.compile(r"\b(?:generated|registered|collected|reported|received)\s+on\b", re.I),
)

ADMIN_METRIC_NAMES: Final[frozenset[str]] = frozenset(
    name.lower()
    for name in (
        "Patient Name",
        "Name",
        "Age",
        "Sex",
        "Gender",
        "UHID",
        "Patient ID",
        "MRN",
        "Ref By",
        "Referred By",
        "Sample Collected At",
        "Registered On",
        "Collected On",
        "Reported On",
        "TAT",
        "Turnaround Time",
        "Instrument",
        "Lab Name",
        "Hospital",
        "Address",
        "DOB",
        "Date of Birth",
        "Phone",
        "Email",
        "PID",
        "ID",
        "Registered On",
        "Collected On",
        "Reported On",
        "Received On",
        "Generated On",
        "Sample Type",
    )
)

BIOMARKER_LINE_PATTERN = re.compile(
    r"^\s*([A-Za-z][A-Za-z0-9\s()/.%#=-]{1,90}?)\s*=?\s*(?:F\s*\d+\s*\*)?"
    r"((?:[\d.,]+)(?:\s*(?:10[\^]?\d+(?:°|º)?/L|mg/dL|g/dL|mmol/L|U/L|u/L|IU/L|mIU/mL|uIU/mL|ng/mL|%|pg|fL|/L|/dL|/uL|mEq/L|K/uL|M/uL))?)"
    r"\s+(.+)?$",
    re.MULTILINE,
)

METRIC_VALUE_PATTERN = re.compile(
    r"(?:^|\n)\s*([A-Za-z][A-Za-z0-9\s()/-]{2,90}?)\s*[:=]\s*"
    r"([\d.]+\s*(?:mg/dL|g/dL|mmol/L|U/L|u/L|IU/L|mIU/mL|uIU/mL|ng/mL|/L|/dL|/uL|x10[\^]?\d+/uL|%|pg|fL|mEq/L|K/uL|M/uL)?)"
    r"(?:\s*[\(\[,]?\s*(?:ref(?:erence)?\.?|normal)\s*[:=]?\s*([^)\]\n]+))?",
    re.IGNORECASE | re.MULTILINE,
)

INLINE_RANGE_PATTERN = re.compile(
    r"(?:reference|ref\.?|normal)\s*[:=]?\s*([<>]?\s*[\d.]+\s*[-–—]\s*[\d.]+\s*(?:\w+)?|[<>]?\s*[\d.]+\s*(?:\w+)?)",
    re.IGNORECASE,
)

# OCR often mangles the "Normal"/"Ref" label (e.g. "Necmad 42-50", "Nocmet
# 150-410"). Pull the numeric range out even when the label is garbled.
GENERIC_RANGE_PATTERN = re.compile(
    r"([<>]?\s*\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)(?:\s*(?:mg/dL|g/dL|mmol/L|/L|/dL|/uL|%|pg|fL|cumm|mm|10\^?\d+))?",
    re.IGNORECASE,
)

SINGLE_VALUE_PATTERN = re.compile(r"[<>]?\s*\d+(?:\.\d+)?")


def _clean_reference(raw: str) -> str:
    """Extract a readable reference range, tolerating OCR-garbled labels."""
    text = (raw or "").strip("()[] \t.\n")
    if not text:
        return "See lab report"

    labelled = INLINE_RANGE_PATTERN.search(text)
    if labelled:
        return labelled.group(1).strip()

    numeric = GENERIC_RANGE_PATTERN.search(text)
    if numeric:
        return f"{numeric.group(1).strip()}-{numeric.group(2)}"

    single = SINGLE_VALUE_PATTERN.search(text)
    if single:
        return single.group(0).strip()

    return text or "See lab report"

# Canonical biomarker names with common aliases and OCR misspellings.
# Each key is the canonical display name; values are lowercase aliases.
CANONICAL_BIOMARKERS: Final[dict[str, tuple[str, ...]]] = {
    "Hemoglobin (Hb)": (
        "hemoglobin",
        "hemaglobin",
        "hemoglobin (hb)",
        "hemaglobin (he)",
        "hemoglobin(hb)",
        "haemoglobin",
        "hgb",
        "hb",
    ),
    "Red Blood Cells (RBC)": (
        "red blood cells (rbc)",
        "red blood cell count",
        "total rbc count",
        "total rec count",
        "red blood corpuscles",
        "rbc",
        "rbc count",
    ),
    "White Blood Cells (WBC)": (
        "white blood cells (wbc)",
        "white blood cell count",
        "total wbc count",
        "total leucocyte count",
        "total leukocyte count",
        "leukocytes",
        "leucocytes",
        "wbc",
        "wbc count",
    ),
    "Platelets": (
        "platelets",
        "platelet count",
        "thaletets",
        "plt",
        "platelet",
        "plts",
        "plat",
        "plt count",
        "platelet count (plt)",
    ),
    "Packed Cell Volume (PCV)": (
        "packed cell volume (pcv)",
        "packed cell volume",
        "platelet cell volume (pcv)",
        "pictisd cal velen (cy)",
        "pictisd cal velen cy",
        "hematocrit",
        "haematocrit",
        "hct",
        "pcv",
    ),
    "Mean Corpuscular Volume (MCV)": (
        "mean corpuscular volume (mcv)",
        "mean corpuscular volume (mcw)",
        "mean corpuscufar volume (mcw)",
        "mean corpuscular volume(mcw)",
        "mean corpuscular volume",
        "mcv",
        "mcw",
    ),
    "Mean Corpuscular Hemoglobin (MCH)": (
        "mean corpuscular hemoglobin (mch)",
        "mean corpuscular haemoglobin",
        "mch",
    ),
    "Mean Corpuscular Hemoglobin Concentration (MCHC)": (
        "mean corpuscular hemoglobin concentration (mchc)",
        "mchc",
    ),
    "Red Cell Distribution Width (RDW)": (
        "red cell distribution width (rdw)",
        "red blood cell distribution width",
        "rdw",
        "rdw-cv",
        "rdw-sd",
    ),
    "Glucose": (
        "glucose",
        "blood glucose",
        "blood sugar",
        "glucose (fasting)",
        "glucose fasting",
        "fasting blood sugar",
        "fbs",
        "rbs",
        "bsl",
    ),
    "HbA1c": (
        "hba1c",
        "glycated hemoglobin",
        "glycosylated haemoglobin",
        "hemoglobin a1c",
        "hemoglobin a1c (hba1c)",
    ),
    "Total Cholesterol": (
        "total cholesterol",
        "cholesterol",
        "cholestrol",
        "serum cholesterol",
    ),
    "Triglycerides": (
        "triglycerides",
        "triglyceride",
        "tg",
    ),
    "HDL Cholesterol": (
        "hdl cholesterol",
        "hdl",
        "high density lipoprotein",
    ),
    "LDL Cholesterol": (
        "ldl cholesterol",
        "ldl",
        "low density lipoprotein",
    ),
    "Creatinine": (
        "creatinine",
        "serum creatinine",
        "creatinine (serum)",
    ),
    "Blood Urea Nitrogen (BUN)": (
        "blood urea nitrogen (bun)",
        "blood urea nitrogen",
        "bun",
        "urea",
    ),
    "Sodium (Na+)": (
        "sodium (na+)",
        "sodium",
        "serum sodium",
        "na",
    ),
    "Potassium (K+)": (
        "potassium (k+)",
        "potassium",
        "serum potassium",
        "k",
    ),
    "Calcium": (
        "calcium",
        "serum calcium",
        "ca",
    ),
    "TSH": (
        "tsh",
        "thyroid stimulating hormone",
        "thyroid-stimulating hormone",
    ),
    "T3 (Triiodothyronine)": (
        "t3",
        "triiodothyronine",
        "total t3",
    ),
    "T4 (Thyroxine)": (
        "t4",
        "thyroxine",
        "total t4",
    ),
    "ALT (SGPT)": (
        "alt (sgpt)",
        "alt",
        "sgpt",
        "alanine aminotransferase",
        "alanine transaminase",
    ),
    "AST (SGOT)": (
        "ast (sgot)",
        "ast",
        "sgot",
        "aspartate aminotransferase",
        "aspartate transaminase",
    ),
    "Bilirubin (Total)": (
        "bilirubin (total)",
        "total bilirubin",
        "bilirubin",
    ),
    "Alkaline Phosphatase": (
        "alkaline phosphatase",
        "alp",
        "alk phos",
    ),
    "Total Protein": (
        "total protein",
        "serum total protein",
    ),
    "Albumin": (
        "albumin",
        "serum albumin",
    ),
    "Uric Acid": (
        "uric acid",
        "serum uric acid",
    ),
    "C-Reactive Protein (CRP)": (
        "c-reactive protein (crp)",
        "c-reactive protein",
        "crp",
    ),
    "Lymphocytes": (
        "lymphocytes",
        "lymphocyte count",
        "lymphocytes (%)",
        "lym#",
        "lym",
        "lymph#",
        "lymph",
        "lymphocyte",
        "lym count",
    ),
    "Neutrophils": (
        "neutrophils",
        "neutrophil count",
        "neutrophils (%)",
        "neut#",
        "neut",
        "neut%",
        "neurophils",
        "neutrophils (n)",
        "neut count",
    ),
    "Eosinophils": (
        "eosinophils",
        "eosinophil count",
        "eosinophils (%)",
    ),
    "Monocytes": (
        "monocytes",
        "monocyte count",
        "monocytes (%)",
        "mxd#",
        "mxd",
        "mix#",
        "mid#",
        "mono#",
        "mono",
        "monocyte",
    ),
    "Basophils": (
        "basophils",
        "basophil count",
        "basophils (%)",
    ),
    "Ferritin": (
        "ferritin",
        "serum ferritin",
    ),
    "ESR": (
        "esr",
        "erythrocyte sedimentation rate",
    ),
    "T3 (Triiodothyronine)": (
        "t3",
        "triiodothyronine",
        "total t3",
        "free t3",
        "t3 (free)",
    ),
    "T4 (Thyroxine)": (
        "t4",
        "thyroxine",
        "total t4",
        "free t4",
        "fT4",
    ),
    "Vitamin B12": (
        "vitamin b12",
        "b12",
        "vitamin b-12",
        "cobalamin",
    ),
    "Vitamin D": (
        "vitamin d",
        "vitamin d3",
        "25-hydroxy vitamin d",
        "25 oh vitamin d",
    ),
    "Iron (Serum)": (
        "iron",
        "serum iron",
        "serum iron (fe)",
    ),
    "TIBC": (
        "tibc",
        "total iron binding capacity",
    ),
    "Transferrin Saturation": (
        "transferrin saturation",
        "tsat",
    ),
    "Chloride (Cl-)": (
        "chloride (cl-)",
        "chloride",
        "serum chloride",
        "cl",
    ),
    "Bicarbonate": (
        "bicarbonate",
        "serum bicarbonate",
        "co2",
        "carbon dioxide",
        "hco3",
    ),
    "Amylase": (
        "amylase",
        "serum amylase",
    ),
    "Lipase": (
        "lipase",
        "serum lipase",
    ),
    "GGT": (
        "ggt",
        "gamma gt",
        "gamma-glutamyl transferase",
        "gamma-glutamyltransferase",
    ),
    "LDH": (
        "ldh",
        "lactate dehydrogenase",
        "lactic dehydrogenase",
    ),
    "Creatine Kinase (CK)": (
        "creatine kinase (ck)",
        "creatine kinase",
        "cpk",
        "ck total",
    ),
    "Troponin I": (
        "troponin i",
        "troponin",
        "hs troponin",
    ),
    "D-Dimer": (
        "d-dimer",
        "d dimer",
    ),
    "Fibrinogen": (
        "fibrinogen",
        "plasma fibrinogen",
    ),
    "INR": (
        "inr",
        "international normalized ratio",
    ),
    "Prothrombin Time (PT)": (
        "prothrombin time (pt)",
        "prothrombin time",
        "pt",
    ),
    "APTT": (
        "aptt",
        "activated partial thromboplastin time",
    ),
    "Magnesium": (
        "magnesium",
        "serum magnesium",
        "mg",
    ),
    "Phosphorus": (
        "phosphorus",
        "serum phosphorus",
        "phosphate",
    ),
    "Albumin/Globulin (A/G) Ratio": (
        "albumin/globulin (a/g) ratio",
        "a/g ratio",
        "albumin globulin ratio",
        "ag ratio",
    ),
    "Reticulocyte Count": (
        "reticulocyte count",
        "reticulocytes",
    ),
    "Platelet Distribution Width (PDW)": (
        "platelet distribution width (pdw)",
        "platelet distribution width",
        "pdw",
    ),
    "Mean Platelet Volume (MPV)": (
        "mean platelet volume (mpv)",
        "mean platelet volume",
        "mpv",
    ),
    "Procalcitonin (PCT)": (
        "procalcitonin",
        "procalcitonin (pct)",
        "pct (procalcitonin)",
    ),
    "Plateletcrit (PCT)": (
        "plateletcrit (pct)",
        "plateletcrit",
        "platelet crit",
        "pct",
    ),
}


def _canonical_key(raw_name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", raw_name.lower())


def normalize_biomarker_name(raw_name: str) -> str:
    """Map OCR-garbled biomarker names to a canonical display name.

    First tries an exact alias match, then fuzzy-matches against canonical
    names so typo-laden OCR output still gets corrected.
    """
    cleaned = _clean_name(raw_name)
    if not cleaned:
        return cleaned

    lowered = cleaned.lower()

    for canonical, aliases in CANONICAL_BIOMARKERS.items():
        if lowered in aliases:
            return canonical

    best_name = cleaned
    best_score = 0.55
    for canonical in CANONICAL_BIOMARKERS:
        score = SequenceMatcher(None, canonical.lower(), lowered).ratio()
        if score > best_score:
            best_score = score
            best_name = canonical

    return best_name


def _build_known_names() -> set[str]:
    names = set(CANONICAL_BIOMARKERS)
    for aliases in CANONICAL_BIOMARKERS.values():
        names.update(aliases)
    return names


_KNOWN_NAMES: Final[frozenset[str]] = frozenset(
    name.lower() for name in _build_known_names()
)


def is_recognized_biomarker(raw_name: str) -> bool:
    """Return True if the name maps to a known canonical biomarker.

    Used to drop OCR garbage (e.g. misread headers) that slipped through the
    line-based extraction but is not a real clinical parameter.
    """
    cleaned = _clean_name(raw_name)
    if not cleaned:
        return False
    lowered = cleaned.lower()
    if lowered in _KNOWN_NAMES:
        return True
    return normalize_biomarker_name(cleaned).lower() != lowered


@dataclass
class BiomarkerRow:
    name: str
    value: str
    reference: str
    status: str  # within_range | high | low | unknown


def _clean_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip(" :-=*")


def _is_admin_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) < 3:
        return True
    for pattern in ADMIN_LINE_PATTERNS:
        if pattern.search(stripped):
            return True
    lowered = _clean_name(stripped).lower()
    if lowered in ADMIN_METRIC_NAMES:
        return True
    if re.match(r"^(investigation|result|reference|test name|parameter)\s*$", stripped, re.I):
        return False
    return False


def _parse_numeric(value_str: str) -> float | None:
    match = re.search(r"([\d.]+)", value_str.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


_SCI_UNIT = re.compile(r"(?<=\d)(10[\^]?\d+(?:°|º)?/L)", re.IGNORECASE)

_SCI_UNIT_DEGENERATE = re.compile(r"(?<=\d)((?:10)?[\^]?\d+(?:°|º)\d?/L)", re.IGNORECASE)


# Short, unambiguous tokens that identify a biomarker even when the rest of
# the row (value/reference) is OCR-corrupted. Used to surface unreadable rows
# as "Could not read" instead of silently dropping them.
_SHORTCODE_TO_CANONICAL: Final[dict[str, str]] = {
    "hgb": "Hemoglobin (Hb)",
    "hb": "Hemoglobin (Hb)",
    "rbc": "Red Blood Cells (RBC)",
    "wbc": "White Blood Cells (WBC)",
    "plt": "Platelets",
    "plts": "Platelets",
    "plat": "Platelets",
    "hct": "Packed Cell Volume (PCV)",
    "pcv": "Packed Cell Volume (PCV)",
    "mcv": "Mean Corpuscular Volume (MCV)",
    "mch": "Mean Corpuscular Hemoglobin (MCH)",
    "mchc": "Mean Corpuscular Hemoglobin Concentration (MCHC)",
    "rdw": "Red Cell Distribution Width (RDW)",
    "rdw-cv": "Red Cell Distribution Width (RDW)",
    "rdw-sd": "Red Cell Distribution Width (RDW)",
    "mpv": "Mean Platelet Volume (MPV)",
    "pdw": "Platelet Distribution Width (PDW)",
    "esr": "ESR",
    # NOTE: "PCT" is deliberately NOT mapped here. On CBC reports PCT is
    # Plateletcrit (%), on inflammatory panels it is Procalcitonin (ng/mL).
    # Without a reliable unit the two collide, so we never force-list it.
    "lym#": "Lymphocytes",
    "lymph#": "Lymphocytes",
    "lym": "Lymphocytes",
    "neut#": "Neutrophils",
    "neut": "Neutrophils",
    "mxd#": "Monocytes",
    "mono#": "Monocytes",
    "mono": "Monocytes",
    "mid#": "Monocytes",
    "fbs": "Glucose",
    "rbs": "Glucose",
    "bsl": "Glucose",
    "hba1c": "HbA1c",
    "alt": "ALT (SGPT)",
    "sgpt": "ALT (SGPT)",
    "ast": "AST (SGOT)",
    "sgot": "AST (SGOT)",
    "alp": "Alkaline Phosphatase",
    "ggt": "GGT",
    "ldh": "LDH",
    "ck": "Creatine Kinase (CK)",
    "cpk": "Creatine Kinase (CK)",
    "crp": "C-Reactive Protein (CRP)",
    "tsh": "TSH",
    "t3": "T3 (Triiodothyronine)",
    "t4": "T4 (Thyroxine)",
    "pt": "Prothrombin Time (PT)",
    "inr": "INR",
    "aptt": "APTT",
    "bun": "Blood Urea Nitrogen (BUN)",
    "tibc": "TIBC",
    "ferritin": "Ferritin",
    "troponin": "Troponin I",
    "d-dimer": "D-Dimer",
    "fibrinogen": "Fibrinogen",
}


def _detect_biomarker_by_shortcode(line: str) -> str | None:
    """Return a canonical biomarker if the line's leading token is a known short code."""
    head = re.match(r"[A-Za-z][A-Za-z0-9#\-#]*", line.strip())
    if not head:
        return None
    token = head.group(0).lower()
    return _SHORTCODE_TO_CANONICAL.get(token)


def _split_glued_value(value_str: str) -> str:
    """Strip an OCR-glued scientific unit (e.g. '18.110°9/L') off a value.

    Automated hematology analyzers print values like 'NEUT# 18.1 10^9/L';
    blurred OCR frequently glues them as '18.110°9/L'. Detect the unit and
    return just the leading number so the status comparison works.
    """
    value_str = value_str.strip()
    # Strip OCR junk that leaks in front of the number (currency symbols,
    # stray '=', quotes, etc.) e.g. "$22.1" or "=73.5".
    value_str = re.sub(r"^[^\w.\d+]+", "", value_str)
    match = _SCI_UNIT.search(value_str)
    if not match:
        match = _SCI_UNIT_DEGENERATE.search(value_str)
    if match and match.start() > 0:
        return value_str[: match.start()].strip()
    return value_str


def _normalize_sci_unit(line: str) -> str:
    """Insert a space before a sci-unit that OCR glued to the value digit."""
    line = _SCI_UNIT.sub(r" \1", line)
    return _SCI_UNIT_DEGENERATE.sub(r" \1", line)


def _parse_reference_bounds(reference: str) -> tuple[float | None, float | None, str | None]:
    reference = reference.strip()
    if not reference or reference.lower() in ("see your lab report", "n/a", "-"):
        return None, None, None

    less_than = re.match(r"<\s*([\d.]+)", reference)
    if less_than:
        return None, float(less_than.group(1)), "less_than"

    greater_than = re.match(r">\s*([\d.]+)", reference)
    if greater_than:
        return float(greater_than.group(1)), None, "greater_than"

    range_match = re.search(r"([\d.]+)\s*[-–—]\s*([\d.]+)", reference)
    if range_match:
        return float(range_match.group(1)), float(range_match.group(2)), "range"

    return None, None, None


def _compare_to_reference(value_str: str, reference: str) -> str:
    value = _parse_numeric(value_str)
    if value is None:
        return "unknown"

    low, high, bound_type = _parse_reference_bounds(reference)
    if bound_type == "less_than" and high is not None:
        if value >= high:
            return "high"
        return "within_range"
    if bound_type == "greater_than" and low is not None:
        if value <= low:
            return "low"
        return "within_range"
    if bound_type == "range" and low is not None and high is not None:
        if value < low:
            return "low"
        if value > high:
            return "high"
        return "within_range"
    return "unknown"


# Physiologically-plausible value bounds (very wide). Used only to catch
# obvious OCR digit-insertion garbage (e.g. MCV 473, PCV 426%, RDW 433) so a
# wrong number is never presented as a real lab value.
_VALUE_PLAUSIBLE: Final[dict[str, tuple[float, float]]] = {
    "Hemoglobin (Hb)": (3.0, 25.0),
    "Red Blood Cells (RBC)": (1.0, 10000000),
    "White Blood Cells (WBC)": (0.5, 500000),
    "Platelets": (1, 2000000),
    "Packed Cell Volume (PCV)": (10, 75),
    "Mean Corpuscular Volume (MCV)": (55, 140),
    "Mean Corpuscular Hemoglobin (MCH)": (15, 45),
    "Mean Corpuscular Hemoglobin Concentration (MCHC)": (22, 42),
    "Red Cell Distribution Width (RDW)": (8, 30),
    "Mean Platelet Volume (MPV)": (4, 20),
    "Platelet Distribution Width (PDW)": (5, 30),
    "ESR": (0, 200),
    "Lymphocytes": (0.1, 100000),
    "Neutrophils": (0.1, 100000),
    "Monocytes": (0.0, 100000),
    "Eosinophils": (0.0, 100000),
    "Basophils": (0.0, 100000),
    "Glucose": (1, 800),
    "HbA1c": (3, 20),
    "Total Cholesterol": (50, 500),
    "Triglycerides": (20, 2000),
    "HDL Cholesterol": (5, 150),
    "LDL Cholesterol": (10, 400),
    "Creatinine": (0.1, 20),
    "Blood Urea Nitrogen (BUN)": (1, 300),
    "Sodium (Na+)": (80, 200),
    "Potassium (K+)": (1, 10),
    "Calcium": (3, 15),
    "TSH": (0.01, 200),
    "ALT (SGPT)": (1, 2000),
    "AST (SGOT)": (1, 2000),
    "Bilirubin (Total)": (0.1, 30),
    "Alkaline Phosphatase": (10, 2000),
    "Total Protein": (2, 12),
    "Albumin": (1, 8),
    "Uric Acid": (1, 20),
    "Ferritin": (1, 5000),
    "Vitamin B12": (50, 3000),
    "Vitamin D": (1, 200),
    "Iron (Serum)": (10, 500),
    "TIBC": (100, 600),
    "Chloride (Cl-)": (60, 150),
    "Bicarbonate": (5, 50),
    "Amylase": (10, 2000),
    "Lipase": (5, 2000),
    "GGT": (1, 2000),
    "LDH": (50, 5000),
    "Creatine Kinase (CK)": (10, 100000),
    "Troponin I": (0.0, 100),
    "D-Dimer": (0.0, 50),
    "Fibrinogen": (50, 1500),
    "INR": (0.5, 10),
    "Prothrombin Time (PT)": (5, 120),
    "APTT": (10, 200),
    "Magnesium": (0.5, 5),
    "Phosphorus": (0.5, 10),
}


def _is_plausible_value(canonical_name: str, value_str: str) -> bool:
    numeric = _parse_numeric(value_str)
    if numeric is None:
        return False
    bounds = _VALUE_PLAUSIBLE.get(canonical_name)
    if not bounds:
        return numeric > 0
    low, high = bounds
    return low <= numeric <= high


def _candidate_junk(value: str) -> int:
    """Lower is better: count characters outside the numeric value (currency
    symbols, OCR noise) that leak into the value column."""
    return sum(1 for ch in value if ch not in "0123456789.,x^/uLdlmgk% -+µ")


def extract_biomarker_rows(text: str) -> list[BiomarkerRow]:
    rows: dict[str, BiomarkerRow] = {}
    seen_scores: dict[str, tuple[int, int]] = {}

    for raw_line in text.splitlines():
        if _is_admin_line(raw_line):
            continue
        line = _normalize_sci_unit(raw_line)

        colon_match = METRIC_VALUE_PATTERN.search(line)
        table_match = BIOMARKER_LINE_PATTERN.match(line)

        yield_name: str | None = None
        yield_value: str | None = None
        yield_reference: str | None = None

        # Prefer the table-row pattern (Name  value  (Ref: range)) because the
        # generic colon pattern also matches the ":" inside "(Ref: range)", which
        # swallows the trailing range and corrupts the detected name for compound/
        # long biomarker names (e.g. "Glucose (Fasting)  210  (Ref: 70-110)").
        if table_match:
            yield_name = normalize_biomarker_name(table_match.group(1))
            yield_value = _split_glued_value(table_match.group(2))
            yield_reference = _clean_reference(table_match.group(3))
        elif colon_match:
            yield_name = normalize_biomarker_name(colon_match.group(1))
            yield_value = _split_glued_value(colon_match.group(2))
            yield_reference = _clean_reference(colon_match.group(3))
            if not yield_reference or yield_reference == "See lab report":
                yield_reference = _clean_reference(line)
        else:
            # No clean table/colon parse. The raw line may still be a real
            # biomarker row whose value OCR corrupted beyond recovery (e.g.
            # "PLT AG¥505"). Detect the biomarker by its leading short code so
            # the test still surfaces as "couldn't read" instead of vanishing.
            yield_name = _detect_biomarker_by_shortcode(line)
            if yield_name is None:
                continue
            yield_value = None
            yield_reference = None

        name = yield_name
        if not name or len(name) < 2:
            continue
        if name.lower() in ADMIN_METRIC_NAMES:
            continue
        if not is_recognized_biomarker(name):
            continue

        key = name.lower()

        if yield_value is None or not re.search(r"\d", yield_value):
            # Biomarker identified but its numeric value is unreadable.
            candidate = BiomarkerRow(
                name=name,
                value="Could not read",
                reference=yield_reference or "See your lab report",
                status="unknown",
            )
            score = (0, 0)
        else:
            status = _compare_to_reference(yield_value, yield_reference)
            if not _is_plausible_value(name, yield_value):
                # Value clearly OCR-corrupt (e.g. digit glue: MCV 473, PCV 426%).
                # Never present a wrong lab value; mark it so the user can retype it.
                candidate = BiomarkerRow(
                    name=name,
                    value="Could not read",
                    reference=yield_reference or "See your lab report",
                    status="unknown",
                )
                score = (0, 0)
            else:
                candidate = BiomarkerRow(
                    name=name,
                    value=yield_value,
                    reference=yield_reference,
                    status=status,
                )
                score = (1, -_candidate_junk(yield_value))

        # Multi-pass OCR can surface several candidates for the same metric
        # (e.g. "MCV 473.5" garbage AND "MCV 73.5" correct). Keep the BEST —
        # a readable-plausible value beats "Could not read", and a cleaner
        # value column wins ties — so a bad first candidate cannot mask a
        # good later one.
        if key not in rows or score > seen_scores[key]:
            rows[key] = candidate
            seen_scores[key] = score

    result = list(rows.values())

    if len(result) < 2:
        for match in METRIC_VALUE_PATTERN.finditer(text):
            name = normalize_biomarker_name(match.group(1))
            if name.lower() in ADMIN_METRIC_NAMES or name.lower() in rows:
                continue
            if not is_recognized_biomarker(name):
                continue
            value = match.group(2).strip()
            if not re.search(r"\d", value):
                continue

            line_end = text.find("\n", match.end())
            line_slice = text[match.start() : line_end if line_end != -1 else match.end() + 120]
            reference = _clean_reference(line_slice)
            if reference == "See lab report":
                reference = _clean_reference(match.group(0))

            rows[name.lower()] = BiomarkerRow(
                name=name,
                value=value,
                reference=reference,
                status=_compare_to_reference(value, reference),
            )

    return list(rows.values())


def filter_clinical_text(text: str) -> str:
    """Return biomarker-focused text with administrative metadata removed.

    Normalizes rows into a colon-separated format that downstream parsers
    (U.I.P. framework) can extract metric/value/reference from.
    """
    rows = extract_biomarker_rows(text)
    if not rows:
        filtered_lines = [line for line in text.splitlines() if not _is_admin_line(line)]
        return "\n".join(filtered_lines).strip()

    lines = []
    for row in rows:
        lines.append(f"{row.name}: {row.value} (Ref: {row.reference})")

    return "\n".join(lines).strip()
