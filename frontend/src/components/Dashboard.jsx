import { useCallback } from "react";
import { localizedMetric } from "../translations";
import useSpeech from "../useSpeech";

const SECTION_LABELS = {
  en: {
    summary: "Your Report in Simple Words",
    nextSteps: "What to Do Next",
    terms: "Simplified Terms",
    numbers: "Your Numbers",
    questions: "Questions for Your Doctor",
    listen: "Listen to this section",
    stop: "Stop reading",
    termLabel: "Term",
    explanation: "Explanation",
    analogy: "Analogy",
    value: "Your value",
    range: "Typical range",
    context: "What this may mean",
    possibleCauses: "What it could be",
    possibleConditions: "What this MAY be linked to",
    doctorGuidance: "What to do next",
    high: "High",
    low: "Low",
    withinRange: "In Range",
    unknown: "Range unknown",
  },
  hi: {
    summary: "आपकी रिपोर्ट सरल शब्दों में",
    nextSteps: "आगे क्या करें",
    terms: "सरल शब्द",
    numbers: "आपके नंबर",
    questions: "डॉक्टर से पूछने के प्रश्न",
    listen: "इस अनुभाग को सुनें",
    stop: "पढ़ना बंद करें",
    termLabel: "शब्द",
    explanation: "व्याख्या",
    analogy: "उदाहरण",
    value: "आपका मान",
    range: "सामान्य सीमा",
    context: "इसका क्या मतलब हो सकता है",
    possibleCauses: "यह क्या हो सकता है",
    possibleConditions: "यह किससे जुड़ा हो सकता है",
    doctorGuidance: "आगे क्या करें",
    high: "उच्च",
    low: "निम्न",
    withinRange: "सामान्य सीमा में",
    unknown: "सीमा अज्ञात",
  },
  ta: {
    summary: "உங்கள் அறிக்கை எளிய வார்த்தைகளில்",
    nextSteps: "அடுத்து என்ன செய்வது",
    terms: "எளிய சொற்கள்",
    numbers: "உங்கள் எண்கள்",
    questions: "மருத்துவரிடம் கேட்க வேண்டிய கேள்விகள்",
    listen: "இந்த பகுதியை கேளுங்கள்",
    stop: "படிப்பதை நிறுத்து",
    termLabel: "சொல்",
    explanation: "விளக்கம்",
    analogy: "உதாரணம்",
    value: "உங்கள் மதிப்பு",
    range: "சாதாரண வரம்பு",
    context: "இதன் அர்த்தம்",
    possibleCauses: "இது என்னவாக இருக்கலாம்",
    possibleConditions: "இது எதனுடன் தொடர்புடையதாக இருக்கலாம்",
    doctorGuidance: "அடுத்து என்ன செய்வது",
    high: "அதிகம்",
    low: "குறைவு",
    withinRange: "சாதாரண வரம்பில்",
    unknown: "வரம்பு தெரியவில்லை",
  },
};

// Latin/romanized versions of the spoken labels. Some platforms have no
// voice that can pronounce Devanagari/Tamil script (e.g. Windows for ta-IN);
// without this the TTS quietly skips those sections, so only the English
// metric name and digits are heard. These spell the label phonetically so it
// can be read by any voice, keeping normal range / status / guidance audible.
// The server TTS path (edge-tts) reads the native script directly and never
// needs these.
const SPEECH_LABELS = {
  en: SECTION_LABELS.en,
  hi: {
    value: "Aapka maan",
    range: "Samaanya seema",
    context: "Iska kya matlab ho sakta hai",
    possibleConditions: "Ye kisse juda ho sakta hai",
    possibleCauses: "Ye kya ho sakta hai",
    doctorGuidance: "Aage kya karein",
    explanation: "Vyakhya",
    analogy: "Udahaaran",
    high: "Ooncha",
    low: "Neema",
    withinRange: "Samaanya seema mein",
    unknown: "Seema anjaat",
  },
  ta: {
    value: "Ungal madhipu",
    range: "Saadhaarana varambu",
    context: "Ithin artham",
    possibleConditions: "Idhu edhanudan thodarpudaiyadhaaka irukkalaam",
    possibleCauses: "Idhu ennavaga irukkalaam",
    doctorGuidance: "Aduthu enna seyya veendum",
    explanation: "Vilakkam",
    analogy: "Udharanam",
    high: "Adhigam",
    low: "Kuraivu",
    withinRange: "Saadhaarana varambu ill",
    unknown: "Varambu theriyaavillai",
  },
};

