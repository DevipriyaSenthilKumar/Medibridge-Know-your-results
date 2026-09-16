from __future__ import annotations

import json
import logging
import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from config import get_settings
from pipeline.biomarker_extractor import is_recognized_biomarker
from pipeline.safety_filter import SafetyFilterError

logger = logging.getLogger(__name__)

UIP_SYSTEM_PROMPT = """You are a highly precise, safety-guarded Medical Document Simplification Engine. Your core objective is to improve patient health literacy while strictly avoiding definitive diagnoses or prescribing treatments.

Apply the following CRITICAL rules to filter the input data before processing:

### 1. DATA FILTRATION RULES (ANTI-DISTRACTION GUARDRAILS)
- ABSOLUTE PROHIBITION: You are strictly forbidden from simplifying, explaining, or generating questions for administrative metadata, logistics, or lab headers.
- Do NOT process items such as: Patient Name, Age, Sex, UHID, Patient ID, Ref. By (Doctor Name), Sample Collected At, Registered On, Collected On, Reported On, TAT (Turnaround Time), or Instruments used.
- TARGET FOCUS: You must strictly isolate and process ONLY row-by-row clinical biomarkers, physiological elements, and lab parameters found under columns labeled 'Investigation', 'Result', or 'Reference Value' (e.g., Hemoglobin, WBC, Platelets, Lymphocytes, TSH, Glucose).

### 2. THE THREE-STAGE U.I.P. EXTRACTION SPECIFICATION
Process the valid clinical biomarkers exactly through these three structural steps:
1. UNDERSTAND: Rewrite technical clinical terms at a simple 6th-grade reading level using clear, everyday analogies. Do not repeat the same generic explanation for different metrics.
2. INTERPRET: Compare the patient's 'Result' value against the 'Reference Value'. Provide a calm, general context explaining whether the metric is within the typical range, high, or low, without issuing a definitive diagnostic label. For values outside the range, add 'possible_causes' — a calm, possibility-based hint of what the deviation MAY indicate (e.g., 'may be linked to anemia, blood loss, or iron deficiency') using words like 'may', 'could', 'a possibility'. NEVER give a definite diagnosis. Add 'doctor_guidance' — a safe, practical next step that does NOT prescribe medicine (e.g., 'Ask your doctor whether iron studies or a repeat test would help; do not start any medicine on your own.').
3. PREPARE: Generate a JSON list containing EXACTLY THREE highly relevant, smart questions the patient should physically take to ask their doctor. If there is a massive clinical deviation (such as a critically low platelet count or dangerously high glucose), the questions MUST actively prompt the patient to discuss that specific anomaly with urgency.

### 4. PLAIN-LANGUAGE REPORT SUMMARY
After the U.I.P. steps, write a 'report_summary' — a short, calm, 6th-grade level summary of the whole report combining what the key numbers suggest (e.g., most values are in range, or a few are lower/higher than typical). Do NOT diagnose or prescribe. Then generate 'next_steps', a list of 2-4 safe, practical actions the patient can take now (e.g., keep the report with them, do not change any medicine on their own, show this summary to the doctor, schedule/keep a follow-up appointment). Never recommend buying medicines, supplements, or home remedies.

### 5. OUTPUT SCHEMA
You must return your response matching this strict JSON Pydantic schema structure:
{
  "emergency_trigger": bool,
  "report_summary": "Short 6th-grade summary of the whole report",
  "simplified_terms": [{"term": "Isolated Clinical Biomarker Name", "explanation": "Simple 6th-grade text", "analogy": "Contextual unique analogy"}],
  "numerical_context": [{"metric": "Biomarker Name", "value": "User Value", "normal_range": "Expected Range", "status": "high | low | within_range | unknown", "calm_explanation": "Contextual status text", "possible_causes": "Possibility-based May-be text for out-of-range values", "possible_conditions": ["Short possibility-based condition names (may relate to X/Y/Z), empty for in-range or unknown", "e.g. dehydration, infection"], "doctor_guidance": "Safe non-prescription next step"}],
  "doctor_questions": ["Specific smart question 1 based on the anomalies found", "Specific smart question 2 based on the anomalies found", "Specific smart question 3 based on the anomalies found"],
  "next_steps": ["Safe practical action 1", "Safe practical action 2", "Safe practical action 3"]
}"""

LANGUAGE_INSTRUCTIONS: dict[str, str] = {
    "en": "Return all string values in English.",
    "hi": (
        "Translate ALL string values in the JSON output into Hindi (Devanagari script). "
        "Keep JSON keys in English. Do not translate keys."
    ),
    "ta": (
        "Translate ALL string values in the JSON output into Tamil (Tamil script). "
        "Keep JSON keys in English. Do not translate keys."
    ),
}


