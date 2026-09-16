"""Extract medicine names from a scanned prescription and explain them in plain language.

Safety design:
- We identify the medicine name and give a plain-language description of what
  the medicine class is commonly used for. We never judge the dose, never say
  whether the medicine is "correct" for the patient, and never issue a verdict.
- Unknown or unreadable medicine names are surfaced as-is with a "confirm with
  your pharmacist" prompt rather than being silently dropped.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Final, Literal

logger = logging.getLogger(__name__)

Lang = Literal["en", "hi", "ta"]

# Common medicine names (generic + common brand variants) mapped to a
# plain-language "what this is commonly used for" description in en/hi/ta.
MEDICINE_KB: Final[dict[str, dict[str, str]]] = {
    "paracetamol": {
        "aliases": "paracetamol, acetaminophen, crocin, dolo 650, dolo, calpol, tylenol, panadol",
        "en": "Commonly used to reduce fever and relieve mild pain.",
        "hi": "आमतौर पर बुखार कम करने और हल्के दर्द से राहत के लिए उपयोग किया जाता है।",
        "ta": "பொதுவாக காய்ச்சலை குறைக்கவும், லேசான வலியை போக்கவும் பயன்படுகிறது.",
    },
    "ibuprofen": {
        "aliases": "ibuprofen, advil, brufen, ibugesic, motrin, nurofen",
        "en": "Commonly used to relieve pain, fever, and inflammation.",
        "hi": "आमतौर पर दर्द, बुखार और सूजन से राहत के लिए उपयोग किया जाता है।",
        "ta": "பொதுவாக வலி, காய்ச்சல் மற்றும் வீக்கத்தை குறைக்க பயன்படுகிறது.",
    },
    "aspirin": {
        "aliases": "aspirin, ecospirin, ecosprin, disprin, acetylsalicylic acid",
        "en": "Sometimes used in low doses for heart protection; also relieves pain and fever.",
        "hi": "कभी-कभी कम खुराक में हृदय सुरक्षा के लिए; दर्द और बुखार से भी राहत देता है।",
        "ta": "ஒரு சில நேரங்களில் இதய பாதுகாப்பிற்கு குறைந்த அளவில்; வலி மற்றும் காய்ச்சலையும் குறைக்கும்.",
    },
    "amoxicillin": {
        "aliases": "amoxicillin, amoxil, mox, moxikind, novamox",
        "en": "An antibiotic commonly used to treat certain bacterial infections.",
        "hi": "एंटीबायोटिक जो आमतौर पर कुछ जीवाणु संक्रमणों के इलाज में उपयोग होता है।",
        "ta": "சில பாக்டீரியல் தொற்றுகளுக்கு சிகிச்சையளிக்க பொதுவாக பயன்படும் நுண்ணுயிர் எதிர்ப்பி.",
    },
    "azithromycin": {
        "aliases": "azithromycin, azee, zithromax, azithral",
        "en": "An antibiotic commonly used to treat certain bacterial infections.",
        "hi": "एंटीबायोटिक जो आमतौर पर कुछ जीवाणु संक्रमणों के इलाज में उपयोग होता है।",
        "ta": "சில பாக்டீரியல் தொற்றுகளுக்கு சிகிச்சையளிக்க பொதுவாக பயன்படும் நுண்ணுயிர் எதிர்ப்பி.",
    },
    "metformin": {
        "aliases": "metformin, glycomet, glyciphage, glucophage",
        "en": "Commonly used in managing diabetes to help control blood sugar.",
        "hi": "आमतौर पर मधुमेह प्रबंधन में रक्त शर्करा नियंत्रित करने के लिए उपयोग होता है।",
        "ta": "நீரிழிவு நிர்வாகத்தில் இரத்த சர்க்கரையை கட்டுப்படுத்த பொதுவாக பயன்படுகிறது.",
    },
    "glimepiride": {
        "aliases": "glimepiride, amaryl, glimestar, glimy",
        "en": "Commonly used in managing diabetes to help control blood sugar.",
        "hi": "आमतौर पर मधुमेह प्रबंधन में रक्त शर्करा नियंत्रित करने के लिए उपयोग होता है।",
        "ta": "நீரிழிவு நிர்வாகத்தில் இரத்த சர்க்கரையை கட்டுப்படுத்த பொதுவாக பயன்படுகிறது.",
    },
    "metoclopramide": {
        "aliases": "metoclopramide, perinorm, emetil, reglan",
        "en": "Commonly used to relieve nausea, vomiting, and acid reflux symptoms.",
        "hi": "आमतौर पर मतली, उल्टी और एसिड रिफ्लक्स के लक्षणों से राहत के लिए उपयोग होता है।",
        "ta": "குமட்டல், வாந்தி மற்றும் அமில எதிர்வீச்சு அறிகுறிகளை குறைக்க பொதுவாக பயன்படுகிறது.",
    },
    "omeprazole": {
        "aliases": "omeprazole, omez, osec, prilosec",
        "en": "Commonly used to reduce stomach acid and treat acidity or ulcers.",
        "hi": "आमतौर पर पेट का एसिड कम करने और एसिडिटी या अल्सर के इलाज में उपयोग होता है।",
        "ta": "வயிற்று அமிலத்தை குறைக்கவும், அமிலத்தன்மை அல்லது புண்களுக்கு பொதுவாக பயன்படுகிறது.",
    },
    "pantoprazole": {
        "aliases": "pantoprazole, pantocid, pan 40, pan, protium",
        "en": "Commonly used to reduce stomach acid and treat acidity or ulcers.",
        "hi": "आमतौर पर पेट का एसिड कम करने और एसिडिटी या अल्सर के इलाज में उपयोग होता है।",
        "ta": "வயிற்று அமிலத்தை குறைக்கவும், அமிலத்தன்மை அல்லது புண்களுக்கு பொதுவாக பயன்படுகிறது.",
    },
    "levothyroxine": {
        "aliases": "levothyroxine, thyrox, eltroxin, thyronorm, synthroid",
        "en": "Thyroid hormone replacement given for low thyroid activity.",
        "hi": "थायराइड की कम गतिविधि के लिए दी जाने वाली थायराइड हार्मोन प्रतिस्थापन दवा।",
        "ta": "குறைந்த தைராய்டு செயல்பாட்டிற்காக வழங்கப்படும் தைராய்டு ஹார்மோன் மாற்று மருந்து.",
    },
    "amlodipine": {
        "aliases": "amlodipine, amlodac, amlopres, norvasc",
        "en": "Commonly used to lower high blood pressure.",
        "hi": "आमतौर पर उच्च रक्तचाप कम करने के लिए उपयोग होता है।",
        "ta": "அதிக இரத்த அழுத்தத்தை குறைக்க பொதுவாக பயன்படுகிறது.",
    },
    "telmisartan": {
        "aliases": "telmisartan, telma, telmisar, micardis",
        "en": "Commonly used to lower high blood pressure.",
        "hi": "आमतौर पर उच्च रक्तचाप कम करने के लिए उपयोग होता है।",
        "ta": "அதிக இரத்த அழுத்தத்தை குறைக்க பொதுவாக பயன்படுகிறது.",
    },
    "atorvastatin": {
        "aliases": "atorvastatin, atorva, atorlip, lipitor",
        "en": "Commonly used to lower cholesterol in the blood.",
        "hi": "आमतौर पर रक्त में कोलेस्ट्रॉल कम करने के लिए उपयोग होता है।",
        "ta": "இரத்தத்தில் கொழுப்பை குறைக்க பொதுவாக பயன்படுகிறது.",
    },
    "rosuvastatin": {
        "aliases": "rosuvastatin, rosuvas, crestor",
        "en": "Commonly used to lower cholesterol in the blood.",
        "hi": "आमतौर पर रक्त में कोलेस्ट्रॉल कम करने के लिए उपयोग होता है।",
        "ta": "இரத்தத்தில் கொழுப்பை குறைக்க பொதுவாக பயன்படுகிறது.",
    },
    "prednisolone": {
        "aliases": "prednisolone, omnacortil, wysolone, prednisone",
        "en": "A steroid commonly used to reduce inflammation.",
        "hi": "एक स्टेरॉयड जो आमतौर पर सूजन कम करने के लिए उपयोग होता है।",
        "ta": "வீக்கத்தை குறைக்க பொதுவாக பயன்படும் ஸ்டீராய்டு.",
    },
    "salbutamol": {
        "aliases": "salbutamol, albuterol, asthalin, ventolin",
        "en": "Commonly used to relieve asthma or breathing difficulty.",
        "hi": "आमतौर पर अस्थमा या सांस की तकलीफ से राहत के लिए उपयोग होता है।",
        "ta": "ஆஸ்துமா அல்லது மூச்சுத் திணறலை போக்க பொதுவாக பயன்படுகிறது.",
    },
    "montelukast": {
        "aliases": "montelukast, montair, montrina, singular",
        "en": "Commonly used to help control asthma and allergic runny nose.",
        "hi": "आमतौर पर अस्थमा और एलर्जी से होने वाली नाक बहने को नियंत्रित करने में उपयोग होता है।",
        "ta": "ஆஸ்துமா மற்றும் ஒவ்வாமையால் ஏற்படும் மூக்கு ஒழுகுதலை கட்டுப்படுத்த பொதுவாக பயன்படுகிறது.",
    },
    "cetirizine": {
        "aliases": "cetirizine, cetzine, zyrtec, alerid",
        "en": "An antihistamine commonly used to relieve allergy symptoms.",
        "hi": "एक एंटीहिस्टामाइन जो आमतौर पर एलर्जी के लक्षणों से राहत के लिए उपयोग होता है।",
        "ta": "ஒவ்வாமை அறிகுறிகளை போக்க பொதுவாக பயன்படும் ஆண்டிஹிஸ்டமைன்.",
    },
    "levocetirizine": {
        "aliases": "levocetirizine, levocet, lc cet, xyzal",
        "en": "An antihistamine commonly used to relieve allergy symptoms.",
        "hi": "एक एंटीहिस्टामाइन जो आमतौर पर एलर्जी के लक्षणों से राहत के लिए उपयोग होता है।",
        "ta": "ஒவ்வாமை அறிகுறிகளை போக்க பொதுவாக பயன்படும் ஆண்டிஹிஸ்டமைன்.",
    },
    "vitamin d": {
        "aliases": "vitamin d, vitamin d3, cholecalciferol, d3, calciferol, uprise d3",
        "en": "A vitamin supplement commonly used when vitamin D levels are low.",
        "hi": "एक विटामिन सप्लीमेंट जो विटामिन D कम होने पर आमतौर पर उपयोग होता है।",
        "ta": "வைட்டமின் D அளவு குறைவாக இருக்கும்போது பொதுவாக பயன்படும் வைட்டமின் சப்ளிமெண்ட்.",
    },
    "iron": {
        "aliases": "iron, ferrous sulphate, ferrous sulfate, fesofor, auric, iron sucrose, ferinject",
        "en": "An iron supplement commonly used when iron levels or hemoglobin are low.",
        "hi": "एक आयरन सप्लीमेंट जो आयरन या हीमोग्लोबिन कम होने पर आमतौर पर उपयोग होता है।",
        "ta": "இரும்பு அல்லது ஹீமோகுளோபின் குறைவாக இருக்கும்போது பொதுவாக பயன்படும் இரும்பு சப்ளிமெண்ட்.",
    },
    "calcium": {
        "aliases": "calcium, shelcal, calcirol, calcium carbonate",
        "en": "A calcium supplement commonly used to support bone health.",
        "hi": "एक कैल्शियम सप्लीमेंट जो आमतौर पर हड्डियों के स्वास्थ्य के लिए उपयोग होता है।",
        "ta": "எலும்பு ஆரோக்கியத்திற்கு பொதுவாக பயன்படும் கால்சியம் சப்ளிமெண்ட்.",
    },
    "cough syrup": {
        "aliases": "cough syrup, benadryl, corex, ascoril, grilinctus, dextromethorphan",
        "en": "A cough syrup commonly used to relieve cough symptoms.",
        "hi": "कफ सिरप जो आमतौर पर खांसी के लक्षणों से राहत के लिए उपयोग होता है।",
        "ta": "இருமல் அறிகுறிகளை போக்க பொதுவாக பயன்படும் இருமல் சிரப்.",
    },
}


def _clean_name(raw: str) -> str:
    return re.sub(r"\s+", " ", raw).strip(" :-=*/")


def _canonical_key(raw_name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", raw_name.lower())


def _build_aliases() -> dict[str, str]:
    """Map every alias (lowercased) to its medicine's canonical key."""
    mapping: dict[str, str] = {}
    for key, entry in MEDICINE_KB.items():
        for alias in entry["aliases"].split(","):
            mapping[alias.strip().lower()] = key
    return mapping