const STATUS_SPEECH_KEY = {
  high: "high",
  low: "low",
  within_range: "within_range",
  unknown: "unknown",
};

const STATUS_PHRASES = {
  en: {
    high: "Your value is high",
    low: "Your value is low",
    within_range: "Your value is normal",
    unknown: "Your value could not be read",
  },
  hi: {
    high: "आपका मान उच्च है",
    low: "आपका मान निम्न है",
    within_range: "आपका मान सामान्य है",
    unknown: "आपका मान नहीं पढ़ा जा सका",
    roman: {
      high: "Aapka maan ooncha hai",
      low: "Aapka maan neema hai",
      within_range: "Aapka maan normal hai",
      unknown: "Aapka maan nahi padha ja saka",
    },
  },
  ta: {
    high: "உங்கள் மதிப்பு அதிகம்",
    low: "உங்கள் மதிப்பு குறைவு",
    within_range: "உங்கள் மதிப்பு இயல்பானது",
    unknown: "உங்கள் மதிப்பை படிக்க முடியவில்லை",
    roman: {
      high: "Ungal madhipu adhigam",
      low: "Ungal madhipu kuraivu",
      within_range: "Ungal madhipu saadhaaranam",
      unknown: "Ungal madhipu padikka mudiyavillai",
    },
  },
};

const statusPhraseFor = (status, language, useNativeScript) => {
  const phrases = STATUS_PHRASES[language] || STATUS_PHRASES.en;
  const key = STATUS_SPEECH_KEY[status] || "within_range";
  if (!useNativeScript && phrases?.roman?.[key]) return phrases.roman[key];
  return phrases[key] || STATUS_PHRASES.en[key];
};

// Numeric glue words per language. Mixing English ("point", "to") into
// Hindi/Tamil audio makes the voice stumble, so every injected word is
// localized: native script for the server TTS path, romanized phonetics for
// the browser-fallback path.
const NUM_WORDS = {
  en: { decimal: " point ", sep: " to ", gt: " greater than ", lt: " less than " },
  hi: {
    decimal: " दशमलव ",
    sep: " से ",
    gt: " से ऊपर ",
    lt: " से नीचे ",
    roman: {
      decimal: " dashamalav ",
      sep: " se ",
      gt: " se oopar ",
      lt: " se neeche ",
    },
  },
  ta: {
    decimal: " புள்ளி ",
    sep: " முதல் ",
    gt: " க்கு மேல் ",
    lt: " க்கு கீழ் ",
    roman: {
      decimal: " palli ",
      sep: " muthal ",
      gt: " kku mel ",
      lt: " kku keezh ",
    },
  },
};

const STEP_WORD = {
  en: "Step",
  hi: "चरण",
  ta: "படி",
  roman: { hi: "Charan", ta: "Padhi" },
};

const numWordsFor = (lang, useNativeScript) => {
  const base = NUM_WORDS[lang] || NUM_WORDS.en;
  if (lang === "en" || useNativeScript || !base.roman) return base;
  return { ...base, ...base.roman };
};

const stepWordFor = (lang, useNativeScript) => {
  const base = STEP_WORD[lang] || "Step";
  if (lang === "en" || useNativeScript || !STEP_WORD.roman) return base;
  return STEP_WORD.roman[lang] || base;
};

