/**
 * Localized metric names so the TTS (and optionally the UI) can speak
 * biomarker names in the user's native language rather than always English.
 *
 * Three maps per language:
 *   METRIC_NAMES    – full native script (Hindi Devanagari / Tamil script)
 *                     used in UI display and when a script-capable TTS voice exists
 *   METRIC_ROMAN    – phonetic Latin spelling, used in speech when NO
 *                     script-capable voice is available (e.g. Windows Tamil
 *                     with only an English voice)
 */

const METRIC_ROMAN = {
  hi: {
    "Hemoglobin (Hb)": "Heemoglobbin",
    "Red Blood Cells (RBC)": "Laal rakt koshikaein",
    "Packed Cell Volume (PCV)": "Packed Cell Volume",
    "Mean Corpuscular Volume (MCV)": "Ausat koshika aayatan",
    "Mean Corpuscular Hemoglobin (MCH)": "Ausat koshika heemoglobbin",
    "Mean Corpuscular Hemoglobin Concentration (MCHC)": "Ausat koshika heemoglobbin saandraa",
    "Red Cell Distribution Width (RDW)": "Laal koshika vitaran chaudaaee",
    "White Blood Cells (WBC)": "Shwet rakt koshikaein",
    "Platelets": "Platelets",
    "Mean Platelet Volume (MPV)": "Ausat platelet aayatan",
    "Platelet Distribution Width (PDW)": "Platelet vitaran chaudaaee",
    "Neutrophils": "Neutrophils",
    "Lymphocytes": "Lymphocytes",
    "Monocytes": "Monocytes",
    "Eosinophils": "Eosinophils",
    "Basophils": "Basophils",
    "Glucose (Fasting)": "Glucose upvaas",
    "Glucose (Postprandial)": "Glucose bhojan ke baad",
    "Glucose": "Glucose",
    "HbA1c": "Glycated Heemoglobbin",
    "Total Cholesterol": "Kul cholesterol",
    "LDL Cholesterol": "Kharab cholesterol",
    "HDL Cholesterol": "Achchha cholesterol",
    "Triglycerides": "Triglycerides",
    "Creatinine": "Creatinine",
    "BUN": "Blood Urea Nitrogen",
    "Uric Acid": "Uric Acid",
    "TSH": "Thyroid Uttejak Hormone",
    "Bilirubin (Total)": "Bilirubin kul",
    "Total Protein": "Kul protein",
    "Albumin": "Albumin",
    "Calcium": "Calcium",
    "Sodium": "Sodium",
    "Potassium": "Potassium",
    "Chloride": "Chloride",
    "Plateletcrit (PCT)": "Platelet Crit",
    "Iron": "Iron",
    "Vitamin D": "Vitamin D",
  },
  ta: {
    "Hemoglobin (Hb)": "Heemoglobbin",
    "Red Blood Cells (RBC)": "Sivappu iraththu anukkal",
    "Packed Cell Volume (PCV)": "Pack Cell Alavu",
    "Mean Corpuscular Volume (MCV)": "Saraasari Corpuscular Alavu",
    "Mean Corpuscular Hemoglobin (MCH)": "Saraasari Corpuscular Heemoglobbin",
    "Mean Corpuscular Hemoglobin Concentration (MCHC)": "Saraasari Corpuscular Heemoglobbin Serivu",
    "Red Cell Distribution Width (RDW)": "Sivappu Sel Vinaiyaga Agalam",
    "White Blood Cells (WBC)": "Vellai iraththu anukkal",
    "Platelets": "Thattu anukkal",
    "Mean Platelet Volume (MPV)": "Saraasari Thattu Alavu",
    "Platelet Distribution Width (PDW)": "Thattu Vinaiyaga Agalam",
    "Neutrophils": "Neutrophils",
    "Lymphocytes": "Lymphocytes",
    "Monocytes": "Monocytes",
    "Eosinophils": "Eosinophils",
    "Basophils": "Basophils",
    "Glucose (Fasting)": "Glucose nonbu",
    "Glucose (Postprandial)": "Glucose unavukku pinbu",
    "Glucose": "Glucose",
    "HbA1c": "Glycated Heemoglobbin",
    "Total Cholesterol": "Motha Colsterol",
    "LDL Cholesterol": "Mosamana Colsterol",
    "HDL Cholesterol": "Nalla Colsterol",
    "Triglycerides": "Triglycerides",
    "Creatinine": "Creatinine",
    "BUN": "Iraththu Urea Nitrogen",
    "Uric Acid": "Uric Acid",
    "TSH": "Thyroid Ukkirippu Hormone",
    "Bilirubin (Total)": "Bilirubin motham",
    "Total Protein": "Motha protein",
    "Albumin": "Albumin",
    "Calcium": "Calcium",
    "Sodium": "Sodium",
    "Potassium": "Potassium",
    "Chloride": "Chloride",
    "Plateletcrit (PCT)": "Thattu Crit",
    "Iron": "Iron",
    "Vitamin D": "Vitamin D",
  },
  en: {},
};

