from __future__ import annotations

import re
from typing import Final

IMAGING_KEYWORDS: Final[tuple[str, ...]] = (
    "x-ray",
    "xray",
    "x ray",
    "mri",
    "magnetic resonance",
    "ct scan",
    "computed tomography",
    "radiograph",
    "fluoroscopy",
    "ultrasound image",
    "pet scan",
    "mammogram image",
    "dicom",
)

IMAGING_EXTENSIONS: Final[tuple[str, ...]] = (
    ".dcm",
    ".dicom",
    ".nii",
    ".nifti",
)

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    re.IGNORECASE,
)

PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)|\d{2,4})[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)",
)

SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

DATE_OF_BIRTH_PATTERN = re.compile(
    r"(?:DOB|Date of Birth|Birth Date)[:\s]*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
    re.IGNORECASE,
)

PATIENT_NAME_PATTERN = re.compile(
    r"(?:Patient(?:\s+Name)?|Name)[:\t ]+([A-Z][a-z]+)"
    r"(?:[ \t]+(?!(?:Age|Sex|Gender|Date|DOB|Weight|Height|UHID|MRN|Mobile|Phone|Address)\b)[A-Z][a-z]+)*",
    re.IGNORECASE,
)

MRN_PATTERN = re.compile(
    r"(?:MRN|Medical Record|Patient ID|Account #?)[:\s#]*[\w-]+",
    re.IGNORECASE,
)

ADDRESS_PATTERN = re.compile(
    r"\b\d{1,5}\s+[A-Za-z0-9 ,.&/-]+"
    r"(?:Street|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Boulevard|Blvd|Court|Circle)\b(?=,|\.|$)",
    re.IGNORECASE,
)

LAB_REPORT_KEYWORDS: Final[tuple[str, ...]] = (
    "lab",
    "laboratory",
    "report",
    "result",
    "results",
    "test",
    "panel",
    "specimen",
    "reference",
    "normal range",
    "ref range",
    "hemoglobin",
    "hgb",
    "hb",
    "glucose",
    "cholesterol",
    "creatinine",
    "wbc",
    "rbc",
    "platelet",
    "cbc",
    "metabolic",
    "lipid",
    "thyroid",
    "tsh",
    "alt",
    "ast",
    "bun",
    "electrolyte",
    "sodium",
    "potassium",
    "mg/dl",
    "g/dl",
    "mmol/l",
    "u/l",
    "units/l",
    "pathology",
    "diagnostic",
)

LAB_VALUE_PATTERN = re.compile(
    r"(?:^|\n)\s*([A-Za-z][A-Za-z0-9\s()/-]{2,90}?)\s*[:=]\s*"
    r"([\d.]+\s*(?:mg/dL|g/dL|mmol/L|U/L|u/L|/L|/dL|/uL|x10[\^]?\d+/uL|%|pg|fL|mEq/L|K/uL|M/uL)?)",
    re.IGNORECASE | re.MULTILINE,
)

# Column-layout lab sheets print "Metric  value  unit  ref-range" with no
# colon/equals between name and value (the most common real-world layout).
# Count those value tokens separately, with a unit required so junk text
# (phone numbers, prices, dates) cannot satisfy the lab-value check.
COLUMN_VALUE_PATTERN = re.compile(
    r"(?:^|\n)\s*[A-Za-z][A-Za-z0-9\s()/-]{2,90}?\s+"
    r"((?:[<>])?\s*\d[\d.,]*\s*(?:mg/dL|g/dL|mmol/L|U/L|u/L|ulU/mL|U/mL|/L|/dL|/uL|"
    r"x10[\^]?\d?/uL|%|pg|fL|mEq/L|million/uL|million/cumm|lakh/cumm|cumm|units/L))",
    re.IGNORECASE | re.MULTILINE,
)

REFERENCE_RANGE_PATTERN = re.compile(
    r"(?:reference|ref\.?|normal)\s*[:=]?\s*([<>]?\s*[\d.]+\s*[-–—]\s*[\d.]+\s*(?:\w+)?|[<>]?\s*[\d.]+\s*(?:\w+)?)",
    re.IGNORECASE,
)


class SafetyFilterError(Exception):
    """Raised when uploaded content fails safety or compliance checks."""