// "2.5" -> "2 दशमलव 5"; "22" (whole) -> "22 दशमलव 0" so no digit is collapsed.
// Never reads "ten" for "1 0" — decimals are spelled digit-by-digit.
const _decimalize = (text, decimalWord) =>
  text.replace(
    /(\d+)\.(\d+)/,
    (_, lead, frac) => `${lead}${decimalWord}${frac.split("").join(" ")}`
  );

const speakableNumber = (value, lang, useNativeScript) => {
  if (value === null || value === undefined) return value;
  const words = numWordsFor(lang, useNativeScript);
  let text = String(value);
  const num = Number(text);
  if (!Number.isNaN(num) && Number.isFinite(num) && !/[eE]/.test(text)) {
    if (!text.includes(".")) text = `${num}.0`;
    text = _decimalize(text, words.decimal);
  }
  return text;
};

const speakableRange = (range, lang, useNativeScript) => {
  if (!range) return range;
  const words = numWordsFor(lang, useNativeScript);
  let out = String(range);
  out = out.replace(/\s*[\u2013\u2212-]\s*/g, words.sep);
  out = out.replace(/\s*>\s?/g, words.gt);
  out = out.replace(/\s*<\s?/g, words.lt);
  // Collapse "4.0-11.0" to "4 से 11" for a cleaner read; keep real decimals.
  out = out.replace(/(\d+)\.0+(?=\s|$)/g, "$1");
  out = _decimalize(out, words.decimal);
  return out;
};

function SpeakerIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="h-4 w-4"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15.536 8.464a5 5 0 010 7.072M17.95 6.05a8 8 0 010 11.9M6.5 8.5H4a1 1 0 00-1 1v5a1 1 0 001 1h2.5l4.5 4.5V4L6.5 8.5z"
      />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="h-4 w-4"
      fill="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <rect x="6" y="6" width="12" height="12" rx="1" />
    </svg>
  );
}

function SectionHeader({ title, onSpeak, isSpeaking, listenLabel, stopLabel }) {
  return (
    <div className="mb-4 flex items-center justify-between gap-3">
      <h2 className="text-lg font-semibold text-medibridge-900">{title}</h2>
      <button
        type="button"
        className="tts-btn"
        onClick={onSpeak}
        aria-label={isSpeaking ? stopLabel : listenLabel}
        title={isSpeaking ? stopLabel : listenLabel}
      >
        {isSpeaking ? <StopIcon /> : <SpeakerIcon />}
      </button>
    </div>
  );
}

