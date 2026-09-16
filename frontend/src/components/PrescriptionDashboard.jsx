import useSpeech from "../useSpeech";

const SECTION_LABELS = {
  en: {
    medicines: "Your Medicines in Simple Words",
    questions: "Questions to Ask Your Pharmacist",
    listen: "Listen to this section",
    stop: "Stop reading",
    name: "Medicine",
    purpose: "Commonly used for",
    unknown: "Not identified",
    note: "MediBridge explains what these medicines are commonly used for — it does not check doses or say whether they are correct for you. Always confirm with your doctor or pharmacist.",
  },
  hi: {
    medicines: "आपकी दवाइयां सरल शब्दों में",
    questions: "फार्मासिस्ट से पूछने के प्रश्न",
    listen: "इस अनुभाग को सुनें",
    stop: "पढ़ना बंद करें",
    name: "दवा",
    purpose: "आमतौर पर किस लिए",
    unknown: "पहचाना नहीं गया",
    note: "MediBridge बताता है कि ये दवाइयां आमतौर पर किस लिए उपयोग होती हैं — यह खुराक की जाँच नहीं करता और न ही बताता है कि वे आपके लिए सही हैं। हमेशा डॉक्टर या फार्मासिस्ट से पुष्टि करें।",
  },
  ta: {
    medicines: "உங்கள் மருந்துகள் எளிய சொற்களில்",
    questions: "மருந்தாளுனரிடம் கேட்க வேண்டிய கேள்விகள்",
    listen: "இந்த பகுதியை கேளுங்கள்",
    stop: "படிப்பதை நிறுத்து",
    name: "மருந்து",
    purpose: "பொதுவாக எதற்கு",
    unknown: "அடையாளம் காணப்படவில்லை",
    note: "MediBridge இந்த மருந்துகள் பொதுவாக எதற்காகப் பயன்படுத்தப்படுகின்றன என்பதை விளக்குகிறது — இது அளவை சரிபார்க்காது அல்லது அவை உங்களுக்கு சரிதானா என்று கூறாது. எப்போதும் மருத்துவர் அல்லது மருந்தாளுனரிடம் உறுதிப்படுத்துங்கள்.",
  },
};

// Romanized spoken labels (see Dashboard.jsx SPEECH_LABELS for why).
const SPEECH_LABELS = {
  en: SECTION_LABELS.en,
  hi: {
    purpose: "Aam taur par kis liye",
    questions: "Pharmacist se poochhne ke prashn",
  },
  ta: {
    purpose: "Podhuvaaga etharku",
    questions: "Mundhaalunidam ketka vendiya kelvigal",
  },
};

function SectionHeader({ title, listenLabel, stopLabel, isSpeaking, onSpeak }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      <button
        type="button"
        onClick={onSpeak}
        className="btn-secondary px-3 py-1.5 text-xs"
        aria-pressed={isSpeaking}
      >
        {isSpeaking ? stopLabel : listenLabel}
      </button>
    </div>
  );
}

export default function PrescriptionDashboard({ results, language }) {
  const labels = SECTION_LABELS[language] || SECTION_LABELS.en;
  const { activeSection, speak, stop } = useSpeech(language);

  // See Dashboard.jsx — server TTS reads native script; browser fallback
  // gets romanized phonetics so nothing is silently skipped.
  const speechLabelsFor = (useNativeScript) =>
    useNativeScript
      ? labels
      : { ...labels, ...(SPEECH_LABELS[language] || {}) };

  const medicines = results.medicines || [];
  const questions = results.pharmacist_questions || [];

  const buildMedicinesSpeech = (useNativeScript) => {
    if (!medicines.length) return "";
    const speechLabels = speechLabelsFor(useNativeScript);
    return medicines
      .map(
        (item, i) =>
          `${i + 1}. ${item.name}. ${speechLabels.purpose}: ${item.purpose}`
      )
      .join(". ");
  };

  const buildQuestionsSpeech = (useNativeScript) => {
    if (!questions.length) return "";
    const speechLabels = speechLabelsFor(useNativeScript);
    return questions
      .map((q, i) => `${speechLabels.questions} ${i + 1}. ${q}`)
      .join(". ");
  };

  return (
    <div className="space-y-6">
      <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        {labels.note}
      </p>

      {medicines.length > 0 && (
        <section className="card" aria-labelledby="rx-medicines-heading">
          <SectionHeader
            title={labels.medicines}
            listenLabel={labels.listen}
            stopLabel={labels.stop}
            isSpeaking={activeSection === "medicines"}
            onSpeak={() => speak("medicines", buildMedicinesSpeech)}
          />
          <div id="rx-medicines-heading" className="mt-4 space-y-3">
            {medicines.map((item, index) => (
              <article
                key={`${item.name}-${index}`}
                className={`flex items-start gap-3 rounded-xl border p-4 ${
                  item.matched
                    ? "border-medibridge-100 bg-medibridge-50/50"
                    : "border-slate-200 bg-slate-50"
                }`}
              >
                <span
                  className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ${
                    item.matched ? "bg-medibridge-600" : "bg-slate-400"
                  }`}
                  aria-hidden="true"
                >
                  {index + 1}
                </span>
                <div>
                  <h3 className="font-semibold text-medibridge-800">{item.name}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-slate-700">
                    <span className="font-medium text-slate-500">{labels.purpose}: </span>
                    {item.purpose}
                  </p>
                  {!item.matched && (
                    <p className="mt-1 text-xs font-medium uppercase tracking-wide text-slate-400">
                      {labels.unknown}
                    </p>
                  )}
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {questions.length > 0 && (
        <section className="card" aria-labelledby="rx-questions-heading">
          <SectionHeader
            title={labels.questions}
            listenLabel={labels.listen}
            stopLabel={labels.stop}
            isSpeaking={activeSection === "questions"}
            onSpeak={() => speak("questions", buildQuestionsSpeech)}
          />
          <ol id="rx-questions-heading" className="mt-4 space-y-3">
            {questions.map((question, index) => (
              <li
                key={question}
                className="flex gap-3 rounded-xl border border-medibridge-100 bg-medibridge-50/50 p-4"
              >
                <span
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-medibridge-600 text-xs font-bold text-white"
                  aria-hidden="true"
                >
                  {index + 1}
                </span>
                <p className="text-sm leading-relaxed text-slate-800">{question}</p>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}