const METRIC_NAMES = {
  hi: {
    "Hemoglobin (Hb)": "हीमोग्लोबिन",
    "Red Blood Cells (RBC)": "लाल रक्त कोशिकाएं",
    "Packed Cell Volume (PCV)": "पैक्ड सेल वॉल्यूम",
    "Mean Corpuscular Volume (MCV)": "औसत कोशिका आयतन",
    "Mean Corpuscular Hemoglobin (MCH)": "औसत कोशिका हीमोग्लोबिन",
    "Mean Corpuscular Hemoglobin Concentration (MCHC)": "औसत कोशिका हीमोग्लोबिन सांद्रता",
    "Red Cell Distribution Width (RDW)": "लाल कोशिका वितरण चौड़ाई",
    "White Blood Cells (WBC)": "श्वेत रक्त कोशिकाएं",
    "Platelets": "प्लेटलेट्स",
    "Mean Platelet Volume (MPV)": "औसत प्लेटलेट आयतन",
    "Platelet Distribution Width (PDW)": "प्लेटलेट वितरण चौड़ाई",
    "Neutrophils": "न्यूट्रोफिल",
    "Lymphocytes": "लिम्फोसाइट्स",
    "Monocytes": "मोनोसाइट्स",
    "Eosinophils": "इओसिनोफिल्स",
    "Basophils": "बेसोफिल्स",
    "Glucose (Fasting)": "ग्लूकोज़ उपवास",
    "Glucose (Postprandial)": "ग्लूकोज़ भोजन के बाद",
    "Glucose": "ग्लूकोज़",
    "HbA1c": "ग्लाइकेटेड हीमोग्लोबिन",
    "Total Cholesterol": "कुल कोलेस्ट्रॉल",
    "LDL Cholesterol": "खराब कोलेस्ट्रॉल",
    "HDL Cholesterol": "अच्छा कोलेस्ट्रॉल",
    "Triglycerides": "ट्राइग्लिसराइड्स",
    "Creatinine": "क्रिएटिनिन",
    "BUN": "ब्लड यूरिया नाइट्रोजन",
    "Uric Acid": "यूरिक एसिड",
    "TSH": "थायरॉइड उत्तेजक हार्मोन",
    "Bilirubin (Total)": "बिलीरुबिन कुल",
    "Total Protein": "कुल प्रोटीन",
    "Albumin": "एल्ब्यूमिन",
    "Calcium": "कैल्शियम",
    "Sodium": "सोडियम",
    "Potassium": "पोटेशियम",
    "Chloride": "क्लोराइड",
    "Plateletcrit (PCT)": "प्लेटलेट क्रिट",
    "Iron": "आयरन",
    "Vitamin D": "विटामिन डी",
    "TIBC": "कुल आयरन बाइंडिंग क्षमता",
    "Transferrin Saturation": "ट्रांसफ़रिन संतृप्ति",
    "ESR": "रक्त अवसादन दर",
    "CRP": "सी-रिएक्टिव प्रोटीन",
    "PSA": "प्रोस्टेट विशिष्ट एंटीजन",
  },
  ta: {
    "Hemoglobin (Hb)": "ஹீமோகுளோபின்",
    "Red Blood Cells (RBC)": "சிவப்பு இரத்த அணுக்கள்",
    "Packed Cell Volume (PCV)": "செல் பேக் அளவு",
    "Mean Corpuscular Volume (MCV)": "சராசரி கோர்பஸ்குலர் அளவு",
    "Mean Corpuscular Hemoglobin (MCH)": "சராசரி கோர்பஸ்குலர் ஹீமோகுளோபின்",
    "Mean Corpuscular Hemoglobin Concentration (MCHC)": "சராசரி கோர்பஸ்குலர் ஹீமோகுளோபின் செறிவு",
    "Red Cell Distribution Width (RDW)": "சிவப்பு செல் விநியோக அகலம்",
    "White Blood Cells (WBC)": "வெள்ளை இரத்த அணுக்கள்",
    "Platelets": "தட்டு அணுக்கள்",
    "Mean Platelet Volume (MPV)": "சராசரி தட்டு அளவு",
    "Platelet Distribution Width (PDW)": "தட்டு விநியோக அகலம்",
    "Neutrophils": "நியூட்ரோஃபில்",
    "Lymphocytes": "லிம்ஃபோசைட்டுகள்",
    "Monocytes": "மோனோசைட்டுகள்",
    "Eosinophils": "ஈசினோஃபில்",
    "Basophils": "பேசோஃபில்",
    "Glucose (Fasting)": "குளுக்கோஸ் நோன்பு",
    "Glucose (Postprandial)": "குளுக்கோஸ் உணவுக்குப் பிறகு",
    "Glucose": "குளுக்கோஸ்",
    "HbA1c": "கிளைகேட்டட் ஹீமோகுளோபின்",
    "Total Cholesterol": "மொத்த கொலஸ்ட்ரால்",
    "LDL Cholesterol": "மோசமான கொலஸ்ட்ரால்",
    "HDL Cholesterol": "நல்ல கொலஸ்ட்ரால்",
    "Triglycerides": "ட்ரைகிளிசரைடுகள்",
    "Creatinine": "கிரியாட்டினின்",
    "BUN": "இரத்த யூரியா நைட்ரஜன்",
    "Uric Acid": "யூரிக் அமிலம்",
    "TSH": "தைராய்டு ஊக்குவிப்பான்",
    "Bilirubin (Total)": "பிலிருபின் மொத்தம்",
    "Total Protein": "மொத்த புரதம்",
    "Albumin": "ஆல்புமின்",
    "Calcium": "கல்சியம்",
    "Sodium": "சோடியம்",
    "Potassium": "பொட்டாசியம்",
    "Chloride": "குளோரைடு",
    "Plateletcrit (PCT)": "தட்டு குரிட்",
    "Iron": "இரும்பு",
    "Vitamin D": "வைட்டமின் டி",
    "TIBC": "மொத்த இரும்பு பிணைப்பு திறன்",
    "Transferrin Saturation": "ட்ரான்ஸ்ஃபெரின் நிறைவு",
    "ESR": "இரத்த படிவு வேகம்",
    "CRP": "சி-ரியாக்டிவ் புரதம்",
    "PSA": "புரோஸ்டேட் சிறப்பு எதிர்ப்பொருள்",
  },
  en: {},
};

/**
 * Return the best metric name for speech / display.
 * @param {string} metricCanonical  – the canonical English metric name
 * @param {string} language         – "en" | "hi" | "ta"
 * @param {boolean} romanize        – if true, prefer Latin-phonetic form
 *                                    (for TTS when no script voice exists)
 */
export function localizedMetric(metricCanonical, language, romanize = false) {
  const lang = language || "en";
  if (romanize) {
    const rmap = METRIC_ROMAN[lang] || {};
    if (rmap[metricCanonical]) return rmap[metricCanonical];
  }
  const map = METRIC_NAMES[lang] || {};
  if (map[metricCanonical]) return map[metricCanonical];
  // Fuzzy: match if the canonical contains a key prefix.
  const fallback = romanize ? METRIC_ROMAN[lang] || {} : map;
  for (const [key, val] of Object.entries(fallback)) {
    if (
      metricCanonical
        .toLowerCase()
        .includes(key.toLowerCase().split("(")[0].trim().toLowerCase())
    ) {
      return val;
    }
  }
  return metricCanonical;
}