# Knowledge base: canonical biomarker key -> status -> per-language
# (possible_causes, doctor_guidance). Always possibility-based, never
# definitive, never implying self-treatment.
CLINICAL_HINTS: dict[str, dict[str, dict[str, tuple[str, str]]]] = {
    "hemoglobin (hb)": {
        "low": {
            "en": (
                "A low level may be linked to anemia, blood loss, or low iron in the body.",
                "Ask your doctor whether iron studies or a repeat test would help. Do not start iron or any medicine on your own.",
            ),
            "hi": (
                "कम स्तर खून की कमी (एनीमिया), रक्त हानि, या शरीर में आयरन की कमी से जुड़ा हो सकता है।",
                "डॉक्टर से पूछें कि क्या आयरन की जांच या दोबारा टेस्ट कराना उचित होगा। बिना सलाह के आयरन या कोई दवा न लें।",
            ),
            "ta": (
                "குறைந்த அளவு இரத்த சோகை (anemia), இரத்த இழப்பு, அல்லது உடலில் இரும்புச்சத்து குறைவுடன் தொடர்புடையதாக இருக்கலாம்.",
                "இரும்பு பரிசோதனை அல்லது மீண்டும் பரிசோதனை தேவையா என மருத்துவரிடம் கேளுங்கள். ஆலோசனை இல்லாமல் மருந்தை ஆரம்பிக்க வேண்டாம்.",
            ),
        },
        "high": {
            "en": (
                "A high level could be linked to dehydration, living at high altitude, or lung conditions.",
                "Ask your doctor whether a repeat test or a chest check-up would be useful. Do not start any medicine on your own.",
            ),
            "hi": (
                "अधिक स्तर निर्जलीकरण (पानी की कमी), ऊँचाई पर रहना, या फेफड़ों की स्थिति से जुड़ा हो सकता है।",
                "डॉक्टर से पूछें कि क्या दोबारा टेस्ट या छाती की जांच उपयोगी होगी। बिना सलाह के कोई दवा न लें।",
            ),
            "ta": (
                "அதிக அளவு நீரிழப்பு, அதிக உயரத்தில் வாழ்வது, அல்லது நுரையீரல் பிரச்சனைகளுடன் தொடர்புடையதாக இருக்கலாம்.",
                "மீண்டும் பரிசோதனை அல்லது மார்பு பரிசோதனை பயனுள்ளதா என மருத்துவரிடம் கேளுங்கள். மருந்தை நீங்களே ஆரம்பிக்க வேண்டாம்.",
            ),
        },
    },
    "packed cell volume (pcv)": {
        "low": {
            "en": (
                "A low value may be a sign of anemia, blood loss, or not enough iron.",
                "Ask your doctor whether you need iron studies or dietary advice. Do not start any medicine yourself.",
            ),
            "hi": (
                "कम मान खून की कमी, रक्त हानि, या आयरन की कमी का संकेत हो सकता है।",
                "डॉक्टर से पूछें कि क्या आयरन जांच या आहार सलाह की जरूरत है। बिना सलाह कोई दवा शुरू न करें।",
            ),
            "ta": (
                "குறைந்த மதிப்பு இரத்த சோகை, இரத்த இழப்பு, அல்லது இரும்புச்சத்து குறைபாட்டின் அறிகுறியாக இருக்கலாம்.",
                "இரும்பு பரிசோதனை அல்லது உணவு ஆலோசனை தேவையா என மருத்துவரிடம் கேளுங்கள். மருந்தை நீங்களே தொடங்க வேண்டாம்.",
            ),
        },
        "high": {
            "en": (
                "A high value could relate to dehydration or conditions that thicken the blood.",
                "Ask your doctor whether you need more fluids or a repeat blood test. Do not start any medicine on your own.",
            ),
            "hi": (
                "अधिक मान निर्जलीकरण या रक्त गाढ़ा करने वाली स्थितियों से जुड़ा हो सकता है।",
                "डॉक्टर से पूछें कि क्या अधिक तरल पदार्थ या दोबारा रक्त परीक्षण जरूरी है। बिना सलाह कोई दवा न लें।",
            ),
            "ta": (
                "அதிக மதிப்பு நீரிழப்பு அல்லது இரத்தத்தை தடிமனாக்கும் நிலைகளுடன் தொடர்புடையதாக இருக்கலாம்.",
                "கூடுதல் திரவங்கள் அல்லது மீண்டும் இரத்த பரிசோதனை தேவையா என மருத்துவரிடம் கேளுங்கள். மருந்தை நீங்களே ஆரம்பிக்க வேண்டாம்.",
            ),
        },
    },
    "red blood cells (rbc)": {
        "low": {
            "en": (
                "A low count may suggest anemia, blood loss, or a vitamin deficiency.",
                "Ask your doctor whether a blood count check or vitamin B12/iron test is needed. Do not buy supplements on your own.",
            ),
            "hi": (
                "कम संख्या एनीमिया, रक्त हानि, या विटामिन की कमी का संकेत दे सकती है।",
                "डॉक्टर से पूछें कि क्या रक्त गणना या विटामिन B12/आयरन जांच आवश्यक है। बिना सलाह सप्लीमेंट न खरीदें।",
            ),
            "ta": (
                "குறைந்த எண்ணிக்கை இரத்த சோகை, இரத்த இழப்பு அல்லது வைட்டமின் குறைபாட்டை சுட்டிக்காட்டலாம்.",
                "இரத்த எண்ணிக்கை அல்லது B12/இரும்பு பரிசோதனை தேவையா என மருத்துவரிடம் கேளுங்கள். சப்ளிமெண்ட் வாங்காமல் இருங்கள்.",
            ),
        },
        "high": {
            "en": (
                "A high count could relate to dehydration, smoking, or lung conditions.",
                "Ask your doctor whether a repeat test or lifestyle advice would help. Do not start any medicine yourself.",
            ),
            "hi": (
                "अधिक संख्या निर्जलीकरण, धूम्रपान, या फेफड़ों की स्थिति से जुड़ी हो सकती है।",
                "डॉक्टर से पूछें कि क्या दोबारा टेस्ट या जीवनशैली सलाह मददगार होगी। बिना सलाह कोई दवा न लें।",
            ),
            "ta": (
                "அதிக எண்ணிக்கை நீரிழப்பு, புகைபிடித்தல் அல்லது நுரையீரல் நிலைகளுடன் தொடர்புடையதாக இருக்கலாம்.",
                "மீண்டும் பரிசோதனை அல்லது வாழ்க்கை முறை ஆலோசனை உதவுமா என மருத்துவரிடம் கேளுங்கள். மருந்தை நீங்களே தொடங்க வேண்டாம்.",
            ),
        },
    },
    "mean corpuscular volume (mcv)": {
        "low": {
            "en": (
                "A low value may point toward an iron-related blood condition.",
                "Ask your doctor whether an iron study would help explain this number. Do not take iron pills without advice.",
            ),
            "hi": (
                "कम मान आयरन से जुड़ी रक्त स्थिति की ओर संकेत कर सकता है।",
                "डॉक्टर से पूछें कि क्या आयरन जांच इस संख्या को समझने में मदद करेगी। बिना सलाह आयरन की गोली न लें।",
            ),
            "ta": (
                "குறைந்த மதிப்பு இரும்பு தொடர்பான இரத்த நிலையை சுட்டிக்காட்டலாம்.",
                "இரும்பு பரிசோதனை இந்த எண்ணிக்கையை விளக்க உதவுமா என மருத்துவரிடம் கேளுங்கள். இரும்பு மாத்திரையை நீங்களே எடுக்க வேண்டாம்.",
            ),
        },
        "high": {
            "en": (
                "A high value may relate to vitamin B12 or folate deficiency.",
                "Ask your doctor whether a vitamin B12 or folate test would be useful. Do not start supplements on your own.",
            ),
            "hi": (
                "अधिक मान विटामिन B12 या फोलेट की कमी से जुड़ा हो सकता है।",
                "डॉक्टर से पूछें कि क्या विटामिन B12 या फोलेट जांच उपयोगी होगी। बिना सलाह सप्लीमेंट शुरू न करें।",
            ),
            "ta": (
                "அதிக மதிப்பு வைட்டமின் B12 அல்லது folate குறைபாட்டுடன் தொடர்புடையதாக இருக்கலாம்.",
                "B12 அல்லது folate பரிசோதனை பயனுள்ளதா என மருத்துவரிடம் கேளுங்கள். சப்ளிமெண்ட்களை நீங்களே தொடங்க வேண்டாம்.",
            ),
        },
    },
    "white blood cells (wbc)": {
        "low": {
            "en": (
                "A low count may be linked to a recent infection, medicines, or bone marrow changes.",
                "Ask your doctor whether a repeat count or further blood work is needed. Do not stop any medicine without advice.",
            ),
            "hi": (
                "कम संख्या हाल की संक्रमण, दवाइयों, या अस्थि मज्जा में बदलाव से जुड़ी हो सकती है।",
                "डॉक्टर से पूछें कि क्या दोबारा गणना या और रक्त जांच आवश्यक है। बिना सलाह कोई दवा बंद न करें।",
            ),
            "ta": (
                "குறைந்த எண்ணிக்கை சமீபத்திய தொற்று, மருந்துகள் அல்லது எலும்பு மஜ்ஜை மாற்றங்களுடன் தொடர்புடையதாக இருக்கலாம்.",
                "மீண்டும் எண்ணிக்கை அல்லது கூடுதல் இரத்த பரிசோதனை தேவையா என மருத்துவரிடம் கேளுங்கள். மருந்தை நிறுத்த வேண்டாம்.",
            ),
        },
        "high": {
            "en": (
                "A high count is commonly seen with an infection, inflammation, or stress.",
                "Ask your doctor whether the cause needs treatment or a repeat test. Do not take any medicine on your own.",
            ),
            "hi": (
                "अधिक संख्या आमतौर पर संक्रमण, सूजन, या तनाव में देखी जाती है।",
                "डॉक्टर से पूछें कि क्या कारण का इलाज करना या दोबारा टेस्ट कराना जरूरी है। बिना सलाह कोई दवा न लें।",
            ),
            "ta": (
                "அதிக எண்ணிக்கை பொதுவாக தொற்று, வீக்கம் அல்லது மன அழுத்தத்தில் காணப்படுகிறது.",
                "காரணத்திற்கு சிகிச்சை தேவையா அல்லது மீண்டும் பரிசோதனை வேண்டுமா என மருத்துவரிடம் கேளுங்கள். மருந்தை நீங்களே எடுக்க வேண்டாம்.",
            ),
        },
    },
    "platelets": {
        "low": {
            "en": (
                "A low count may be linked to infections, medicines, or bone marrow changes, and needs a doctor's attention.",
                "Ask for advice today — your doctor may want a repeat count or more tests. Do not take any medicine or painkiller on your own.",
            ),
            "hi": (
                "कम संख्या संक्रमण, दवाइयों, या अस्थि मज्जा में बदलाव से जुड़ी हो सकती है और डॉक्टर के ध्यान की जरूरत है।",
                "आज ही सलाह लें — डॉक्टर दोबारा गणना या और जांच चाह सकते हैं। बिना सलाह कोई दवा या दर्दनिवारक न लें।",
            ),
            "ta": (
                "குறைந்த எண்ணிக்கை தொற்று, மருந்துகள் அல்லது எலும்பு மஜ்ஜை மாற்றங்களுடன் தொடர்புடையதாக இருக்கலாம், மருத்துவர் கவனம் தேவை.",
                "இன்றே ஆலோசனை பெறுங்கள் — மீண்டும் எண்ணிக்கை அல்லது கூடுதல் பரிசோதனை தேவைப்படலாம். மருந்தை நீங்களே எடுக்க வேண்டாம்.",
            ),
        },
        "high": {
            "en": (
                "A high count could relate to inflammation, infection, or reacting to blood loss.",
                "Ask your doctor whether treatment or a repeat test is needed. Do not take aspirin or any medicine on your own.",
            ),
            "hi": (
                "अधिक संख्या सूजन, संक्रमण, या रक्त हानि की प्रतिक्रिया से जुड़ी हो सकती है।",
                "डॉक्टर से पूछें कि क्या इलाज या दोबारा टेस्ट जरूरी है। बिना सलाह एस्पिरिन या कोई दवा न लें।",
            ),
            "ta": (
                "அதிக எண்ணிக்கை வீக்கம், தொற்று அல்லது இரத்த இழப்பிற்கு எதிர்வினையுடன் தொடர்புடையதாக இருக்கலாம்.",
                "சிகிச்சை அல்லது மீண்டும் பரிசோதனை தேவையா என மருத்துவரிடம் கேளுங்கள். ஆஸ்பிரின் அல்லது மருந்தை நீங்களே எடுக்க வேண்டாம்.",
            ),
        },
    },
    "glucose": {
        "low": {
            "en": (
                "A low value may be linked to long gaps without food or certain medicines.",
                "Ask your doctor whether you need a repeat test or diet guidance. Do not change diabetic medicine on your own.",
            ),
            "hi": (
                "कम मान लंबे समय खाना न खाना या कुछ दवाइयों से जुड़ा हो सकता है।",
                "डॉक्टर से पूछें कि क्या दोबारा टेस्ट या आहार सलाह जरूरी है। बिना सलाह मधुमेह की दवा न बदलें।",
            ),
            "ta": (
                "குறைந்த மதிப்பு நீண்ட நேரம் உண்ணாமல் இருப்பது அல்லது சில மருந்துகளுடன் தொடர்புடையதாக இருக்கலாம்.",
                "மீண்டும் பரிசோதனை அல்லது உணவு ஆலோசனை தேவையா என மருத்துவரிடம் கேளுங்கள். மருந்தை நீங்களே மாற்ற வேண்டாம்.",
            ),
        },
        "high": {
            "en": (
                "A high value may be linked to diabetes, recent sweet foods, or stress — worth a repeat test to be sure.",
                "Ask your doctor about a repeat glucose or HbA1c test, and dietary advice. Do not start diabetes medicine on your own.",
            ),
            "hi": (
                "अधिक मान मधुमेह, हाल में मीठा खाना, या तनाव से जुड़ा हो सकता है — पक्के के लिए दोबारा टेस्ट अच्छा रहेगा।",
                "डॉक्टर से दोबारा ग्लूकोज़ या HbA1c जांच और आहार सलाह के बारे में पूछें। बिना सलाह मधुमेह की दवा न शुरू करें।",
            ),
            "ta": (
                "அதிக மதிப்பு நீரிழிவு, அண்மையில் இனிப்பு உணவுகள் அல்லது மன அழுத்தத்துடன் தொடர்புடையதாக இருக்கலாம் — மீண்டும் பரிசோதனை செய்வது நல்லது.",
                "மீண்டும் குளுக்கோஸ் அல்லது HbA1c பரிசோதனை மற்றும் உணவு ஆலோசனை பற்றி மருத்துவரிடம் கேளுங்கள். மருந்தை நீங்களே தொடங்க வேண்டாம்.",
            ),
        },
    },
    "hba1c": {
        "high": {
            "en": (
                "A high value suggests average sugar levels were raised over recent months, commonly seen in diabetes management.",
                "Ask your doctor about diet, activity, and whether your diabetes plan needs review. Do not change medicine doses yourself.",
            ),
            "hi": (
                "अधिक मान दर्शाता है कि पिछले महीनों में औसत शर्करा स्तर अधिक रहा, जो अक्सर मधुमेह प्रबंधन में देखा जाता है।",
                "डॉक्टर से आहार, व्यायाम, और मधुमेह योजना की समीक्षा के बारे में पूछें। बिना सलाह दवा की मात्रा न बदलें।",
            ),
            "ta": (
                "அதிக மதிப்பு கடந்த மாதங்களில் சராசரி சர்க்கரை அதிகமாக இருந்ததை காட்டுகிறது, பொதுவாக நீரிழிவு மேலாண்மையில் காணப்படும்.",
                "உணவு, உடல் செயல்பாடு மற்றும் நீரிழிவு திட்டத்தின் மதிப்பாய்வு பற்றி மருத்துவரிடம் கேளுங்கள். மருந்தை நீங்களே மாற்ற வேண்டாம்.",
            ),
        },
    },
    "total cholesterol": {
        "high": {
            "en": (
                "A high value may be linked to diet, family history, or thyroid issues.",
                "Ask your doctor for a full lipid profile and lifestyle advice. Do not start cholesterol medicine on your own.",
            ),
            "hi": (
                "अधिक मान आहार, पारिवारिक इतिहास, या थायराइड समस्या से जुड़ा हो सकता है।",
                "डॉक्टर से पूर्ण लिपिड प्रोफ़ाइल और जीवनशैली सलाह मांगें। बिना सलाह कोलेस्ट्रॉल की दवा न शुरू करें।",
            ),
            "ta": (
                "அதிக மதிப்பு உணவு, குடும்ப வரலாறு அல்லது தைராய்டு பிரச்சனைகளுடன் தொடர்புடையதாக இருக்கலாம்.",
                "முழு lipid profile மற்றும் வாழ்க்கை முறை ஆலோசனைக்காக மருத்துவரிடம் கேளுங்கள். மருந்தை நீங்களே தொடங்க வேண்டாம்.",
            ),
        },
    },
    "ldl cholesterol": {
        "high": {
            "en": (
                "A high LDL ('bad' cholesterol) may raise heart risk if combined with other factors.",
                "Ask your doctor whether your overall heart risk and diet need review. Do not start medicines without advice.",
            ),
            "hi": (
                "अधिक LDL ('खराब' कोलेस्ट्रॉल) अन्य कारकों के साथ हृदय जोखिम बढ़ा सकता है।",
                "डॉक्टर से पूछें कि क्या हृदय जोखिम और आहार की समीक्षा जरूरी है। बिना सलाह दवा न शुरू करें।",
            ),
            "ta": (
                "அதிக LDL ('கெட்ட' கொழுப்பு) மற்ற காரணிகளுடன் சேர்ந்தால் இதய ஆபத்தை அதிகரிக்கலாம்.",
                "இதய ஆபத்து மற்றும் உணவு மதிப்பாய்வு தேவையா என மருத்துவரிடம் கேளுங்கள். மருந்தை நீங்களே தொடங்க வேண்டாம்.",
            ),
        },
    },
    "hdl cholesterol": {
        "low": {
            "en": (
                "A low HDL ('good' cholesterol) may relate to inactivity, smoking, or diet.",
                "Ask your doctor about exercise and lifestyle changes that raise good cholesterol. Do not start medicine yourself.",
            ),
            "hi": (
                "कम HDL ('अच्छा' कोलेस्ट्रॉल) निष्क्रियता, धूम्रपान, या आहार से जुड़ा हो सकता है।",
                "डॉक्टर से व्यायाम और जीवनशैली बदलाव के बारे में पूछें। बिना सलाह दवा न शुरू करें।",
            ),
            "ta": (
                "குறைந்த HDL ('நல்ல' கொழுப்பு) உடல் செயல்பாடின்மை, புகைபிடித்தல் அல்லது உணவுடன் தொடர்புடையதாக இருக்கலாம்.",
                "உடற்பயிற்சி மற்றும் வாழ்க்கை முறை மாற்றங்கள் பற்றி மருத்துவரிடம் கேளுங்கள். மருந்தை நீங்களே தொடங்க வேண்டாம்.",
            ),
        },
    },
    "triglycerides": {
        "high": {
            "en": (
                "A high value may relate to sugars, alcohol, or fatty diet.",
                "Ask your doctor about diet changes and a repeat fasting test. Do not start any medicine on your own.",
            ),
            "hi": (
                "अधिक मान शक्कर, शराब, या वसायुक्त आहार से जुड़ा हो सकता है।",
                "डॉक्टर से आहार बदलाव और दोबारा खाली पेट जांच के बारे में पूछें। बिना सलाह कोई दवा न लें।",
            ),
            "ta": (
                "அதிக மதிப்பு சர்க்கரை, மது அல்லது கொழுப்பு உணவுடன் தொடர்புடையதாக இருக்கலாம்.",
                "உணவு மாற்றங்கள் மற்றும் மீண்டும் வெறும் வயிற்றில் பரிசோதனை பற்றி மருத்துவரிடம் கேளுங்கள். மருந்தை நீங்களே எடுக்க வேண்டாம்.",
            ),
        },
    },
    "creatinine": {
        "high": {
            "en": (
                "A high value may relate to dehydration, kidney strain, or muscle factors.",
                "Ask your doctor for a repeat test and possibly a kidney check-up. Do not take any medicine or painkiller on your own.",
            ),
            "hi": (
                "अधिक मान निर्जलीकरण, गुर्दे पर दबाव, या मांसपेशियों के कारणों से जुड़ा हो सकता है।",
                "डॉक्टर से दोबारा टेस्ट और संभवतः गुर्दे की जांच के लिए पूछें। बिना सलाह कोई दवा या दर्दनिवारक न लें।",
            ),
            "ta": (
                "அதிக மதிப்பு நீரிழப்பு, சிறுநீரக அழுத்தம் அல்லது தசை காரணிகளுடன் தொடர்புடையதாக இருக்கலாம்.",
                "மீண்டும் பரிசோதனை மற்றும் சிறுநீரக பரிசோதனைக்காக மருத்துவரிடம் கேளுங்கள். வலி நிவாரணி மருந்தை நீங்களே எடுக்க வேண்டாம்.",
            ),
        },
    },
    "tsh": {
        "high": {
            "en": (
                "A high TSH may suggest the thyroid is working slower than usual.",
                "Ask your doctor whether thyroid medicine or a repeat thyroid panel is needed. Do not start thyroid medicine yourself.",
            ),
            "hi": (
                "अधिक TSH बताता है कि थायराइड सामान्य से धीमा काम कर रहा है।",
                "डॉक्टर से पूछें कि क्या थायराइड दवा या दोबारा थायराइड जांच जरूरी है। बिना सलाह थायराइड दवा न लें।",
            ),
            "ta": (
                "அதிக TSH தைராய்டு வழக்கத்தை விட மெதுவாக செயல்படுவதை சுட்டிக்காட்டலாம்.",
                "தைராய்டு மருந்து அல்லது மீண்டும் தைராய்டு பரிசோதனை தேவையா என மருத்துவரிடம் கேளுங்கள். மருந்தை நீங்களே எடுக்க வேண்டாம்.",
            ),
        },
    },
    "uric acid": {
        "high": {
            "en": (
                "A high value may be linked to diet, kidney function, or conditions like gout.",
                "Ask your doctor whether your diet or medicines need review. Do not start any joint medicine yourself.",
            ),
            "hi": (
                "अधिक मान आहार, गुर्दे की कार्यप्रणाली, या गाउट जैसी स्थितियों से जुड़ा हो सकता है।",
                "डॉक्टर से पूछें कि क्या आहार या दवाओं की समीक्षा जरूरी है। बिना सलाह जोड़ों की कोई दवा न लें।",
            ),
            "ta": (
                "அதிக மதிப்பு உணவு, சிறுநீரக செயல்பாடு அல்லது gout போன்ற நிலைகளுடன் தொடர்புடையதாக இருக்கலாம்.",
                "உணவு அல்லது மருந்துகள் மதிப்பாய்வு தேவையா என மருத்துவரிடம் கேளுங்கள். மருந்தை நீங்களே எடுக்க வேண்டாம்.",
            ),
        },
    },
    "sodium (na+)": {
        "low": {
            "en": (
                "A low value may relate to fluid imbalance, medicines, or diet.",
                "Ask your doctor whether a repeat test or fluid guidance is needed. Do not change salt or medicines on your own.",
            ),
            "hi": (
                "कम मान तरल संतुलन, दवाइयों, या आहार से जुड़ा हो सकता है।",
                "डॉक्टर से पूछें कि क्या दोबारा टेस्ट या तरल पदार्थ सलाह जरूरी है। बिना सलाह नमक या दवा न बदलें।",
            ),
            "ta": (
                "குறைந்த மதிப்பு திரவ சமநிலை, மருந்துகள் அல்லது உணவுடன் தொடர்புடையதாக இருக்கலாம்.",
                "மீண்டும் பரிசோதனை அல்லது திரவ ஆலோசனை தேவையா என மருத்துவரிடம் கேளுங்கள். உப்பு அல்லது மருந்தை நீங்களே மாற்ற வேண்டாம்.",
            ),
        },
        "high": {
            "en": (
                "A high value may relate to dehydration or low water intake.",
                "Ask your doctor about fluid intake and a repeat test. Do not change any medicine on your own.",
            ),
            "hi": (
                "अधिक मान निर्जलीकरण या कम पानी पीने से जुड़ा हो सकता है।",
                "डॉक्टर से तरल पदार्थ और दोबारा टेस्ट के बारे में पूछें। बिना सलाह कोई दवा न बदलें।",
            ),
            "ta": (
                "அதிக மதிப்பு நீரிழப்பு அல்லது குறைந்த நீர் உட்கொள்ளலுடன் தொடர்புடையதாக இருக்கலாம்.",
                "திரவ உட்கொள்ளல் மற்றும் மீண்டும் பரிசோதனை பற்றி மருத்துவரிடம் கேளுங்கள். மருந்தை நீங்களே மாற்ற வேண்டாம்.",
            ),
        },
    },
    "potassium (k+)": {
        "low": {
            "en": (
                "A low value may relate to medicines, dehydration, or dietary changes.",
                "Ask your doctor whether potassium needs checking or treating. Do not take potassium supplements yourself.",
            ),
            "hi": (
                "कम मान दवाइयों, निर्जलीकरण, या आहार बदलाव से जुड़ा हो सकता है।",
                "डॉक्टर से पूछें कि क्या पोटैशियम की जांच या इलाज जरूरी है। बिना सलाह पोटैशियम सप्लीमेंट न लें।",
            ),
            "ta": (
                "குறைந்த மதிப்பு மருந்துகள், நீரிழப்பு அல்லது உணவு மாற்றங்களுடன் தொடர்புடையதாக இருக்கலாம்.",
                "பொட்டாசியம் பரிசோதனை அல்லது சிகிச்சை தேவையா என மருத்துவரிடம் கேளுங்கள். பொட்டாசியம் சப்ளிமெண்ட் எடுக்க வேண்டாம்.",
            ),
        },
        "high": {
            "en": (
                "A high value may relate to kidney function, medicines, or diet — needs early review.",
                "Ask for advice soon; your doctor may order a repeat test. Do not change diet or medicines without guidance.",
            ),
            "hi": (
                "अधिक मान गुर्दे की कार्यप्रणाली, दवाइयों, या आहार से जुड़ा हो सकता है — जल्द समीक्षा जरूरी।",
                "जल्द सलाह लें; डॉक्टर दोबारा टेस्ट करा सकते हैं। बिना सलाह आहार या दवा न बदलें।",
            ),
            "ta": (
                "அதிக மதிப்பு சிறுநீரக செயல்பாடு, மருந்துகள் அல்லது உணவுடன் தொடர்புடையதாக இருக்கலாம் — விரைவில் மதிப்பாய்வு தேவை.",
                "விரைவில் ஆலோசனை பெறுங்கள்; மீண்டும் பரிசோதனை செய்யலாம். உணவு அல்லது மருந்தை மாற்ற வேண்டாம்.",
            ),
        },
    },
}


