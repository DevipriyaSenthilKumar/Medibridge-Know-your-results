import logging
from typing import Annotated, Literal, Optional

from fastapi import FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from config import get_settings
from db import (
    add_report,
    create_session,
    create_user,
    delete_session,
    get_previous_report,
    get_report,
    get_user_by_token,
    list_reports,
    verify_user,
)
from pipeline.biomarker_extractor import filter_clinical_text
from pipeline.ocr_engine import OCRError, extract_text_from_image, is_tesseract_available
from pipeline.prescription_extractor import analyze_prescription
from pipeline.safety_filter import (
    SafetyFilterError,
    reject_imaging_document,
    scrub_pii,
    validate_lab_report_text,
)
from pipeline.tts_engine import TTSUnavailable, synthesize_speech
from pipeline.uip_framework import UIPAnalysisResult, analyze_lab_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

if is_tesseract_available():
    logger.info("Tesseract OCR: ready")
else:
    logger.warning("Tesseract OCR: not found — set TESSERACT_CMD in backend/.env")


_LANG = Literal["en", "hi", "ta"]

# User-facing error messages localized per language. Keys are the English
# strings raised by the pipeline; entries map language -> localized text.
_ERROR_L10N: dict[str, dict[str, str]] = {
    "Could not read any text from this image. Please upload a clear, well-lit photo of a text-based lab report.": {
        "en": "Could not read any text from this image. Please upload a clear, well-lit photo of a text-based lab report.",
        "hi": "इस छवि से कोई पाठ नहीं पढ़ा जा सका। कृपया टेक्स्ट-आधारित लैब रिपोर्ट की साफ़ और अच्छी रोशनी वाली फ़ोटो अपलोड करें।",
        "ta": "இந்த படத்திலிருந்து எந்த உரையும் படிக்க முடியவில்லை. தயவுசெய்து உரை அடிப்படையிலான ஆய்வக அறிக்கையின் தெளிவான, நல்ல வெளிச்சம் உள்ள புகைப்படத்தை பதிவேற்றவும்.",
    },
    "Could not extract enough text from the image. Please upload a clearer photo of a text-based lab report.": {
        "en": "Could not extract enough text from the image. Please upload a clearer photo of a text-based lab report.",
        "hi": "छवि से पर्याप्त पाठ नहीं निकाला जा सका। कृपया टेक्स्ट-आधारित लैब रिपोर्ट की साफ़ फ़ोटो अपलोड करें।",
        "ta": "படத்திலிருந்து போதுமான உரையைப் பிரித்தெடுக்க முடியவில்லை. உரை அடிப்படையிலான ஆய்வக அறிக்கையின் தெளிவான புகைப்படத்தை பதிவேற்றவும்.",
    },
    "Could not extract enough lab test data from this document for analysis.": {
        "en": "Could not extract enough lab test data from this document for analysis.",
        "hi": "इस दस्तावेज़ से विश्लेषण हेतु पर्याप्त लैब परीक्षण डेटा नहीं निकाला जा सका।",
        "ta": "இந்த ஆவணத்திலிருந்து பகுப்பாய்விற்கு போதுமான ஆய்வக சோதனை தரவைப் பிரித்தெடுக்க முடியவில்லை.",
    },
    "We couldn't clearly read the test names and values from this document. Try a clearer, closer photo, or type the values using the 'Type your test values instead' option.": {
        "en": "We couldn't clearly read the test names and values from this document. Try a clearer, closer photo, or type the values using the 'Type your test values instead' option.",
        "hi": "हम इस दस्तावेज़ से परीक्षण के नाम और मान स्पष्ट रूप से नहीं पढ़ सके। साफ़ और नज़दीक से फ़ोटो लेकर कोशिश करें, या 'Type your test values instead' विकल्प का उपयोग करके मान लिखें।",
        "ta": "இந்த ஆவணத்திலிருந்து சோதனை பெயர்கள் மற்றும் மதிப்புகளை தெளிவாக படிக்க முடியவில்லை. தெளிவான, நெருக்கமான புகைப்படத்தை எடுத்து முயற்சிக்கவும், அல்லது 'Type your test values instead' விருப்பத்தை பயன்படுத்தி மதிப்புகளை தட்டச்சு செய்யவும்.",
    },
    "Not enough text was found. Please upload a clear photo of a full lab report page.": {
        "en": "Not enough text was found. Please upload a clear photo of a full lab report page.",
        "hi": "पर्याप्त पाठ नहीं मिला। कृपया पूरे लैब रिपोर्ट पृष्ठ की साफ़ फ़ोटो अपलोड करें।",
        "ta": "போதுமான உரை கிடைக்கவில்லை. முழு ஆய்வக அறிக்கை பக்கத்தின் தெளிவான புகைப்படத்தை பதிவேற்றவும்.",
    },
    "No lab test values were detected in this image. Please upload a clearer photo of a lab report that shows test names and numbers.": {
        "en": "No lab test values were detected in this image. Please upload a clearer photo of a lab report that shows test names and numbers.",
        "hi": "इस छवि में कोई लैब परीक्षण मान नहीं मिला। कृपया लैब रिपोर्ट की साफ़ फ़ोटो अपलोड करें जिसमें परीक्षण के नाम और संख्याएँ दिखें।",
        "ta": "இந்த படத்தில் ஆய்வக சோதனை மதிப்புகள் எதுவும் கண்டறியப்படவில்லை. சோதனை பெயர்கள் மற்றும் எண்களைக் காட்டும் ஆய்வக அறிக்கையின் தெளிவான புகைப்படத்தை பதிவேற்றவும்.",
    },
    "This does not look like a laboratory report. Please upload a photo of a real text-based lab result sheet — not random notes, homework, receipts, or other documents.": {
        "en": "This does not look like a laboratory report. Please upload a photo of a real text-based lab result sheet — not random notes, homework, receipts, or other documents.",
        "hi": "यह लैब रिपोर्ट जैसा नहीं दिखता। कृपया वास्तविक टेक्स्ट-आधारित लैब रिज़ल्ट शीट की फ़ोटो अपलोड करें — नोट्स, होमवर्क, रसीदें या अन्य दस्तावेज़ नहीं।",
        "ta": "இது ஆய்வக அறிக்கை போல் தெரியவில்லை. உண்மையான உரை அடிப்படையிலான ஆய்வக முடிவுத் தாளின் புகைப்படத்தைப் பதிவேற்றவும் — குறிப்புகள், வீட்டுப்பாடம், ரசீதுகள் அல்லது பிற ஆவணங்கள் அல்ல.",
    },
    "The text found does not appear to be from a medical lab report. MediBridge only analyzes laboratory result documents.": {
        "en": "The text found does not appear to be from a medical lab report. MediBridge only analyzes laboratory result documents.",
        "hi": "मिला पाठ चिकित्सा लैब रिपोर्ट से नहीं लगता। MediBridge केवल प्रयोगशाला परिणाम दस्तावेज़ों का विश्लेषण करता है।",
        "ta": "கண்டறியப்பட்ட உரை மருத்துவ ஆய்வக அறிக்கையில் இருந்து வந்தது போல் தெரியவில்லை. MediBridge ஆய்வக முடிவு ஆவணங்களை மட்டுமே பகுப்பாய்வு செய்கிறது.",
    },
    "This file appears to be a medical imaging scan (DICOM/NIfTI). MediBridge only supports text-based lab reports, not X-rays or MRIs.": {
        "en": "This file appears to be a medical imaging scan (DICOM/NIfTI). MediBridge only supports text-based lab reports, not X-rays or MRIs.",
        "hi": "यह फ़ाइल मेडिकल इमेजिंग स्कैन (DICOM/NIfTI) प्रतीत होती है। MediBridge केवल टेक्स्ट-आधारित लैब रिपोर्ट का समर्थन करता है, एक्स-रे या MRI का नहीं।",
        "ta": "இந்த கோப்பு மருத்துவ இமேஜிங் ஸ்கேன் (DICOM/NIfTI) போல் தெரிகிறது. MediBridge உரை அடிப்படையிலான ஆய்வக அறிக்கைகளை மட்டுமே ஆதரிக்கிறது, எக்ஸ்ரே அல்லது MRI அல்ல.",
    },
    "DICOM imaging files are not supported. Please upload a photo of a text-based lab report.": {
        "en": "DICOM imaging files are not supported. Please upload a photo of a text-based lab report.",
        "hi": "DICOM इमेजिंग फ़ाइलें समर्थित नहीं हैं। कृपया टेक्स्ट-आधारित लैब रिपोर्ट की फ़ोटो अपलोड करें।",
        "ta": "DICOM இமேஜிங் கோப்புகள் ஆதரிக்கப்படாது. உரை அடிப்படையிலான ஆய்வக அறிக்கையின் புகைப்படத்தை பதிவேற்றவும்.",
    },
    "File metadata suggests this is an X-ray, MRI, or CT scan. Please upload a text-based laboratory report instead.": {
        "en": "File metadata suggests this is an X-ray, MRI, or CT scan. Please upload a text-based laboratory report instead.",
        "hi": "फ़ाइल मेटाडेटा इंगित करता है कि यह एक्स-रे, MRI या CT स्कैन है। कृपया इसके स्थान पर टेक्स्ट-आधारित प्रयोगशाला रिपोर्ट अपलोड करें।",
        "ta": "கோப்பு மெட்டாடேட்டா இது எக்ஸ்ரே, MRI அல்லது CT ஸ்கேன் எனக் குறிக்கிறது. அதற்குப் பதிலாக உரை அடிப்படையிலான ஆய்வக அறிக்கையைப் பதிவேற்றவும்.",
    },
    "Only image uploads are supported. Please upload a photo of your lab report.": {
        "en": "Only image uploads are supported. Please upload a photo of your lab report.",
        "hi": "केवल छवि अपलोड समर्थित हैं। कृपया अपनी लैब रिपोर्ट की फ़ोटो अपलोड करें।",
        "ta": "படப் பதிவேற்றங்கள் மட்டுமே ஆதரிக்கப்படும். உங்கள் ஆய்வக அறிக்கையின் புகைப்படத்தை பதிவேற்றவும்.",
    },
}


