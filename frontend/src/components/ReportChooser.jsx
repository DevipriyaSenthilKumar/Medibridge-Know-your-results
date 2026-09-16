const LABELS = {
  en: {
    title: "What are you analyzing today?",
    subtitle: "Choose the document so MediBridge reads it correctly.",
    labTitle: "Lab Result",
    labDesc: "A blood test or lab report sheet",
    rxTitle: "Prescription",
    rxDesc: "The medicines your doctor prescribed",
    close: "Close",
  },
  hi: {
    title: "आज आप क्या विश्लेषण करना चाहते हैं?",
    subtitle: "दस्तावेज़ चुनें ताकि MediBridge इसे सही ढंग से पढ़ सके।",
    labTitle: "लैब रिपोर्ट",
    labDesc: "रक्त परीक्षण या लैब रिपोर्ट शीट",
    rxTitle: "दवा पर्ची",
    rxDesc: "डॉक्टर द्वारा लिखी गई दवाइयां",
    close: "बंद करें",
  },
  ta: {
    title: "இன்று எதை பகுப்பாய்வு செய்ய விரும்புகிறீர்கள்?",
    subtitle: "MediBridge சரியாக படிக்க ஆவணத்தை தேர்வு செய்யவும்.",
    labTitle: "ஆய்வக முடிவு",
    labDesc: "இரத்தப் பரிசோதனை அல்லது ஆய்வக அறிக்கை",
    rxTitle: "மருந்து பரிந்துரை",
    rxDesc: "மருத்துவர் பரிந்துரைத்த மருந்துகள்",
    close: "மூடு",
  },
};

export default function ReportChooser({ language, onSelect, onClose }) {
  const labels = LABELS[language] || LABELS.en;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={labels.title}
      >
        <h2 className="text-xl font-bold text-medibridge-900">{labels.title}</h2>
        <p className="mt-1 text-sm text-slate-500">{labels.subtitle}</p>

        <div className="mt-5 grid grid-cols-1 gap-3">
          <button
            type="button"
            onClick={() => onSelect("lab")}
            className="group flex items-center gap-4 rounded-2xl border border-slate-200 p-4 text-left transition hover:border-medibridge-500 hover:bg-medibridge-50"
          >
            <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-medibridge-100 text-xl text-medibridge-700 group-hover:bg-medibridge-200" aria-hidden="true">
              🧪
            </span>
            <span>
              <span className="block font-semibold text-slate-900">{labels.labTitle}</span>
              <span className="block text-sm text-slate-500">{labels.labDesc}</span>
            </span>
          </button>

          <button
            type="button"
            onClick={() => onSelect("prescription")}
            className="group flex items-center gap-4 rounded-2xl border border-slate-200 p-4 text-left transition hover:border-medibridge-500 hover:bg-medibridge-50"
          >
            <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-medibridge-100 text-xl text-medibridge-700 group-hover:bg-medibridge-200" aria-hidden="true">
              💊
            </span>
            <span>
              <span className="block font-semibold text-slate-900">{labels.rxTitle}</span>
              <span className="block text-sm text-slate-500">{labels.rxDesc}</span>
            </span>
          </button>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="mt-5 w-full rounded-xl border border-slate-200 py-2 text-sm font-medium text-slate-500 transition hover:border-slate-300 hover:text-slate-700"
        >
          {labels.close}
        </button>
      </div>
    </div>
  );
}