def reject_imaging_document(filename: str, content_type: str, raw_bytes: bytes) -> None:
    lowered_name = filename.lower()
    for ext in IMAGING_EXTENSIONS:
        if lowered_name.endswith(ext):
            raise SafetyFilterError(
                "This file appears to be a medical imaging scan (DICOM/NIfTI). "
                "MediBridge only supports text-based lab reports, not X-rays or MRIs."
            )

    if content_type in ("application/dicom", "application/x-dicom"):
        raise SafetyFilterError(
            "DICOM imaging files are not supported. Please upload a photo of a text-based lab report."
        )

    for keyword in IMAGING_KEYWORDS:
        if keyword in lowered_name:
            raise SafetyFilterError(
                f"This upload appears to be a medical imaging file ('{keyword}'). "
                "MediBridge only processes text-based lab result sheets, not X-rays or MRIs."
            )

    # Only scan raw bytes for imaging markers when the payload is NOT a real
    # image. Compressed image bytes (PNG/JPEG/WebP) randomly decode into ASCII
    # fragments that falsely match keywords like "mri", causing valid lab-report
    # photos to be rejected. DICOM/NIfTI and raw text payloads never claim an
    # image/* content type, so they are the ones worth scanning.
    if not (content_type and content_type.lower().startswith("image/")):
        try:
            header_sample = raw_bytes[:8192].decode("utf-8", errors="ignore").lower()
        except Exception:
            header_sample = ""

        for keyword in IMAGING_KEYWORDS:
            if keyword in header_sample:
                raise SafetyFilterError(
                    "File metadata suggests this is an X-ray, MRI, or CT scan. "
                    "Please upload a text-based laboratory report instead."
                )


def scrub_pii(text: str) -> str:
    if not text:
        return text

    scrubbed = text

    scrubbed = EMAIL_PATTERN.sub("[EMAIL_REDACTED]", scrubbed)
    scrubbed = PHONE_PATTERN.sub("[PHONE_REDACTED]", scrubbed)
    scrubbed = SSN_PATTERN.sub("[SSN_REDACTED]", scrubbed)
    scrubbed = DATE_OF_BIRTH_PATTERN.sub("DOB: [DATE_REDACTED]", scrubbed)
    scrubbed = PATIENT_NAME_PATTERN.sub("Patient Name: [NAME_REDACTED]", scrubbed)
    scrubbed = MRN_PATTERN.sub(lambda m: re.sub(r"[\w-]+$", "[ID_REDACTED]", m.group(0)), scrubbed)
    scrubbed = ADDRESS_PATTERN.sub("[ADDRESS_REDACTED]", scrubbed)

    scrubbed = re.sub(
        r"(?:Dr\.|Doctor)[ \t]+[A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+)?",
        "Dr. [NAME_REDACTED]",
        scrubbed,
    )

    return scrubbed


def validate_lab_report_text(text: str) -> None:
    """Reject uploads whose OCR text does not resemble a laboratory report."""
    if not text or len(text.strip()) < 20:
        raise SafetyFilterError(
            "Not enough text was found. Please upload a clear photo of a full lab report page."
        )

    lowered = text.lower()
    keyword_hits = sum(1 for keyword in LAB_REPORT_KEYWORDS if keyword in lowered)

    lab_values = LAB_VALUE_PATTERN.findall(text)
    column_values = COLUMN_VALUE_PATTERN.findall(text)
    value_hits = len(lab_values) + len(column_values)
    numeric_lines = re.findall(
        r"[:=]\s*[\d.]+\s*(?:mg/dL|g/dL|mmol/L|U/L|/dL|/uL|%)",
        text,
        re.IGNORECASE,
    )

    has_report_context = any(
        token in lowered
        for token in ("lab", "laboratory", "report", "result", "pathology", "diagnostic", "panel")
    )

    if keyword_hits < 2:
        raise SafetyFilterError(
            "This does not look like a laboratory report. "
            "Please upload a photo of a real text-based lab result sheet — "
            "not random notes, homework, receipts, or other documents."
        )

    if value_hits < 2 and len(numeric_lines) < 2:
        raise SafetyFilterError(
            "No lab test values were detected in this image. "
            "Please upload a clearer photo of a lab report that shows test names and numbers."
        )

    if not has_report_context and value_hits < 3:
        raise SafetyFilterError(
            "The text found does not appear to be from a medical lab report. "
            "MediBridge only analyzes laboratory result documents."
        )