def _localize_error(message: str, lang: _LANG) -> str:
    """Return the localized version of a known user-facing error message."""
    if lang == "en":
        return message
    translated = _ERROR_L10N.get(message.strip())
    if translated:
        return translated.get(lang, message)

    if message.startswith("This upload appears to be a medical imaging file"):
        localized = {
            "hi": (
                "यह अपलोड मेडिकल इमेजिंग फ़ाइल प्रतीत होती है। "
                "MediBridge केवल टेक्स्ट-आधारित लैब रिपोर्ट शीट का विश्लेषण करता है, एक्स-रे या MRI का नहीं।"
            ),
            "ta": (
                "இந்த பதிவேற்றம் மருத்துவ இமேஜிங் கோப்பு போல் தெரிகிறது. "
                "MediBridge உரை அடிப்படையிலான ஆய்வக முடிவுத் தாள்களை மட்டுமே பகுப்பாய்வு செய்கிறது, எக்ஸ்ரே அல்லது MRI அல்ல."
            ),
        }
        return localized.get(lang, message)

    return message

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "MediBridge helps patients understand lab results with OCR, "
        "PII-safe AI simplification, and doctor visit preparation questions."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    ai_provider: str
    ocr_available: bool


class AnalyzeResponse(BaseModel):
    language: str
    emergency_trigger: bool
    report_summary: str
    simplified_terms: list[dict]
    numerical_context: list[dict]
    doctor_questions: list[str] = Field(min_length=3, max_length=3)
    next_steps: list[str]
    ocr_preview: str = Field(description="First 200 chars of scrubbed OCR text for transparency")