export default function Dashboard({ results, language }) {
  const labels = SECTION_LABELS[language] || SECTION_LABELS.en;
  const { activeSection, speak, stop } = useSpeech(language);

  // Labels used while speaking. Server TTS voices read the native script;
  // browser speechSynthesis gets romanized phonetics when no script-capable
  // voice is installed.
  const speechLabelsFor = (useNativeScript) =>
    useNativeScript
      ? labels
      : { ...labels, ...(SPEECH_LABELS[language] || {}) };

  const buildSummarySpeech = () => {
    if (!results.report_summary) return "";
    return results.report_summary;
  };

  const buildNextStepsSpeech = (useNativeScript) => {
    if (!results.next_steps?.length) return "";
    const stepWord = stepWordFor(language, useNativeScript);
    return results.next_steps
      .map((step, index) => `${stepWord} ${index + 1}. ${step}`)
      .join(". ");
  };

  const buildTermsSpeech = (useNativeScript) => {
    if (!results.simplified_terms?.length) return "";
    const speechLabels = speechLabelsFor(useNativeScript);
    return results.simplified_terms
      .map(
        (item, index) =>
          `${index + 1}. ${localizedMetric(item.term, language, !useNativeScript)}. ${speechLabels.explanation}: ${item.explanation}. ${speechLabels.analogy}: ${item.analogy}`
      )
      .join(". ");
  };

  const buildNumbersSpeech = (useNativeScript) => {
    if (!results.numerical_context?.length) return "";
    const speechLabels = speechLabelsFor(useNativeScript);
    return results.numerical_context
      .map((item, index) => {
        const name = localizedMetric(item.metric, language, !useNativeScript);
        const statusPhrase = statusPhraseFor(item.status, language, useNativeScript);
        // Status + value in one sentence: "WBC. Your value is high: 22.1.
        // Normal range: 4 to 11."
        let sentence = `${index + 1}. ${name}. ${statusPhrase}: ${speakableNumber(item.value, language, useNativeScript)}. ${speechLabels.range}: ${speakableRange(item.normal_range, language, useNativeScript)}.`;
        // Only elaborate on values that are out of range.
        if (item.status === "high" || item.status === "low") {
          if (item.possible_conditions?.length) {
            sentence += ` ${speechLabels.possibleConditions}: ${item.possible_conditions.join(", ")}.`;
          }
          if (item.possible_causes) {
            sentence += ` ${speechLabels.possibleCauses}: ${item.possible_causes}`;
          }
          if (item.doctor_guidance) {
            sentence += ` ${speechLabels.doctorGuidance}: ${item.doctor_guidance}`;
          }
        }
        return sentence;
      })
      .join(". ");
  };

  const buildQuestionsSpeech = () => {
    if (!results.doctor_questions?.length) return "";
    return results.doctor_questions
      .map((question, index) => `Question ${index + 1}. ${question}`)
      .join(". ");
  };

  const statusMeta = useCallback((status) => {
    const key = status || "unknown";
    const map = {
      high: {
        badge: "bg-red-100 text-red-800 border-red-200",
        value: "text-red-700",
        card: "border-red-200",
      },
      low: {
        badge: "bg-amber-100 text-amber-800 border-amber-200",
        value: "text-amber-700",
        card: "border-amber-200",
      },
      within_range: {
        badge: "bg-emerald-100 text-emerald-800 border-emerald-200",
        value: "text-emerald-700",
        card: "border-emerald-200",
      },
      unknown: {
        badge: "bg-slate-100 text-slate-700 border-slate-200",
        value: "text-slate-900",
        card: "border-slate-200",
      },
    };
    return map[key] || map.unknown;
  }, []);

  const statusLabel = useCallback(
    (status) => {
      if (status === "high") return labels.high;
      if (status === "low") return labels.low;
      if (status === "within_range") return labels.withinRange;
      return labels.unknown;
    },
    [labels]
  );

  return (
    <div className="space-y-5">
      {results.report_summary && (
        <section className="card" aria-labelledby="summary-heading">
          <SectionHeader
            title={labels.summary}
            listenLabel={labels.listen}
            stopLabel={labels.stop}
            isSpeaking={activeSection === "summary"}
            onSpeak={() => speak("summary", buildSummarySpeech)}
          />
          <p
            id="summary-heading"
            className="rounded-xl border border-medibridge-100 bg-medibridge-50/50 p-4 text-base leading-relaxed text-slate-800"
          >
            {results.report_summary}
          </p>
        </section>
      )}

      {results.next_steps?.length > 0 && (
        <section className="card" aria-labelledby="nextsteps-heading">
          <SectionHeader
            title={labels.nextSteps}
            listenLabel={labels.listen}
            stopLabel={labels.stop}
            isSpeaking={activeSection === "nextsteps"}
            onSpeak={() => speak("nextsteps", buildNextStepsSpeech)}
          />
          <ol id="nextsteps-heading" className="space-y-3">
            {results.next_steps.map((step, index) => (
              <li
                key={step}
                className="flex gap-3 rounded-xl border border-emerald-100 bg-emerald-50/50 p-4"
              >
                <span
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-xs font-bold text-white"
                  aria-hidden="true"
                >
                  {index + 1}
                </span>
                <p className="text-sm leading-relaxed text-slate-800">{step}</p>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section className="card" aria-labelledby="terms-heading">
        <SectionHeader
          title={labels.terms}
          listenLabel={labels.listen}
          stopLabel={labels.stop}
          isSpeaking={activeSection === "terms"}
          onSpeak={() => speak("terms", buildTermsSpeech)}
        />
        <div id="terms-heading" className="space-y-4">
          {results.simplified_terms?.map((item) => (
            <article
              key={item.term}
              className="rounded-xl border border-slate-100 bg-slate-50 p-4"
            >
              <h3 className="font-semibold text-medibridge-800">{localizedMetric(item.term, language)}</h3>
              <p className="mt-2 text-sm text-slate-700">
                <span className="font-medium text-slate-900">{labels.explanation}: </span>
                {item.explanation}
              </p>
              <p className="mt-2 text-sm text-slate-600">
                <span className="font-medium text-slate-800">{labels.analogy}: </span>
                {item.analogy}
              </p>
            </article>
          ))}
        </div>
      </section>

      <section className="card" aria-labelledby="numbers-heading">
        <SectionHeader
          title={labels.numbers}
          listenLabel={labels.listen}
          stopLabel={labels.stop}
          isSpeaking={activeSection === "numbers"}
          onSpeak={() => speak("numbers", buildNumbersSpeech)}
        />
        <div id="numbers-heading" className="grid gap-4 sm:grid-cols-2">
          {results.numerical_context?.[0]?.calm_explanation && (
            <p className="col-span-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-500">
              {results.numerical_context[0].calm_explanation}
            </p>
          )}
          {results.numerical_context?.map((item) => {
            const meta = statusMeta(item.status);
            return (
              <article
                key={`${item.metric}-${item.value}`}
                className={`rounded-xl border bg-gradient-to-br from-white to-medibridge-50/30 p-4 ${meta.card}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-semibold text-medibridge-800">{localizedMetric(item.metric, language)}</h3>
                  <span
                    className={`inline-flex shrink-0 items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${meta.badge}`}
                  >
                    {statusLabel(item.status)}
                  </span>
                </div>
                <dl className="mt-3 space-y-2 text-sm">
                  <div className="flex justify-between gap-2">
                    <dt className="text-slate-500">{labels.value}</dt>
                    <dd className={`text-lg font-bold ${meta.value}`}>{item.value}</dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt className="text-slate-500">{labels.range}</dt>
                    <dd className="text-slate-700">{item.normal_range}</dd>
                  </div>
                </dl>
                {item.possible_causes && (
                  <p className="mt-3 rounded-lg border border-amber-100 bg-amber-50/60 p-3 text-sm leading-relaxed text-amber-900">
                    <span className="font-semibold">{labels.possibleCauses}: </span>
                    {item.possible_causes}
                  </p>
                )}
                {item.possible_conditions?.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      {labels.possibleConditions}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {item.possible_conditions.map((condition) => (
                        <span
                          key={condition}
                          className="inline-flex items-center rounded-full border border-purple-200 bg-purple-50 px-2.5 py-0.5 text-xs font-medium text-purple-800"
                        >
                          {condition}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {item.doctor_guidance && (
                  <p className="mt-3 rounded-lg border border-emerald-100 bg-emerald-50/60 p-3 text-sm leading-relaxed text-emerald-900">
                    <span className="font-semibold">{labels.doctorGuidance}: </span>
                    {item.doctor_guidance}
                  </p>
                )}
              </article>
            );
          })}
        </div>
      </section>

      <section className="card" aria-labelledby="questions-heading">
        <SectionHeader
          title={labels.questions}
          listenLabel={labels.listen}
          stopLabel={labels.stop}
          isSpeaking={activeSection === "questions"}
          onSpeak={() => speak("questions", buildQuestionsSpeech)}
        />
        <ol id="questions-heading" className="space-y-3">
          {results.doctor_questions?.map((question, index) => (
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
    </div>
  );
}