# Common conditions mentioned as *possibilities* when a result is out of
# range. Language-safe term list used to build per-value "possible conditions"
# chips. Always possibility-based, never a diagnosis.
CONDITION_TERMS: dict[str, dict[str, str]] = {
    "anemia": {"en": "Anemia (low blood count)", "hi": "एनीमिया (खून की कमी)", "ta": "இரத்த சோகை (இரத்தம் குறைவு)"},
    "iron-deficiency": {"en": "Iron deficiency", "hi": "आयरन की कमी", "ta": "இரும்பு குறைபாடு"},
    "blood-loss": {"en": "Blood loss", "hi": "रक्त हानि", "ta": "இரத்த இழப்பு"},
    "b12-deficiency": {"en": "Vitamin B12 deficiency", "hi": "विटामिन B12 की कमी", "ta": "வைட்டமின் B12 குறைபாடு"},
    "folate-deficiency": {"en": "Folate deficiency", "hi": "फोलेट की कमी", "ta": "ஃபோலேட் குறைபாடு"},
    "nutritional-deficiency": {"en": "Nutritional deficiency", "hi": "पोषण की कमी", "ta": "ஊட்டச்சத்து குறைபாடு"},
    "dehydration": {"en": "Dehydration", "hi": "निर्जलीकरण", "ta": "நீரிழப்பு"},
    "high-altitude": {"en": "Living at high altitude", "hi": "ऊँचाई पर रहना", "ta": "அதிக உயரத்தில் வசிப்பது"},
    "lung-condition": {"en": "Lung condition", "hi": "फेफड़ों की स्थिति", "ta": "நுரையீரல் பிரச்சனை"},
    "smoking": {"en": "Smoking", "hi": "धूम्रपान", "ta": "புகைபிடித்தல்"},
    "infection": {"en": "Infection", "hi": "संक्रमण", "ta": "தொற்று"},
    "inflammation": {"en": "Inflammation", "hi": "सूजन", "ta": "வீக்கம்"},
    "stress": {"en": "Physical stress", "hi": "शारीरिक तनाव", "ta": "உடல் அழுத்தம்"},
    "immune-response": {"en": "Immune response", "hi": "प्रतिरक्षा प्रतिक्रिया", "ta": "நோய் எதிர்ப்பு மறுமொழி"},
    "allergy": {"en": "Allergy", "hi": "एलर्जी", "ta": "ஒவ்வாமை"},
    "bone-marrow-change": {"en": "Bone marrow change", "hi": "अस्थि मज्जा में बदलाव", "ta": "எலும்பு மஜ்ஜை மாற்றம்"},
    "medication-effect": {"en": "Medicine side-effect", "hi": "दवाइयों का प्रभाव", "ta": "மருந்து பக்க விளைவு"},
    "pregnancy": {"en": "Pregnancy", "hi": "गर्भावस्था", "ta": "கர்ப்பம்"},
    "diabetes": {"en": "High blood sugar (diabetes)", "hi": "उच्च रक्त शर्करा (मधुमेह)", "ta": "அதிக சர்க்கரை (நீரிழிவு)"},
    "prediabetes": {"en": "Pre-diabetes", "hi": "प्री-मधुमेह", "ta": "முன் நீரிழிவு"},
    "insulin-resistance": {"en": "Insulin resistance", "hi": "इंसुलिन प्रतिरोध", "ta": "இன்சுலின் எதிர்ப்பு"},
    "metabolic-syndrome": {"en": "Metabolic syndrome", "hi": "मेटाबोलिक सिंड्रोम", "ta": "வளர்சிதை மாற்ற நோய்க்குறி"},
    "high-fat-diet": {"en": "High-fat diet", "hi": "उच्च वसा आहार", "ta": "அதிக கொழுப்பு உணவு"},
    "hypothyroidism": {"en": "Underactive thyroid", "hi": "थायराइड की कम गतिविधि", "ta": "தைராய்டு செயலிழப்பு"},
    "hyperthyroidism": {"en": "Overactive thyroid", "hi": "थायराइड की अधिक गतिविधि", "ta": "தைராய்டு அதிக செயல்பாடு"},
    "thyroiditis": {"en": "Thyroid inflammation", "hi": "थायराइड सूजन", "ta": "தைராய்டு வீக்கம்"},
    "kidney-strain": {"en": "Kidney strain", "hi": "गुर्दे पर असर", "ta": "சிறுநீரக பாதிப்பு"},
    "kidney-stones": {"en": "Kidney stones", "hi": "गुर्दे की पथरी", "ta": "சிறுநீரக கல்"},
    "urinary-infection": {"en": "Urinary infection", "hi": "मूत्र संक्रमण", "ta": "சிறுநீர் தொற்று"},
    "gout": {"en": "Gout / high uric acid", "hi": "गाउट / अधिक यूरिक एसिड", "ta": "கீல்வாதம் / அதிக யூரிக் அமிலம்"},
    "liver-strain": {"en": "Liver strain", "hi": "लीवर पर असर", "ta": "கல்லீரல் பாதிப்பு"},
    "fatty-liver": {"en": "Fatty liver", "hi": "फैटी लीवर", "ta": "கொழுப்பு கல்லீரல்"},
    "gallbladder-issue": {"en": "Gall bladder issue", "hi": "पित्ताशय की समस्या", "ta": "பித்தப்பை பிரச்சனை"},
    "muscle-injury": {"en": "Muscle strain", "hi": "मांसपेशियों में खिंचाव", "ta": "தசை காயம்"},
    "heart-strain": {"en": "Heart muscle strain", "hi": "हृदय की मांसपेशियों पर असर", "ta": "இதய தசை பாதிப்பு"},
    "heart-attack-risk": {"en": "Heart attack risk", "hi": "दिल का दौरा पड़ने का खतरा", "ta": "மாரடைப்பு அபாயம்"},
    "bleeding-risk": {"en": "Higher bleeding tendency", "hi": "खून बहने की प्रवृत्ति", "ta": "இரத்தப்போக்கு அபாயம்"},
    "clotting-risk": {"en": "Higher clotting tendency", "hi": "थक्का बनने की प्रवृत्ति", "ta": "இரத்த உறைவு அபாயம்"},
    "autoimmune": {"en": "Autoimmune reaction", "hi": "ऑटोइम्यून प्रतिक्रिया", "ta": "தன்னுடல் எதிர்ப்பு எதிர்வினை"},
    "tissue-damage": {"en": "Tissue stress or damage", "hi": "ऊतकों पर दबाव या क्षति", "ta": "திசு அழுத்தம் அல்லது சேதம்"},
    "dvt-risk": {"en": "Possible clot in a vein", "hi": "नस में थक्का बनने की संभावना", "ta": "நரம்பில் இரத்த உறைவு சாத்தியம்"},
    "liver-cirrhosis": {"en": "Advanced liver damage", "hi": "लीवर की गंभीर क्षति", "ta": "கடுமையான கல்லீரல் பாதிப்பு"},
    "chronic-liver-disease": {"en": "Chronic liver disease", "hi": "पुरानी लीवर बीमारी", "ta": "நாள்பட்ட கல்லீரல் நோய்"},
    "jaundice": {"en": "Jaundice", "hi": "पीलिया", "ta": "மஞ்சள் காமாலை"},
    "protein-deficiency": {"en": "Low protein / malnutrition", "hi": "कम प्रोटीन / कुपोषण", "ta": "குறைந்த புரதம்"},
    "kidney-protein-loss": {"en": "Protein leaking through kidneys", "hi": "गुर्दे से प्रोटीन रिसाव", "ta": "சிறுநீரக வழியே புரதம் வெளியேறுதல்"},
    "bone-disorder": {"en": "Bone metabolism issue", "hi": "हड्डियों की चयापचय समस्या", "ta": "எலும்பு வளர்சிதை மாற்ற பிரச்சனை"},
    "dvt-troponin": {"en": "Heart muscle strain", "hi": "हृदय की मांसपेशियों पर असर", "ta": "இதய தசை பாதிப்பு"},
    "blood-disease": {"en": "Blood cell condition", "hi": "रक्त कोशिका की स्थिति", "ta": "இரத்த அணு நிலை"},
    "high-protein-diet": {"en": "High-protein diet", "hi": "उच्च प्रोटीन आहार", "ta": "அதிக புரத உணவு"},
    "high-purine-diet": {"en": "High-purine diet", "hi": "उच्च प्यूरीन आहार", "ta": "அதிக பியூரின் உணவு"},
    "iron-overload": {"en": "Excess iron in the body", "hi": "शरीर में अधिक आयरन", "ta": "உடலில் அதிக இரும்பு"},
    "pancreas-strain": {"en": "Pancreas strain", "hi": "पैनक्रियाज पर असर", "ta": "கணைய பாதிப்பு"},
    "post-surgery": {"en": "Recent surgery or bed rest", "hi": "हाल की सर्जरी या बेड रेस्ट", "ta": "சமீபத்திய அறுவை சிகிச்சை அல்லது படுக்கை ஓய்வு"},
    "vitamin-k-deficiency": {"en": "Vitamin K deficiency", "hi": "विटामिन K की कमी", "ta": "வைட்டமின் K குறைபாடு"},
}