class PrescriptionResponse(BaseModel):
    language: str
    medicines: list[dict]
    pharmacist_questions: list[str] = Field(min_length=3, max_length=3)
    ocr_preview: str = Field(description="First 200 chars of scrubbed OCR text for transparency")


@app.get("/", tags=["System"])
async def root() -> dict:
    return {
        "message": "MediBridge API is running.",
        "web_app": "Open http://localhost:5173 (run frontend: npm run dev in frontend folder).",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        ai_provider=settings.ai_provider,
        ocr_available=is_tesseract_available(),
    )


@app.post("/api/analyze", response_model=AnalyzeResponse, tags=["Analysis"])
async def analyze_lab_report(
    file: Annotated[UploadFile, File(description="Lab report image (JPEG, PNG, WebP, or PDF page as image)")],
    lang: Annotated[
        Literal["en", "hi", "ta"],
        Query(description="Output language: en (English), hi (Hindi), ta (Tamil)"),
    ] = "en",
) -> AnalyzeResponse:
    if lang not in settings.supported_languages:
        raise HTTPException(status_code=400, detail=f"Unsupported language '{lang}'. Use en, hi, or ta.")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail=_localize_error(
                "Only image uploads are supported. Please upload a photo of your lab report.",
                lang,
            ),
        )

    raw_bytes = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(raw_bytes) > max_bytes:
        size_msg = {
            "en": f"File too large. Maximum size is {settings.max_upload_size_mb} MB.",
            "hi": f"फ़ाइल बहुत बड़ी है। अधिकतम आकार {settings.max_upload_size_mb} MB है।",
            "ta": f"கோப்பு மிகப்பெரியது. அதிகபட்ச அளவு {settings.max_upload_size_mb} MB.",
        }
        raise HTTPException(
            status_code=413,
            detail=size_msg.get(lang, size_msg["en"]),
        )

    filename = file.filename or "upload.jpg"
    content_type = file.content_type or "application/octet-stream"

    try:
        reject_imaging_document(filename=filename, content_type=content_type, raw_bytes=raw_bytes)
    except SafetyFilterError as exc:
        raise HTTPException(status_code=422, detail=_localize_error(str(exc), lang)) from exc

    try:
        ocr_text = await extract_text_from_image(raw_bytes)
    except OCRError as exc:
        raise HTTPException(status_code=422, detail=_localize_error(str(exc), lang)) from exc
    except Exception as exc:
        logger.exception("OCR extraction failed")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {exc}") from exc

    if not ocr_text or len(ocr_text.strip()) < 10:
        raise HTTPException(
            status_code=422,
            detail=_localize_error(
                "Could not extract enough text from the image. Please upload a clearer photo of a text-based lab report.",
                lang,
            ),
        )

    scrubbed_text = scrub_pii(ocr_text)

    try:
        validate_lab_report_text(scrubbed_text)
    except SafetyFilterError as exc:
        raise HTTPException(status_code=422, detail=_localize_error(str(exc), lang)) from exc

    clinical_text = filter_clinical_text(scrubbed_text)

    try:
        result: UIPAnalysisResult = await analyze_lab_text(clinical_text, language=lang)
    except SafetyFilterError as exc:
        raise HTTPException(status_code=422, detail=_localize_error(str(exc), lang)) from exc
    except Exception as exc:
        logger.exception("AI analysis failed")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc

    return AnalyzeResponse(
        language=lang,
        emergency_trigger=result.emergency_trigger,
        report_summary=result.report_summary,
        simplified_terms=[term.model_dump() for term in result.simplified_terms],
        numerical_context=[metric.model_dump() for metric in result.numerical_context],
        doctor_questions=result.doctor_questions,
        next_steps=result.next_steps,
        ocr_preview=clinical_text[:200],
    )