_ALIAS_LOOKUP: Final[dict[str, str]] = _build_aliases()


@dataclass
class MedicineResult:
    name: str  # canonical or as-written medicine name
    purpose: str  # plain-language description in the requested language
    matched: bool  # True when identified from the knowledge base
    key: str = ""  # knowledge-base key when matched


def _extract_candidate_names(text: str) -> list[str]:
    """Pull likely medicine line beginnings from a prescription OCR blob."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidates: list[str] = []

    skip_prefixes = (
        "patient",
        "dr.",
        "doctor",
        "rx",
        "prescription",
        "date",
        "dear",
        "reg",
        "ref",
        "pharmacy",
        "address",
        "phone",
        "hospital",
        "clinic",
        "medical",
        "name",
        "age",
        "sex",
        "gender",
        "dob",
        "weight",
        "height",
        "allergy",
        "allergies",
        "symptoms",
        "complaints",
        "diagnosis",
        "advice",
        "instructions",
        "signature",
        "before",
        "after",
        "morning",
        "noon",
        "evening",
        "night",
        "take",
        "daily",
        "bd",
        "od",
        "tds",
        "qid",
        "sos",
        "stat",
        "empty",
        "with",
    )

    dosage_forms = (
        "tab",
        "cap",
        "syp",
        "inj",
        "ointment",
        "cream",
        "drop",
        "drops",
        "sachet",
        "gel",
    )

    for line in lines:
        # Strip a leading list number like "1.", "2)" or "1."
        cleaned = _clean_name(line)
        cleaned = re.sub(r"^\s*\d{1,3}\s*[.)]\s*", "", cleaned)
        if len(cleaned) < 3:
            continue

        # The prescription header marker "Rx:" prefixes the first medicine line
        # ("Rx: Tab Dolo 650 1-0-1..."). Strip it instead of dropping the line.
        rx_match = re.match(r"^\s*rx\s*[:.\s/]*\s*", cleaned, re.IGNORECASE)
        if rx_match:
            cleaned = cleaned[rx_match.end():].strip()
            if len(cleaned) < 3:
                continue

        lowered = cleaned.lower()
        if lowered.startswith(skip_prefixes):
            continue

        # Skip prescription of an image that fails OCR with only digits.
        if re.fullmatch(r"[\d\s.\-/]+", cleaned):
            continue

        # Grab the medicine name: optional form prefix (Tab/Cap/Syp/Inj)
        # followed by brand/generic words and optional strength digits.
        # Case-insensitive and tolerant of "Tab."/"Cap." spoken-style
        # abbreviations, not just "Tab ".
        match = re.match(
            r"(?i)^(?:(tab|cap|syp|inj|ointment|cream|drop(?:s)?|sachet|gel)\s*\.?\s*)?"
            r"([A-Za-z][A-Za-z\-]{1,24}(?:\s+[A-Za-z][A-Za-z\-]{1,24}){0,3}(?:\s+\d{1,4})?)",
            cleaned,
        )
        if not match:
            continue

        form = (match.group(1) or "").lower()
        name = match.group(2).strip()
        if len(name) < 3:
            continue

        # Keep the candidate only when it plausibly is a medicine:
        # 1) it maps to a known medicine, OR
        # 2) it has a dosage-form prefix (Tab/Cap/Syp/Inj...), OR
        # 3) it carries a strength number (Dolo 650, Amoxil 500mg, Pan 40).
        if _match_medicine(name).matched or form or re.search(r"\d", name):
            candidates.append(name)

    return candidates


def _match_medicine(raw_name: str) -> MedicineResult:
    cleaned = _clean_name(raw_name)
    if not cleaned:
        return MedicineResult(name=raw_name, purpose="", matched=False)

    lowered = cleaned.lower()
    # Strip dosage-form prefixes ("Tab", "Cap", "Syp", "Inj", etc.) so the
    # name matches brand aliases like "Dolo 650".
    lowered = re.sub(
        r"^(?:tab|cap|syp|inj|ointment|cream|drop|drops)[.,\s]*",
        "",
        lowered,
    )

    # Exact alias match first (handles brand names like "Dolo 650").
    for alias, key in _ALIAS_LOOKUP.items():
        if lowered == alias or lowered.startswith(alias + " "):
            return MedicineResult(name=cleaned, purpose="", matched=True, key=key)

    # Fuzzy fallback for OCR typos against medicine keys.
    best_key = ""
    best_score = 0.72
    for key in MEDICINE_KB:
        score = SequenceMatcher(None, key, lowered).ratio()
        if score > best_score:
            best_score = score
            best_key = key

    if best_key:
        return MedicineResult(name=best_key, purpose="", matched=True, key=best_key)

    return MedicineResult(name=cleaned, purpose="", matched=False)


def analyze_prescription(text: str, language: Lang) -> dict:
    """Return structured, plain-language info about medicines in a prescription."""
    lang = language if language in ("en", "hi", "ta") else "en"

    raw_names = _extract_candidate_names(text)
    seen: set[str] = set()
    medicines: list[dict] = []

    for raw in raw_names:
        result = _match_medicine(raw)
        key = result.key or _canonical_key(result.name)
        if key in seen:
            continue
        seen.add(key)

        entry = MEDICINE_KB.get(result.key, {}) if result.key else {}
        if result.matched and entry:
            display_name = result.key.title()
            purpose = entry.get(lang, entry.get("en", ""))
        elif result.matched:
            display_name = result.name
            purpose = (
                "Could not interpret this name. Read it exactly as written and confirm with your pharmacist."
                if lang == "en"
                else "इस नाम को समझा नहीं जा सका। इसे जैसे लिखा है वैसे ही पढ़ें और फार्मासिस्ट से पुष्टि करें।"
                if lang == "hi"
                else "இந்த பெயரை புரிந்துகொள்ள முடியவில்லை. அப்படியே படித்து மருந்து விற்பனையாளரிடம் உறுதிப்படுத்தவும்."
            )
        else:
            display_name = result.name
            purpose = (
                "Not in our common-medicine list — write it down and confirm exactly how to take it with your pharmacist or doctor."
                if lang == "en"
                else "यह हमारी सामान्य दवाइयों की सूची में नहीं है — इसे लिख लें और फार्मासिस्ट या डॉक्टर से इसे लेने का सही तरीका पूछें।"
                if lang == "ta"
                else "இது எங்கள் பொதுவான மருந்து பட்டியலில் இல்லை — இதை எழுதி வைத்து, சரியாக எப்படி உட்கொள்வது என மருந்தாளுனர் அல்லது மருத்துவரிடம் கேளுங்கள்."
            )

        medicines.append(
            {
                "name": display_name,
                "purpose": purpose,
                "matched": result.matched,
            }
        )

    questions = _pharmacist_questions(text, medicines, lang)

    return {"medicines": medicines[:12], "pharmacist_questions": questions}


def _pharmacist_questions(text: str, medicines: list[dict], lang: str) -> list[str]:
    med_names = ", ".join(item["name"] for item in medicines[:3]) or "the medicines"

    if lang == "hi":
        base = [
            f"क्या इन दवाइयों ({med_names}) को एक साथ लेना सुरक्षित है और क्या कोई परस्पर प्रभाव हो सकता है?",
            "इन दवाइयों की खुराक और लेने का सही समय क्या है — भोजन से पहले या बाद में?",
            "क्या इन दवाइयों का कोई सामान्य दुष्प्रभाव है और क्या इन्हें किसी भोजन या अन्य दवा के साथ नहीं लेना चाहिए?",
        ]
    elif lang == "ta":
        base = [
            f"இந்த மருந்துகளை ({med_names}) ஒன்றாக எடுத்துக்கொள்வது பாதுகாப்பானதா, மற்றும் ஏதேனும் தொடர்பு உண்டா?",
            "இந்த மருந்துகளின் அளவு மற்றும் சரியான நேரம் என்ன — உணவுக்கு முன் அல்லது பின்?",
            "இந்த மருந்துகளுக்கு பொதுவான பக்க விளைவுகள் உண்டா, வேறு எதை தவிர்க்க வேண்டும்?",
        ]
    else:
        base = [
            f"Is it safe to take these medicines ({med_names}) together, and can they interact?",
            "What are the right doses and timing for these medicines — before or after food?",
            "Are there common side effects, and is there anything to avoid with these medicines?",
        ]

    return base