# canonical metric -> status -> possible condition ids (possibility-based).
POSSIBLE_CONDITIONS: dict[str, dict[str, list[str]]] = {
    "hemoglobin (hb)": {"high": ["dehydration", "high-altitude", "lung-condition", "smoking"], "low": ["anemia", "blood-loss", "iron-deficiency", "b12-deficiency"]},
    "packed cell volume (pcv)": {"high": ["dehydration", "lung-condition", "high-altitude"], "low": ["anemia", "blood-loss", "iron-deficiency"]},
    "red blood cells (rbc)": {"high": ["dehydration", "smoking", "lung-condition", "high-altitude"], "low": ["anemia", "blood-loss", "b12-deficiency", "nutritional-deficiency"]},
    "mean corpuscular volume (mcv)": {"high": ["b12-deficiency", "folate-deficiency"], "low": ["iron-deficiency", "anemia"]},
    "mean corpuscular hemoglobin (mch)": {"high": ["b12-deficiency", "folate-deficiency"], "low": ["iron-deficiency", "anemia"]},
    "mean corpuscular hemoglobin concentration (mchc)": {"high": ["dehydration", "medication-effect"], "low": ["iron-deficiency", "anemia"]},
    "red cell distribution width (rdw)": {"high": ["iron-deficiency", "b12-deficiency", "folate-deficiency"], "low": ["anemia"]},
    "white blood cells (wbc)": {"high": ["infection", "inflammation", "stress", "immune-response"], "low": ["infection", "medication-effect", "bone-marrow-change"]},
    "neutrophils": {"high": ["infection", "inflammation"], "low": ["infection", "medication-effect", "bone-marrow-change"]},
    "lymphocytes": {"high": ["infection", "immune-response"], "low": ["stress", "medication-effect", "autoimmune"]},
    "monocytes": {"high": ["infection", "inflammation", "tissue-damage"], "low": ["bone-marrow-change", "medication-effect"]},
    "eosinophils": {"high": ["allergy", "inflammation", "infection"], "low": ["stress"]},
    "basophils": {"high": ["allergy", "inflammation"], "low": []},
    "platelets": {"high": ["inflammation", "infection", "blood-loss"], "low": ["infection", "medication-effect", "bone-marrow-change", "bleeding-risk"]},
    "platelet distribution width (pdw)": {"high": ["inflammation", "clotting-risk"], "low": []},
    "mean platelet volume (mpv)": {"high": ["clotting-risk", "inflammation"], "low": ["medication-effect", "bone-marrow-change"]},
    "plateletcrit (pct)": {"high": ["inflammation", "clotting-risk"], "low": []},
    "glucose": {"high": ["prediabetes", "diabetes", "insulin-resistance"], "low": ["medication-effect", "nutritional-deficiency"]},
    "hba1c": {"high": ["prediabetes", "diabetes"], "low": []},
    "total cholesterol": {"high": ["high-fat-diet", "hypothyroidism", "metabolic-syndrome"], "low": ["nutritional-deficiency"]},
    "triglycerides": {"high": ["high-fat-diet", "diabetes", "insulin-resistance", "metabolic-syndrome"], "low": []},
    "hdl cholesterol": {"high": [], "low": ["metabolic-syndrome", "insulin-resistance", "high-fat-diet"]},
    "ldl cholesterol": {"high": ["high-fat-diet", "metabolic-syndrome", "hyperthyroidism"], "low": []},
    "creatinine": {"high": ["kidney-strain", "dehydration", "medication-effect"], "low": ["nutritional-deficiency"]},
    "blood urea nitrogen (bun)": {"high": ["kidney-strain", "dehydration", "high-protein-diet"], "low": ["liver-strain", "nutritional-deficiency"]},
    "sodium (na+)": {"high": ["dehydration", "kidney-strain", "medication-effect"], "low": ["medication-effect", "dehydration", "kidney-strain"]},
    "potassium (k+)": {"high": ["kidney-strain", "medication-effect"], "low": ["medication-effect", "dehydration", "nutritional-deficiency"]},
    "calcium": {"high": ["bone-disorder", "hyperthyroidism", "dehydration"], "low": ["nutritional-deficiency", "kidney-strain"]},
    "chloride (cl-)": {"high": ["dehydration", "kidney-strain"], "low": ["medication-effect", "metabolic-syndrome"]},
    "bicarbonate": {"high": ["metabolic-syndrome"], "low": ["kidney-strain", "dehydration"]},
    "tsh": {"high": ["hypothyroidism", "thyroiditis"], "low": ["hyperthyroidism"]},
    "t3 (triiodothyronine)": {"high": ["hyperthyroidism"], "low": ["hypothyroidism"]},
    "t4 (thyroxine)": {"high": ["hyperthyroidism"], "low": ["hypothyroidism"]},
    "alt (sgpt)": {"high": ["liver-strain", "fatty-liver", "medication-effect"], "low": []},
    "ast (sgot)": {"high": ["liver-strain", "muscle-injury", "heart-strain"], "low": []},
    "bilirubin (total)": {"high": ["liver-strain", "jaundice", "blood-disease"], "low": []},
    "alkaline phosphatase": {"high": ["liver-strain", "gallbladder-issue", "bone-disorder"], "low": []},
    "total protein": {"high": ["dehydration", "inflammation"], "low": ["protein-deficiency", "liver-strain", "kidney-protein-loss"]},
    "albumin": {"high": ["dehydration"], "low": ["protein-deficiency", "liver-strain", "kidney-protein-loss"]},
    "uric acid": {"high": ["gout", "kidney-strain", "high-purine-diet"], "low": []},
    "c-reactive protein (crp)": {"high": ["infection", "inflammation", "tissue-damage"], "low": []},
    "esr": {"high": ["inflammation", "infection", "autoimmune"], "low": []},
    "ferritin": {"high": ["inflammation", "liver-strain", "iron-overload"], "low": ["iron-deficiency", "anemia"]},
    "vitamin b12": {"high": ["liver-strain"], "low": ["b12-deficiency", "nutritional-deficiency"]},
    "vitamin d": {"high": ["medication-effect"], "low": ["nutritional-deficiency", "bone-disorder"]},
    "iron (serum)": {"high": ["iron-overload", "liver-strain"], "low": ["iron-deficiency", "blood-loss", "nutritional-deficiency"]},
    "tibc": {"high": ["iron-deficiency", "pregnancy"], "low": ["iron-overload", "liver-strain"]},
    "transferrin saturation": {"high": ["iron-overload"], "low": ["iron-deficiency"]},
    "amylase": {"high": ["pancreas-strain", "gallbladder-issue"], "low": []},
    "lipase": {"high": ["pancreas-strain"], "low": []},
    "ggt": {"high": ["liver-strain", "fatty-liver", "medication-effect"], "low": []},
    "ldh": {"high": ["liver-strain", "tissue-damage", "anemia", "inflammation"], "low": []},
    "creatine kinase (ck)": {"high": ["muscle-injury", "heart-strain", "medication-effect"], "low": []},
    "troponin i": {"high": ["heart-strain", "heart-attack-risk"], "low": []},
    "d-dimer": {"high": ["dvt-risk", "inflammation", "post-surgery"], "low": []},
    "fibrinogen": {"high": ["inflammation", "clotting-risk", "pregnancy"], "low": ["liver-strain", "bleeding-risk"]},
    "inr": {"high": ["bleeding-risk", "liver-strain", "vitamin-k-deficiency"], "low": ["clotting-risk"]},
    "prothrombin time (pt)": {"high": ["bleeding-risk", "liver-strain", "vitamin-k-deficiency"], "low": ["clotting-risk"]},
    "aptt": {"high": ["bleeding-risk", "liver-strain"], "low": ["clotting-risk"]},
    "magnesium": {"high": ["kidney-strain", "medication-effect"], "low": ["nutritional-deficiency", "medication-effect"]},
    "phosphorus": {"high": ["kidney-strain", "bone-disorder"], "low": ["nutritional-deficiency"]},
    "albumin/globulin (a/g) ratio": {"high": [], "low": ["liver-strain", "kidney-protein-loss", "autoimmune"]},
    "reticulocyte count": {"high": ["anemia", "blood-loss"], "low": ["bone-marrow-change", "bone-disorder"]},
    "procalcitonin (pct)": {"high": ["infection", "inflammation"], "low": []},
}