@app.post("/api/analyze-prescription", response_model=PrescriptionResponse, tags=["Prescription"])
async def analyze_prescription_image(
    file: Annotated[UploadFile, File(description="Prescription image (JPEG, PNG, or WebP)")],
    lang: Annotated[
        Literal["en", "hi", "ta"],
        Query(description="Output language: en (English), hi (Hindi), ta (Tamil)"),
    ] = "en",
) -> PrescriptionResponse:
    if lang not in settings.supported_languages:
        raise HTTPException(status_code=400, detail=f"Unsupported language '{lang}'. Use en, hi, or ta.")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail=_localize_error(
                "Only image uploads are supported. Please upload a photo of your lab report.",
                lang,
            ),
        )

    raw_bytes = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(raw_bytes) > max_bytes:
        size_msg = {
            "en": f"File too large. Maximum size is {settings.max_upload_size_mb} MB.",
            "hi": f"फ़ाइल बहुत बड़ी है। अधिकतम आकार {settings.max_upload_size_mb} MB है।",
            "ta": f"கோப்பு மிகப்பெரியது. அதிகபட்ச அளவு {settings.max_upload_size_mb} MB.",
        }
        raise HTTPException(
            status_code=413,
            detail=size_msg.get(lang, size_msg["en"]),
        )

    try:
        ocr_text = await extract_text_from_image(raw_bytes)
    except OCRError as exc:
        raise HTTPException(status_code=422, detail=_localize_error(str(exc), lang)) from exc
    except Exception as exc:
        logger.exception("OCR extraction failed")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {exc}") from exc

    if not ocr_text or len(ocr_text.strip()) < 10:
        raise HTTPException(
            status_code=422,
            detail=_localize_error(
                "Could not extract enough text from the image. Please upload a clearer photo of a text-based lab report.",
                lang,
            ),
        )

    scrubbed_text = scrub_pii(ocr_text)
    result = analyze_prescription(scrubbed_text, language=lang)

    if not result["medicines"]:
        no_meds = {
            "en": (
                "We couldn't clearly read the medicine names — this usually happens with blurry photos "
                "or handwritten prescriptions. Try a sharper, closer photo, or type the medicine names here "
                "so we can still help."
            ),
            "hi": (
                "हम दवाइयों के नाम स्पष्ट रूप से नहीं पढ़ पाए — यह आमतौर पर धुंधली फ़ोटो या हस्तलिखित पर्ची के कारण होता है। "
                "साफ़ और नज़दीक की फ़ोटो लें, या दवाइयों के नाम यहाँ लिखें ताकि हम फिर भी मदद कर सकें।"
            ),
            "ta": (
                "மருந்து பெயர்களை தெளிவாக படிக்க முடியவில்லை — இது பொதுவாக மங்கலான புகைப்படம் அல்லது கையெழுத்து "
                "மருந்து பரிந்துரையால் ஏற்படும். தெளிவான, நெருக்கமான புகைப்படம் எடுக்கவும், அல்லது மருந்து பெயர்களை "
                "இங்கே தட்டச்சு செய்யவும்."
            ),
        }
        raise HTTPException(status_code=422, detail=(no_meds.get(lang, no_meds["en"])))

    return PrescriptionResponse(
        language=lang,
        medicines=result["medicines"],
        pharmacist_questions=result["pharmacist_questions"],
        ocr_preview=scrubbed_text[:200],
    )


