"""Generate offline/engine-data.json from the backend knowledge base.

This script serializes the pure-data portions of the MediBridge backend
(alias tables, clinical hints, possible conditions, regexes, per-language
templates) into a single JSON file the offline browser engine consumes.
Run:  python backend/gen_offline_data.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from pipeline import biomarker_extractor as bex  # noqa: E402
from pipeline import safety_filter as safe  # noqa: E402
from pipeline import uip_framework as uip  # noqa: E402


def _rx(pattern: re.Pattern) -> dict:
    return {"pattern": pattern.pattern, "flags": pattern.flags}


# --- Per-language template strings (mirrors uip_framework._mock_analysis_from_text) ---
TERM_EXPL = {
    "hi": "यह एक लैब परीक्षण है जो आपके रक्त या स्वास्थ्य की जांच करता है।",
    "ta": "இது உங்கள் இரத்தம் அல்லது உடல்நலத்தை பரிசோதிக்கும் ஒரு ஆய்வக பரிசோதனை.",
    "en": "This is a lab test that checks part of your blood or body chemistry.",
}
TERM_ANALOGY = {
    "hi": "यह शरीर की जांच रिपोर्ट की तरह है — संख्याएँ बताती हैं कि सब ठीक है या नहीं।",
    "ta": "இது உடல் பரிசோதனை அறிக்கை போன்றது — எண்கள் எல்லாம் சரியா என்று காட்டுகிறது.",
    "en": "Think of it like a report card for one part of your health.",
}
NUM_EXPL = {
    "hi": "यह आपकी रिपोर्ट से पढ़ा गया मान है। आपका डॉक्टर इसे आपके लिए सही संदर्भ में समझाएगा।",
    "ta": "இது உங்கள் அறிக்கையிலிருந்து படிக்கப்பட்ட மதிப்பு. உங்கள் மருத்துவர் இதை சரியான சூழலில் விளக்குவார்.",
    "en": "This value comes from your uploaded report. Your doctor can explain what it means for you personally.",
}
Q_TEMPLATES = {
    "hi": [
        "मेरे {metric} का परिणाम ({value}) मेरे स्वास्थ्य के लिए क्या मायने रखता है?",
        "क्या इनमें से कोई परिणाम सामान्य सीमा से बाहर है, और अगले कदम क्या होने चाहिए?",
        "क्या इन रिपोर्ट के आधार पर कोई अतिरिक्त जांच या फॉलो-अप की जरूरत है?",
    ],
    "ta": [
        "என் {metric} முடிவு ({value}) என் உடல்நலத்திற்கு என்ன அர்த்தம்?",
        "இந்த முடிவுகளில் ஏதேனும் சாதாரண வரம்பை விட வேறுபடுகிறதா, அடுத்து என்ன செய்ய வேண்டும்?",
        "இந்த அறிக்கையின் அடிப்படையில் கூடுதல் பரிசோதனை அல்லது follow-up தேவையா?",
    ],
    "en": [
        "What does my {metric} result ({value}) mean for my overall health?",
        "Are any of these results outside the usual range, and what are the next steps?",
        "Based on this report, do I need any follow-up tests or a repeat lab draw?",
    ],
}

data = {
    "canonical_biomarkers": {
        name: list(aliases) for name, aliases in bex.CANONICAL_BIOMARKERS.items()
    },
    "shortcode_to_canonical": bex._SHORTCODE_TO_CANONICAL,
    "value_plausible": {k: list(v) for k, v in bex._VALUE_PLAUSIBLE.items()},
    "admin_metric_names": sorted(bex.ADMIN_METRIC_NAMES),
    "admin_line_patterns": [_rx(p) for p in bex.ADMIN_LINE_PATTERNS],
    "extractor_patterns": {
        "biomarker_line": _rx(bex.BIOMARKER_LINE_PATTERN),
        "metric_value": _rx(bex.METRIC_VALUE_PATTERN),
        "inline_range": _rx(bex.INLINE_RANGE_PATTERN),
        "generic_range": _rx(bex.GENERIC_RANGE_PATTERN),
        "single_value": _rx(bex.SINGLE_VALUE_PATTERN),
        "sci_unit": _rx(bex._SCI_UNIT),
        "sci_unit_degenerate": _rx(bex._SCI_UNIT_DEGENERATE),
    },
    "safety": {
        "imaging_keywords": list(safe.IMAGING_KEYWORDS),
        "imaging_extensions": list(safe.IMAGING_EXTENSIONS),
        "lab_report_keywords": list(safe.LAB_REPORT_KEYWORDS),
        "lab_value": _rx(safe.LAB_VALUE_PATTERN),
        "column_value": _rx(safe.COLUMN_VALUE_PATTERN),
        "reference_range": _rx(safe.REFERENCE_RANGE_PATTERN),
        "email": _rx(safe.EMAIL_PATTERN),
        "phone": _rx(safe.PHONE_PATTERN),
        "ssn": _rx(safe.SSN_PATTERN),
        "dob": _rx(safe.DATE_OF_BIRTH_PATTERN),
        "patient_name": _rx(safe.PATIENT_NAME_PATTERN),
        "mrn": _rx(safe.MRN_PATTERN),
        "address": _rx(safe.ADDRESS_PATTERN),
    },
    "uip": {
        "clinical_hints": uip.CLINICAL_HINTS,
        "condition_terms": uip.CONDITION_TERMS,
        "possible_conditions": uip.POSSIBLE_CONDITIONS,
        "overall_hints": uip._OVERALL_HINTS,
        "metric_pattern": _rx(uip.METRIC_PATTERN),
        "inline_range_pattern": _rx(uip.INLINE_RANGE_PATTERN),
        "emergency_keywords": list(uip.EMERGENCY_KEYWORDS),
        "term_expl": TERM_EXPL,
        "term_analogy": TERM_ANALOGY,
        "num_expl": NUM_EXPL,
        "q_templates": Q_TEMPLATES,
    },
}

out = BACKEND.parent / "offline" / "engine-data.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size / 1024:.1f} KB)")