def _condition_terms(ids: list[str], language: str) -> list[str]:
    """Localize condition ids into a list of display strings."""
    lang = language if language in CONDITION_TERMS.get("anemia", {}) else "en"
    out: list[str] = []
    for cid in ids:
        terms = CONDITION_TERMS.get(cid)
        if not terms:
            continue
        out.append(terms.get(lang, terms.get("en", cid)))
    return out


def _possible_conditions_for(metric: str, status: str, language: str) -> list[str]:
    """Possible conditions (localized) tied to a metric/status deviation."""
    key = metric.lower()
    ids = POSSIBLE_CONDITIONS.get(key, {}).get(status, [])
    if ids:
        return _condition_terms(ids, language)

    # Fall back to fuzzy match on the clinical-hints knowledge base name.
    for entry_key, entry in POSSIBLE_CONDITIONS.items():
        if key in entry_key or entry_key in key:
            ids = entry.get(status, [])
            if ids:
                return _condition_terms(ids, language)
    return []


def _get_clinical_hint(
    metric: str,
    status: str,
    language: Literal["en", "hi", "ta"],
) -> tuple[str, str]:
    """Return (possible_causes, doctor_guidance) for a metric/status/language."""
    key = metric.lower()
    lang = language if language in ("en", "hi", "ta") else "en"

    exact = CLINICAL_HINTS.get(key, {}).get(status)
    if exact:
        causes, guidance = exact.get(lang, exact.get("en", ("", "")))
        if causes:
            return causes, guidance

    for entry_key, entry in CLINICAL_HINTS.items():
        if key in entry_key or entry_key in key:
            variant = entry.get(status)
            if variant:
                causes, guidance = variant.get(lang, variant.get("en", ("", "")))
                if causes:
                    return causes, guidance

    generic = {
        "en": (
            f"A {status.replace('_', ' ')} result may be a sign worth understanding — your doctor can explain it best.",
            "Ask your doctor what this result means for you and whether any follow-up test is needed. Do not start or stop medicines yourself.",
        ),
        "hi": (
            f"{metric} का परिणाम समझने लायक हो सकता है — आपका डॉक्टर इसे सबसे अच्छे से समझाएगा।",
            "अपने डॉक्टर से पूछें कि इसका क्या मतलब है और क्या अनुवर्ती जांच जरूरी है। बिना सलाह दवा शुरू या बंद न करें।",
        ),
        "ta": (
            f"{metric} முடிவு புரிந்து கொள்ள வேண்டியதாக இருக்கலாம் — உங்கள் மருத்துவர் சிறப்பாக விளக்குவார்.",
            "இது என்ன அர்த்தம் மற்றும் மேலும் பரிசோதனை தேவையா என மருத்துவரிடம் கேளுங்கள். மருந்தை நீங்களே தொடங்கவோ நிறுத்தவோ வேண்டாம்.",
        ),
    }
    return generic.get(lang, generic["en"])