class PrescriptionTextRequest(BaseModel):
    text: str = Field(description="Medicine names typed by the user (one per line or comma separated)")


@app.post("/api/analyze-prescription-text", response_model=PrescriptionResponse, tags=["Prescription"])
async def analyze_prescription_typed(
    payload: PrescriptionTextRequest,
    lang: Annotated[
        Literal["en", "hi", "ta"],
        Query(description="Output language: en (English), hi (Hindi), ta (Tamil)"),
    ] = "en",
) -> PrescriptionResponse:
    if lang not in settings.supported_languages:
        raise HTTPException(status_code=400, detail=f"Unsupported language '{lang}'. Use en, hi, or ta.")

    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="No medicine names were entered.")

    scrubbed_text = scrub_pii(text)
    result = analyze_prescription(scrubbed_text, language=lang)

    if not result["medicines"]:
        no_meds = {
            "en": "No medicine names were recognized. Please check the spelling and try again.",
            "hi": "कोई दवा का नाम पहचाना नहीं गया। कृपया वर्तनी जाँच कर फिर से प्रयास करें।",
            "ta": "எந்த மருந்து பெயரும் அடையாளம் காணப்படவில்லை. எழுத்துப்பிழையைச் சரிபார்த்து மீண்டும் முயற்சிக்கவும்.",
        }
        raise HTTPException(status_code=422, detail=no_meds.get(lang, no_meds["en"]))

    return PrescriptionResponse(
        language=lang,
        medicines=result["medicines"],
        pharmacist_questions=result["pharmacist_questions"],
        ocr_preview=scrubbed_text[:200],
    )