class SimplifiedTerm(BaseModel):
    term: str
    explanation: str
    analogy: str


class NumericalContext(BaseModel):
    metric: str
    value: str
    normal_range: str
    status: str = "within_range"  # high | low | within_range | unknown
    calm_explanation: str
    possible_causes: str = ""
    doctor_guidance: str = ""
    possible_conditions: list[str] = Field(default_factory=list)


class UIPAnalysisResult(BaseModel):
    emergency_trigger: bool = False
    report_summary: str = ""
    simplified_terms: list[SimplifiedTerm] = Field(default_factory=list)
    numerical_context: list[NumericalContext] = Field(default_factory=list)
    doctor_questions: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)

    @field_validator("doctor_questions")
    @classmethod
    def validate_doctor_questions(cls, value: list[str]) -> list[str]:
        if len(value) != 3:
            raise ValueError("doctor_questions must contain exactly 3 items")
        return value


def _build_user_prompt(scrubbed_text: str, language: Literal["en", "hi", "ta"]) -> str:
    lang_instruction = LANGUAGE_INSTRUCTIONS[language]
    return (
        f"{lang_instruction}\n\n"
        "Analyze the following de-identified laboratory report text. "
        "Respond with ONLY valid JSON matching the required schema. No markdown fences.\n\n"
        f"--- LAB REPORT TEXT ---\n{scrubbed_text}\n--- END ---"
    )


def _extract_json_payload(raw: str) -> dict:
    cleaned = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response")

    return json.loads(cleaned[start : end + 1])


METRIC_PATTERN = re.compile(
    r"(?:^|\n)\s*([A-Za-z][A-Za-z0-9\s()/-]{2,90}?)\s*[:=]\s*"
    r"((?:Could not read)|[\d.]+\s*(?:mg/dL|g/dL|mmol/L|U/L|u/L|IU/L|mIU/mL|uIU/mL|ng/mL|/L|/dL|/uL|x10[\^]?\d+/uL|%|pg|fL|mEq/L|K/uL|M/uL)?)",
    re.IGNORECASE | re.MULTILINE,
)

INLINE_RANGE_PATTERN = re.compile(
    r"\((?:Reference|Ref\.?|Normal)\s*[:=]?\s*([^)]+)\)",
    re.IGNORECASE,
)

EMERGENCY_KEYWORDS = (
    "critical",
    "panic",
    "urgent",
    "immediate",
    "life-threatening",
    "stat",
)


def _clean_metric_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip(" -*")


def _parse_lab_metrics(scrubbed_text: str) -> list[tuple[str, str, str]]:
    metrics: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    for match in METRIC_PATTERN.finditer(scrubbed_text):
        metric = _clean_metric_name(match.group(1))
        value = match.group(2).strip()
        if not metric or len(metric) < 2:
            continue

        # Only recognized lab biomarkers may become "metrics". OCR header garbage
        # ("Age 21 Years...", "PID 555", "e Generated on...") must never surface
        # as fake results in Simplified Terms or Your Numbers.
        if not is_recognized_biomarker(metric):
            continue

        key = metric.lower()
        if key in seen:
            continue
        seen.add(key)

        line_end = scrubbed_text.find("\n", match.end())
        line_slice = scrubbed_text[match.start() : line_end if line_end != -1 else match.end() + 120]
        range_match = INLINE_RANGE_PATTERN.search(line_slice)
        normal_range = range_match.group(1).strip() if range_match else "See your lab report"

        # Tolerate OCR-garbled labels (e.g. "Necmad 42-50") by pulling the
        # numeric range out when the captured text does not start with a digit.
        if normal_range and not re.match(r"\d", normal_range):
            numeric = re.search(r"(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)", normal_range)
            if numeric:
                normal_range = f"{numeric.group(1)}-{numeric.group(2)}"

        metrics.append((metric, value, normal_range))

    return metrics


def _mock_analysis_from_text(
    scrubbed_text: str,
    language: Literal["en", "hi", "ta"],
) -> UIPAnalysisResult:
    parsed = _parse_lab_metrics(scrubbed_text)
    if not parsed:
        raise SafetyFilterError(
            "We couldn't clearly read the test names and values from this document. "
            "Try a clearer, closer photo, or type the values using the 'Type your test values instead' option."
        )

    lowered = scrubbed_text.lower()
    emergency_trigger = any(keyword in lowered for keyword in EMERGENCY_KEYWORDS)

    statuses = [
        _compare_value_to_range(value, normal_range)
        for _, value, normal_range in parsed
    ]

    if language == "hi":
        term_expl = "यह एक लैब परीक्षण है जो आपके रक्त या स्वास्थ्य की जांच करता है।"
        term_analogy = "यह शरीर की जांच रिपोर्ट की तरह है — संख्याएँ बताती हैं कि सब ठीक है या नहीं।"
        num_expl = "यह आपकी रिपोर्ट से पढ़ा गया मान है। आपका डॉक्टर इसे आपके लिए सही संदर्भ में समझाएगा।"
        q_templates = [
            "मेरे {metric} का परिणाम ({value}) मेरे स्वास्थ्य के लिए क्या मायने रखता है?",
            "क्या इनमें से कोई परिणाम सामान्य सीमा से बाहर है, और अगले कदम क्या होने चाहिए?",
            "क्या इन रिपोर्ट के आधार पर कोई अतिरिक्त जांच या फॉलो-अप की जरूरत है?",
        ]
        summary = _build_mock_summary(parsed, statuses, "hi")
        next_steps = _build_mock_next_steps(emergency_trigger, "hi")
    elif language == "ta":
        term_expl = "இது உங்கள் இரத்தம் அல்லது உடல்நலத்தை பரிசோதிக்கும் ஒரு ஆய்வக பரிசோதனை."
        term_analogy = "இது உடல் பரிசோதனை அறிக்கை போன்றது — எண்கள் எல்லாம் சரியா என்று காட்டுகிறது."
        num_expl = "இது உங்கள் அறிக்கையிலிருந்து படிக்கப்பட்ட மதிப்பு. உங்கள் மருத்துவர் இதை சரியான சூழலில் விளக்குவார்."
        q_templates = [
            "என் {metric} முடிவு ({value}) என் உடல்நலத்திற்கு என்ன அர்த்தம்?",
            "இந்த முடிவுகளில் ஏதேனும் சாதாரண வரம்பை விட வேறுபடுகிறதா, அடுத்து என்ன செய்ய வேண்டும்?",
            "இந்த அறிக்கையின் அடிப்படையில் கூடுதல் பரிசோதனை அல்லது follow-up தேவையா?",
        ]
        summary = _build_mock_summary(parsed, statuses, "ta")
        next_steps = _build_mock_next_steps(emergency_trigger, "ta")
    else:
        term_expl = "This is a lab test that checks part of your blood or body chemistry."
        term_analogy = "Think of it like a report card for one part of your health."
        num_expl = "This value comes from your uploaded report. Your doctor can explain what it means for you personally."
        q_templates = [
            "What does my {metric} result ({value}) mean for my overall health?",
            "Are any of these results outside the usual range, and what are the next steps?",
            "Based on this report, do I need any follow-up tests or a repeat lab draw?",
        ]
        summary = _build_mock_summary(parsed, statuses, "en")
        next_steps = _build_mock_next_steps(emergency_trigger, "en")

    simplified_terms = [
        SimplifiedTerm(
            term=metric,
            explanation=term_expl,
            analogy=term_analogy,
        )
        for metric, _, _ in parsed[:3]
    ]

    numerical_context = []
    for (metric, value, normal_range), status in zip(parsed, statuses):
        causes, guidance = "", ""
        conditions: list[str] = []
        if status in ("high", "low"):
            causes, guidance = _get_clinical_hint(metric, status, language)
            conditions = _possible_conditions_for(metric, status, language)
        numerical_context.append(
            NumericalContext(
                metric=metric,
                value=value,
                normal_range=normal_range,
                status=status,
                calm_explanation=num_expl,
                possible_causes=causes,
                doctor_guidance=guidance,
                possible_conditions=conditions,
            )
        )

    primary = parsed[0]
    doctor_questions = [
        q_templates[0].format(metric=primary[0], value=primary[1]),
        q_templates[1],
        q_templates[2],
    ]

    return UIPAnalysisResult(
        emergency_trigger=emergency_trigger,
        report_summary=summary,
        simplified_terms=simplified_terms,
        numerical_context=numerical_context,
        doctor_questions=doctor_questions,
        next_steps=next_steps,
    )