class LabTextRequest(BaseModel):
    text: str = Field(description="Lab report values typed by the user (one per line or comma separated)")


@app.post("/api/analyze-lab-text", response_model=AnalyzeResponse, tags=["Lab Report"])
async def analyze_lab_typed(
    payload: LabTextRequest,
    lang: Annotated[
        Literal["en", "hi", "ta"],
        Query(description="Output language: en (English), hi (Hindi), ta (Tamil)"),
    ] = "en",
) -> AnalyzeResponse:
    if lang not in settings.supported_languages:
        raise HTTPException(status_code=400, detail=f"Unsupported language '{lang}'. Use en, hi, or ta.")

    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="No lab values were entered.")

    scrubbed_text = scrub_pii(text)
    clinical_text = filter_clinical_text(scrubbed_text)

    try:
        result: UIPAnalysisResult = await analyze_lab_text(clinical_text, language=lang)
    except SafetyFilterError as exc:
        raise HTTPException(status_code=422, detail=_localize_error(str(exc), lang)) from exc
    except Exception as exc:
        logger.exception("AI analysis failed")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc

    if not result.numerical_context:
        no_vals = {
            "en": "No recognized test values were found. Type them like: Hemoglobin 11.2 (Ref: 12-16), Platelets 180 (Ref: 150-410).",
            "hi": "कोई पहचाना गया टेस्ट मान नहीं मिला। ऐसे लिखें: Hemoglobin 11.2 (Ref: 12-16), Platelets 180 (Ref: 150-410)।",
            "ta": "எந்த அங்கீகரிக்கப்பட்ட சோதனை மதிப்பும் காணப்படவில்லை. இவ்வாறு தட்டச்சு செய்யவும்: Hemoglobin 11.2 (Ref: 12-16), Platelets 180 (Ref: 150-410).",
        }
        raise HTTPException(status_code=422, detail=no_vals.get(lang, no_vals["en"]))

    return AnalyzeResponse(
        language=lang,
        emergency_trigger=result.emergency_trigger,
        report_summary=result.report_summary,
        simplified_terms=[term.model_dump() for term in result.simplified_terms],
        numerical_context=[metric.model_dump() for metric in result.numerical_context],
        doctor_questions=result.doctor_questions,
        next_steps=result.next_steps,
        ocr_preview=scrubbed_text[:200],
    )


class AuthRequest(BaseModel):
    email: str = Field(description="User email")
    password: str = Field(description="Password (min 6 characters)")


class AuthResponse(BaseModel):
    token: str
    email: str


class SaveReportRequest(BaseModel):
    kind: Literal["lab", "prescription"] = "lab"
    language: Literal["en", "hi", "ta"] = "en"
    analysis: dict = Field(description="The full analysis/prescription response JSON")


class HistoryItem(BaseModel):
    id: int
    kind: str
    language: str
    summary: str
    created_at: str


class HistoryResponse(BaseModel):
    reports: list[HistoryItem]


class HistoryDetailResponse(BaseModel):
    report: dict
    previous: Optional[dict] = None