def _compare_value_to_range(value_str: str, normal_range: str) -> str:
    """Return 'low', 'high', or 'within_range' for a value vs its reference range."""
    num = _extract_number(value_str)
    if num is None:
        return "unknown"

    low, high = _parse_range_numbers(normal_range)
    if low is None or high is None:
        return "within_range"

    if num < low:
        return "low"
    if num > high:
        return "high"
    return "within_range"


def _extract_number(text: str) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _parse_range_numbers(normal_range: str) -> tuple[float | None, float | None]:
    less_than = re.match(r"<\s*([\d.]+)", normal_range)
    if less_than:
        return None, float(less_than.group(1))

    greater_than = re.match(r">\s*([\d.]+)", normal_range)
    if greater_than:
        return float(greater_than.group(1)), None

    range_match = re.search(r"([\d.]+)\s*[-–—~]\s*([\d.]+)", normal_range)
    if range_match:
        return float(range_match.group(1)), float(range_match.group(2))

    return None, None


def _metric_group(metric: str) -> str | None:
    """Map a metric name to the health pattern group it belongs to."""
    m = metric.lower()
    if any(k in m for k in ("hemoglobin", "haemoglobin", " hb", "packed cell", "pcv", "corpuscular", "rbc")):
        return "anemia"
    if any(k in m for k in ("white blood", "wbc", "neutrophil", "leukocyte")):
        return "infection"
    if any(k in m for k in ("glucose", "sugar", "hba1c")):
        return "diabetes"
    if any(k in m for k in ("cholesterol", "triglyceride", "ldl", "hdl")):
        return "lipids"
    if any(k in m for k in ("tsh", "thyroid")):
        return "thyroid"
    if any(k in m for k in ("creatinine", "urea", "bun", "uric acid")):
        return "kidney"
    if "platelet" in m:
        return "platelets"
    return None


_OVERALL_HINTS: dict[str, dict[str, str]] = {
    "anemia": {
        "en": "Your report shows a possible pattern that may be linked to low blood count (anemia) — several red-cell values are below typical.",
        "hi": "आपकी रिपोर्ट एक संभावित पैटर्न दिखाती है जो खून की कमी (एनीमिया) से जुड़ा हो सकता है — कई लाल रक्त कोशिका मान सामान्य से कम हैं।",
        "ta": "உங்கள் அறிக்கை சாத்தியமான முறையை காட்டுகிறது, இது இரத்த சோகை (anemia) உடன் தொடர்புடையதாக இருக்கலாம் — பல சிவப்பு இரத்த அணு மதிப்புகள் குறைவாக உள்ளன.",
    },
    "infection": {
        "en": "Your report shows a possible pattern that may be linked to an infection or inflammation — white blood cell counts are above typical.",
        "hi": "आपकी रिपोर्ट एक संभावित पैटर्न दिखाती है जो किसी संक्रमण या सूजन से जुड़ा हो सकता है — सफेद रक्त कोशिकाएँ सामान्य से अधिक हैं।",
        "ta": "உங்கள் அறிக்கை சாத்தியமான முறையை காட்டுகிறது, இது தொற்று அல்லது வீக்கத்துடன் தொடர்புடையதாக இருக்கலாம் — வெள்ளை இரத்த அணுக்கள் அதிகமாக உள்ளன.",
    },
    "diabetes": {
        "en": "Your report shows a possible pattern that may be linked to high blood sugar (diabetes) — sugar-related values are above typical.",
        "hi": "आपकी रिपोर्ट एक संभावित पैटर्न दिखाती है जो उच्च रक्त शर्करा (मधुमेह) से जुड़ा हो सकता है — शर्करा से जुड़े मान सामान्य से अधिक हैं।",
        "ta": "உங்கள் அறிக்கை சாத்தியமான முறையை காட்டுகிறது, இது அதிக இரத்த சர்க்கரை (நீரிழிவு) உடன் தொடர்புடையதாக இருக்கலாம் — சர்க்கரை மதிப்புகள் அதிகமாக உள்ளன.",
    },
    "lipids": {
        "en": "Your report shows a possible pattern that may be linked to higher cholesterol levels — lipid values are above typical.",
        "hi": "आपकी रिपोर्ट एक संभावित पैटर्न दिखाती है जो उच्च कोलेस्ट्रॉल से जुड़ा हो सकता है — वसा (लिपिड) मान सामान्य से अधिक हैं।",
        "ta": "உங்கள் அறிக்கை சாத்தியமான முறையை காட்டுகிறது, இது அதிக கொலஸ்ட்ரால் உடன் தொடர்புடையதாக இருக்கலாம் — கொழுப்பு மதிப்புகள் அதிகமாக உள்ளன.",
    },
    "thyroid-high": {
        "en": "Your report shows a possible pattern that may be linked to an overactive thyroid — thyroid values are above typical.",
        "hi": "आपकी रिपोर्ट एक संभावित पैटर्न दिखाती है जो थायराइड की अधिक गतिविधि से जुड़ा हो सकता है — थायराइड मान सामान्य से अधिक हैं।",
        "ta": "உங்கள் அறிக்கை சாத்தியமான முறையை காட்டுகிறது, இது அதிக தைராய்டு செயல்பாட்டுடன் தொடர்புடையதாக இருக்கலாம் — தைராய்டு மதிப்புகள் அதிகமாக உள்ளன.",
    },
    "thyroid-low": {
        "en": "Your report shows a possible pattern that may be linked to an underactive thyroid — thyroid values are below typical.",
        "hi": "आपकी रिपोर्ट एक संभावित पैटर्न दिखाती है जो थायराइड की कम गतिविधि से जुड़ा हो सकता है — थायराइड मान सामान्य से कम हैं।",
        "ta": "உங்கள் அறிக்கை சாத்தியமான முறையை காட்டுகிறது, இது குறைந்த தைராய்டு செயல்பாட்டுடன் தொடர்புடையதாக இருக்கலாம் — தைராய்டு மதிப்புகள் குறைவாக உள்ளன.",
    },
    "kidney": {
        "en": "Your report shows a possible pattern that may be linked to kidney strain — kidney-related values are above typical.",
        "hi": "आपकी रिपोर्ट एक संभावित पैटर्न दिखाती है जो गुर्दे पर असर से जुड़ा हो सकता है — गुर्दे से जुड़े मान सामान्य से अधिक हैं।",
        "ta": "உங்கள் அறிக்கை சாத்தியமான முறையை காட்டுகிறது, இது சிறுநீரக பாதிப்புடன் தொடர்புடையதாக இருக்கலாம் — சிறுநீரக மதிப்புகள் அதிகமாக உள்ளன.",
    },
    "platelets-low": {
        "en": "Your report shows a possible pattern that may be linked to a higher bleeding tendency — platelet count is below typical.",
        "hi": "आपकी रिपोर्ट एक संभावित पैटर्न दिखाती है जो खून बहने की प्रवृत्ति से जुड़ा हो सकता है — प्लेटलेट्स सामान्य से कम हैं।",
        "ta": "உங்கள் அறிக்கை சாத்தியமான முறையை காட்டுகிறது, இது அதிக இரத்தப்போக்கு போக்குடன் தொடர்புடையதாக இருக்கலாம் — தட்டுக்கள் குறைவாக உள்ளன.",
    },
    "platelets-high": {
        "en": "Your report shows a possible pattern that may be linked to a higher clotting tendency — platelet count is above typical.",
        "hi": "आपकी रिपोर्ट एक संभावित पैटर्न दिखाती है जो खून के थक्के बनने की प्रवृत्ति से जुड़ा हो सकता है — प्लेटलेट्स सामान्य से अधिक हैं।",
        "ta": "உங்கள் அறிக்கை சாத்தியமான முறையை காட்டுகிறது, இது அதிக இரத்த உறைவு போக்குடன் தொடர்புடையதாக இருக்கலாம் — தட்டுக்கள் அதிகமாக உள்ளன.",
    },
}


def _build_mock_overall_prediction(
    parsed: list[tuple[str, str, str]],
    statuses: list[str],
    language: Literal["en", "hi", "ta"],
) -> str:
    """Best-effort, possibility-based overall reading of the whole report."""
    scores: dict[str, int] = {}
    for (metric, _, _), status in zip(parsed, statuses):
        group = _metric_group(metric)
        if not group or status == "within_range":
            continue
        if group == "anemia" and status == "low":
            scores["anemia"] = scores.get("anemia", 0) + 1
        elif group == "infection" and status == "high":
            scores["infection"] = scores.get("infection", 0) + 1
        elif group == "diabetes" and status == "high":
            scores["diabetes"] = scores.get("diabetes", 0) + 1
        elif group == "lipids" and (
            status == "high" or (metric.lower().startswith("hdl") and status == "low")
        ):
            scores["lipids"] = scores.get("lipids", 0) + 1
        elif group == "thyroid":
            if status == "high":
                scores["thyroid-high"] = scores.get("thyroid-high", 0) + 1
            elif status == "low":
                scores["thyroid-low"] = scores.get("thyroid-low", 0) + 1
        elif group == "kidney" and status == "high":
            scores["kidney"] = scores.get("kidney", 0) + 1
        elif group == "platelets":
            if status == "low":
                scores["platelets-low"] = scores.get("platelets-low", 0) + 1
            elif status == "high":
                scores["platelets-high"] = scores.get("platelets-high", 0) + 1

    if not scores:
        if any(status == "unknown" for status in statuses):
            if language == "hi":
                return (
                    "कुल मिलाकर, हम जिन मानों को पढ़ सके वे सामान्य सीमा के भीतर दिख रहे हैं, "
                    "लेकिन हम हर परीक्षण को स्पष्ट रूप से नहीं पढ़ सके — कृपया पूरी रिपोर्ट डॉक्टर से पुष्टि करवाएं।"
                )
            if language == "ta":
                return (
                    "ஒட்டுமொத்தமாக, நாங்கள் படிக்கக் கூடிய மதிப்புகள் சாதாரண வரம்பிற்குள் உள்ளன, "
                    "ஆனால் ஒவ்வொரு சோதனையையும் தெளிவாக படிக்க முடியவில்லை — முழு அறிக்கையையும் மருத்துவரிடம் உறுதிப்படுத்தவும்."
                )
            return (
                "Overall, the values we could read look like they are inside the typical range, "
                "but we couldn't clearly read every test — please verify the full report with your doctor."
            )
        if language == "hi":
            return (
                "समग्र रूप से, आपके दर्ज मान सामान्य सीमा के भीतर दिख रहे हैं — "
                "कोई स्पष्ट चेतावनी पैटर्न नहीं मिला।"
            )
        if language == "ta":
            return (
                "ஒட்டுமொத்தமாக, உங்கள் மதிப்புகள் சாதாரண வரம்பிற்குள் உள்ளன — "
                "தெளிவான எச்சரிக்கை முறை எதுவும் கண்டறியப்படவில்லை."
            )
        return (
            "Overall, the values you entered look like they are inside the typical range — "
            "no clear warning pattern was detected."
        )

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    picked = [name for name, _ in ranked[:2]]
    hints = [ _OVERALL_HINTS[name][language] for name in picked if name in _OVERALL_HINTS ]
    if not hints:
        if language == "hi":
            return "आपकी रिपोर्ट में कुछ ऐसे मान हैं जो सामान्य सीमा से बाहर हैं, और यह किसी समस्या से जुड़ा हो सकता है।"
        if language == "ta":
            return "உங்கள் அறிக்கையில் சில மதிப்புகள் சாதாரண வரம்பிற்கு வெளியே உள்ளன, இது ஒரு பிரச்சனையுடன் தொடர்புடையதாக இருக்கலாம்."
        return "Your report shows some values outside the typical range, which may be linked to a health problem."
    return " ".join(hints)


def _build_mock_summary(
    parsed: list[tuple[str, str, str]],
    statuses: list[str],
    language: Literal["en", "hi", "ta"],
) -> str:
    low = [name for (name, _, _), status in zip(parsed, statuses) if status == "low"]
    high = [name for (name, _, _), status in zip(parsed, statuses) if status == "high"]
    overall = _build_mock_overall_prediction(parsed, statuses, language)

    if language == "hi":
        if not low and not high:
            return (
                overall + " "
                "फिर भी, कृपया पूरी रिपोर्ट अपने डॉक्टर को दिखाएं।"
            )
        parts = ["आपकी रिपोर्ट के विस्तृत मान:"]
        if low:
            parts.append("सामान्य से कम: " + " और ".join(low) + "।")
        if high:
            parts.append("सामान्य से अधिक: " + " और ".join(high) + "।")
        parts.append("यह कोई निदान नहीं है — कृपया अपने डॉक्टर से इस पर चर्चा करें।")
        return overall + " " + " ".join(parts)
    if language == "ta":
        if not low and not high:
            return (
                overall + " "
                "இருப்பினும், முழு அறிக்கையையும் உங்கள் மருத்துவரிடம் காட்டுங்கள்."
            )
        parts = ["உங்கள் அறிக்கையின் விரிவான மதிப்புகள்:"]
        if low:
            parts.append("வழக்கத்தை விட குறைவு: " + " மற்றும் ".join(low) + ".")
        if high:
            parts.append("வழக்கத்தை விட அதிகம்: " + " மற்றும் ".join(high) + ".")
        parts.append("இது நோயறிதல் அல்ல — மருத்துவரிடம் விவாதிக்கவும்.")
        return overall + " " + " ".join(parts)
    if not low and not high:
        return (
            overall + " "
            "Still, please show the full report to your doctor."
        )
    parts = ["Here are the detailed values:"]
    if low:
        parts.append("Lower than typical: " + ", ".join(low) + ".")
    if high:
        parts.append("Higher than typical: " + ", ".join(high) + ".")
    parts.append("This is not a diagnosis — please discuss it with your doctor.")
    return overall + " " + " ".join(parts)


def _build_mock_next_steps(emergency_trigger: bool, language: Literal["en", "hi", "ta"]) -> list[str]:
    if language == "hi":
        urgent = ["यदि आपको सीने में दर्द, सांस लेने में तकलीफ, या बेहोशी लगे, तो तुरंत आपातकालीन सेवाओं से संपर्क करें।"]
        base = [
            "इस रिपोर्ट और सवालों की सूची अपने अगले डॉक्टर की नियुक्ति पर साथ ले जाएं।",
            "बिना डॉक्टर की सलाह के कोई दवा की खुराक न बदलें और न ही कोई नुस्खा आज़माएं।",
            "घबराएं नहीं — यह केवल जानकारी है। अपने डॉक्टर से इस पर चर्चा करें।",
        ]
        return urgent + base if emergency_trigger else base
    if language == "ta":
        urgent = ["நெஞ்சு வலி, மூச்சுத் திணறல் அல்லது மயக்கம் ஏற்பட்டால் உடனே அவசர சேவையை அழைக்கவும்."]
        base = [
            "இந்த அறிக்கையையும் கேள்விகளையும் அடுத்த மருத்துவர் சந்திப்புக்கு எடுத்துச் செல்லுங்கள்.",
            "மருத்துவரின் ஆலோசனை இல்லாமல் மருந்தை மாற்றவோ அல்லது வீட்டு வைத்தியம் முயற்சிக்கவோ வேண்டாம்.",
            "பயப்பட வேண்டாம் — இது தகவல் மட்டுமே. உங்கள் மருத்துவரிடம் பேசுங்கள்.",
        ]
        return urgent + base if emergency_trigger else base
    urgent = [
        "If you feel chest pain, severe breathlessness, or faintness, contact emergency services right away."
    ]
    base = [
        "Bring this report and the question list to your next doctor's appointment.",
        "Do not change any medicine dose or try home remedies without your doctor's advice.",
        "Stay calm — this is information only. Talk it through with your doctor.",
    ]
    return urgent + base if emergency_trigger else base


async def _call_openai(user_prompt: str) -> str:
    from openai import AsyncOpenAI

    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not configured")

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model=settings.openai_model,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": UIP_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content or ""


async def _call_anthropic(user_prompt: str) -> str:
    import httpx

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is not configured")

    payload = {
        "model": settings.anthropic_model,
        "max_tokens": 4096,
        "temperature": 0.1,
        "system": UIP_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    blocks = data.get("content", [])
    text_parts = [block.get("text", "") for block in blocks if block.get("type") == "text"]
    return "\n".join(text_parts)


async def analyze_lab_text(
    scrubbed_text: str,
    language: Literal["en", "hi", "ta"] = "en",
) -> UIPAnalysisResult:
    settings = get_settings()
    user_prompt = _build_user_prompt(scrubbed_text, language)

    if settings.ai_provider == "mock":
        logger.info("Using mock AI analysis (AI_PROVIDER=mock)")
        return _mock_analysis_from_text(scrubbed_text, language)

    raw_response = ""
    try:
        if settings.ai_provider == "openai":
            raw_response = await _call_openai(user_prompt)
        elif settings.ai_provider == "anthropic":
            raw_response = await _call_anthropic(user_prompt)
        else:
            raise ValueError(f"Unknown AI provider: {settings.ai_provider}")
    except Exception as exc:
        logger.exception("LLM call failed, falling back to mock analysis")
        if settings.ai_provider != "mock":
            return _mock_analysis_from_text(scrubbed_text, language)
        raise exc

    try:
        payload = _extract_json_payload(raw_response)
        return UIPAnalysisResult.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        logger.warning("Failed to parse LLM JSON (%s), using mock fallback", exc)
        return _mock_analysis_from_text(scrubbed_text, language)