def _auth_user(authorization: str) -> Optional[dict]:
    """Resolve a `Bearer <token>` header to a user, or None."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None
    return get_user_by_token(token)


def _require_authed_user(authorization: str) -> dict:
    user = _auth_user(authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in. Please log in.")
    return user


@app.post("/api/auth/signup", response_model=AuthResponse, tags=["Account"])
async def signup(payload: AuthRequest) -> AuthResponse:
    try:
        user = create_user(payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if user is None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    token = create_session(user["id"])
    return AuthResponse(token=token, email=user["email"])


@app.post("/api/auth/login", response_model=AuthResponse, tags=["Account"])
async def login(payload: AuthRequest) -> AuthResponse:
    user = verify_user(payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    token = create_session(user["id"])
    return AuthResponse(token=token, email=user["email"])


@app.post("/api/auth/logout", tags=["Account"])
async def logout(authorization: Annotated[str, Header()] = "") -> dict:
    user = _auth_user(authorization)
    if user is not None:
        token = authorization.split(" ", 1)[1].strip()
        delete_session(token)
    return {"status": "ok"}


@app.post("/api/history", response_model=HistoryResponse, tags=["History"])
async def history_list(
    authorization: Annotated[str, Header()] = "",
) -> HistoryResponse:
    user = _require_authed_user(authorization)
    items = [HistoryItem(**row) for row in list_reports(user["id"])]
    return HistoryResponse(reports=items)


@app.post("/api/history/save", response_model=HistoryItem, tags=["History"])
async def history_save(
    payload: SaveReportRequest,
    authorization: Annotated[str, Header()] = "",
) -> HistoryItem:
    user = _require_authed_user(authorization)
    report_id = add_report(user["id"], payload.kind, payload.language, payload.analysis)
    row = {**{"id": report_id, "kind": payload.kind, "language": payload.language},
           **{"summary": payload.analysis.get("report_summary", "") or "Report",
              "created_at": ""}}
    # Fetch canonical row back so created_at matches what the client sees.
    stored = get_report(user["id"], report_id) or {
        "id": report_id,
        "kind": payload.kind,
        "language": payload.language,
        "summary": row["summary"],
        "created_at": "",
    }
    return HistoryItem(
        id=stored["id"],
        kind=stored["kind"],
        language=stored["language"],
        summary=stored.get("summary", ""),
        created_at=stored.get("created_at", ""),
    )


@app.post("/api/history/{report_id}", response_model=HistoryDetailResponse, tags=["History"])
async def history_detail(
    report_id: int,
    authorization: Annotated[str, Header()] = "",
) -> HistoryDetailResponse:
    user = _require_authed_user(authorization)
    report = get_report(user["id"], report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    previous = get_previous_report(user["id"], report_id, report["kind"])
    return HistoryDetailResponse(
        report={"kind": report["kind"], "language": report["language"], "analysis": report["analysis"]},
        previous={"kind": previous["kind"], "language": previous["language"], "analysis": previous["analysis"]}
        if previous
        else None,
    )
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.debug)


class TTSRequest(BaseModel):
    text: str = Field(description="The section text to read aloud")
    language: Literal["en", "hi", "ta"] = "en"


@app.post(
    "/api/tts",
    tags=["Speech"],
    summary="Neural text-to-speech (edge-tts)",
    description=(
        "Synthesize a section of the analysis into professional MP3 audio using "
        "Microsoft Edge neural voices (en-IN / hi-IN / ta-IN). Audio is cached "
        "on disk, so repeating the same section is instant."
    ),
)
async def text_to_speech(payload: TTSRequest) -> FileResponse:
    if payload.language not in settings.supported_languages:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language '{payload.language}'. Use en, hi, or ta.",
        )
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="No text was provided to speak.")

    try:
        mp3_path = await synthesize_speech(payload.text, payload.language)
    except TTSUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("TTS synthesis failed")
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {exc}") from exc

    return FileResponse(mp3_path, media_type="audio/mpeg")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.debug)
