import { useCallback, useEffect, useState } from "react";
import AuthModal from "./components/AuthModal.jsx";
import Dashboard from "./components/Dashboard.jsx";
import ErrorBoundary from "./components/ErrorBoundary.jsx";
import HistoryPanel from "./components/HistoryPanel.jsx";
import Logo from "./components/Logo.jsx";
import PrescriptionDashboard from "./components/PrescriptionDashboard.jsx";
import ReportChooser from "./components/ReportChooser.jsx";
import UploadZone from "./components/UploadZone.jsx";
import useAuth from "./hooks/useAuth.js";

const LABELS = {
  en: {
    tagline: "Understand your lab results in plain language",
    disclaimer:
      "MediBridge does not diagnose or treat. Always discuss results with your doctor.",
    uploadTitle: "Upload Your Lab Report",
    newUpload: "Upload Another Report",
    emergencyTitle: "Possible Emergency Detected",
    emergencyBody:
      "Some values in your report may need urgent medical attention. Please contact a doctor or emergency services immediately.",
    reportType: "What are you uploading?",
    labType: "Lab Report",
    rxType: "Prescription",
    rxTitle: "Upload The Prescription",
    rxTagline: "Understand the medicines on your prescription in plain language",
    rxDisclaimer:
      "MediBridge does not check doses or say whether medicines are correct. Always discuss with your doctor or pharmacist.",
    rxNewUpload: "Upload Another Prescription",
    signIn: "Sign in",
    logout: "Log out",
    history: "My Reports",
    savedFlash: "This report was saved to your history.",
    heroTitle: "Your lab report, explained.",
    heroSubtitle:
      "MediBridge reads a photo of your lab result or prescription and explains it in plain, safe language — in English, हिन्दी, or தமிழ்.",
    heroStart: "Get Started",
    heroSkip: "Continue without an account",
    heroTrust: "Does not diagnose. Does not prescribe. Always discuss with your doctor.",
    featuresTitle: "Built for everyday patients",
    feat1Title: "Reads from a photo",
    feat1Desc: "OCR turns your paper report into text — no typing required.",
    feat2Title: "Plain-language insight",
    feat2Desc: "Medical terms become simple explanations, never a diagnosis.",
    feat3Title: "Speaks your language",
    feat3Desc: "Summaries and audio in English, हिन्दी, and தமிழ்.",
    howTitle: "How it works",
    how1: "Upload or photograph your report",
    how2: "Choose Lab Result or Prescription",
    how3: "Read your summary or listen in your language",
    navHome: "Home",
    navAnalyze: "New Report",
    navRecords: "Previous Records",
    changeType: "Change report type",
    unsignedNote:
      "You're using MediBridge without an account. Sign in to save your history.",
  },
  hi: {
    tagline: "अपनी लैब रिपोर्ट को सरल भाषा में समझें",
    disclaimer:
      "MediBridge निदान या उपचार नहीं करता। हमेशा परिणाम अपने डॉक्टर से चर्चा करें।",
    uploadTitle: "अपनी लैब रिपोर्ट अपलोड करें",
    newUpload: "दूसरी रिपोर्ट अपलोड करें",
    emergencyTitle: "संभावित आपात स्थिति",
    emergencyBody:
      "आपकी रिपोर्ट में कुछ मान तुरंत चिकित्सा ध्यान की आवश्यकता हो सकती है। कृपया तुरंत डॉक्टर या आपातकालीन सेवाओं से संपर्क करें।",
    reportType: "आप क्या अपलोड कर रहे हैं?",
    labType: "लैब रिपोर्ट",
    rxType: "दवा पर्ची",
    rxTitle: "दवा पर्ची अपलोड करें",
    rxTagline: "अपनी दवा पर्ची की दवाइयों को सरल भाषा में समझें",
    rxDisclaimer:
      "MediBridge खुराक की जाँच नहीं करता और न ही बताता है कि दवाइयां सही हैं। हमेशा डॉक्टर या फार्मासिस्ट से चर्चा करें।",
    rxNewUpload: "दूसरी दवा पर्ची अपलोड करें",
    signIn: "साइन इन करें",
    logout: "लॉग आउट",
    history: "मेरी रिपोर्ट",
    savedFlash: "यह रिपोर्ट आपके इतिहास में सहेजी गई।",
    heroTitle: "आपकी लैब रिपोर्ट, सरल भाषा में।",
    heroSubtitle:
      "MediBridge आपकी लैब रिपोर्ट या दवा पर्ची की फोटो पढ़ता है और उसे सरल, सुरक्षित भाषा में समझाता है — अंग्रेज़ी, हिन्दी या தமிழ் में।",
    heroStart: "शुरू करें",
    heroSkip: "खाते के बिना जारी रखें",
    heroTrust: "निदान नहीं करता। उपचार नहीं लिखता। हमेशा अपने डॉक्टर से चर्चा करें।",
    featuresTitle: "आम मरीज़ों के लिए बनाया गया",
    feat1Title: "फोटो से पढ़ता है",
    feat1Desc: "OCR आपकी कागज़ी रिपोर्ट को टेक्स्ट में बदल देता है — टाइपिंग की ज़रूरत नहीं।",
    feat2Title: "सरल भाषा में विश्लेषण",
    feat2Desc: "मेडिकल शब्द सरल समझौते बन जाते हैं, कभी निदान नहीं।",
    feat3Title: "आपकी भाषा में बोलता है",
    feat3Desc: "सारांश और ऑडियो अंग्रेज़ी, हिन्दी और தமிழ் में।",
    howTitle: "यह कैसे काम करता है",
    how1: "अपनी रिपोर्ट अपलोड या फोटो खींचें",
    how2: "लैब रिपोर्ट या दवा पर्ची चुनें",
    how3: "अपनी भाषा में सारांश पढ़ें या सुनें",
    navHome: "होम",
    navAnalyze: "नई रिपोर्ट",
    navRecords: "पिछली रिपोर्ट",
    changeType: "रिपोर्ट का प्रकार बदलें",
    unsignedNote:
      "आप बिना खाते के MediBridge उपयोग कर रहे हैं। इतिहास सहेजने के लिए साइन इन करें।",
  },
  ta: {
    tagline: "உங்கள் ஆய்வக அறிக்கையை எளிய மொழியில் புரிந்து கொள்ளுங்கள்",
    disclaimer:
      "MediBridge நோயறிதல் அல்லது சிகிச்சை வழங்காது. முடிவுகளை எப்போதும் மருத்துவருடன் பேசுங்கள்.",
    uploadTitle: "உங்கள் ஆய்வக அறிக்கையை பதிவேற்றுங்கள்",
    newUpload: "மற்றொரு அறிக்கையை பதிவேற்றுங்கள்",
    emergencyTitle: "அவசர சூழ்நிலை சாத்தியம்",
    emergencyBody:
      "உங்கள் அறிக்கையில் சில மதிப்புகள் உடனடி மருத்துவ கவனம் தேவைப்படலாம். உடனே மருத்துவர் அல்லது அவசர சேவையை தொடர்பு கொள்ளுங்கள்.",
    reportType: "எதை பதிவேற்றுகிறீர்கள்?",
    labType: "ஆய்வக அறிக்கை",
    rxType: "மருந்து பரிந்துரை",
    rxTitle: "மருந்து பரிந்துரையை பதிவேற்றுங்கள்",
    rxTagline: "உங்கள் பரிந்துரையில் உள்ள மருந்துகளை எளிய மொழியில் புரிந்து கொள்ளுங்கள்",
    rxDisclaimer:
      "MediBridge அளவை சரிபார்க்காது அல்லது மருந்துகள் சரிதானா என்று கூறாது. எப்போதும் மருத்துவர் அல்லது மருந்தாளுனரிடம் பேசுங்கள்.",
    rxNewUpload: "மற்றொரு பரிந்துரையை பதிவேற்றுங்கள்",
    signIn: "உள்நுழைக",
    logout: "வெளியேறு",
    history: "எனது அறிக்கைகள்",
    savedFlash: "இந்த அறிக்கை உங்கள் வரலாற்றில் சேமிக்கப்பட்டது.",
    heroTitle: "உங்கள் ஆய்வக அறிக்கை, எளிய மொழியில்.",
    heroSubtitle:
      "MediBridge உங்கள் ஆய்வக முடிவு அல்லது பரிந்துரையின் புகைப்படத்தை படித்து, எளிய பாதுகாப்பான மொழியில் விளக்குகிறது — English, हिन्दी அல்லது தமிழ்.",
    heroStart: "தொடங்குங்கள்",
    heroSkip: "கணக்கு இல்லாமல் தொடரவும்",
    heroTrust: "நோயறிதல் செய்யாது. சிகிச்சை பரிந்துரைக்காது. எப்போதும் உங்கள் மருத்துவரிடம் பேசுங்கள்.",
    featuresTitle: "சாதாரண நோயாளிகளுக்காக",
    feat1Title: "புகைப்படத்திலிருந்து படிக்கும்",
    feat1Desc: "OCR உங்கள் காகித அறிக்கையை உரையாக மாற்றுகிறது — தட்டச்சு தேவையில்லை.",
    feat2Title: "எளிய மொழி விளக்கம்",
    feat2Desc: "மருத்துவ சொற்கள் எளிய விளக்கங்களாகின்றன, ஒருபோதும் நோயறிதல் அல்ல.",
    feat3Title: "உங்கள் மொழியில் பேசும்",
    feat3Desc: "சுருக்கங்கள் மற்றும் ஒலியும் English, हिन्दी, தமிழ்.",
    howTitle: "இது எப்படி வேலை செய்கிறது",
    how1: "உங்கள் அறிக்கையை பதிவேற்றவும் அல்லது புகைப்படம் எடுக்கவும்",
    how2: "ஆய்வக முடிவு அல்லது மருந்து பரிந்துரையை தேர்வு செய்யவும்",
    how3: "உங்கள் மொழியில் சுருக்கத்தை படிக்கவும் அல்லது கேட்கவும்",
    navHome: "முகப்பு",
    navAnalyze: "புதிய அறிக்கை",
    navRecords: "முந்தைய அறிக்கைகள்",
    changeType: "அறிக்கை வகையை மாற்று",
    unsignedNote:
      "நீங்கள் கணக்கு இல்லாமல் MediBridge ஐ பயன்படுத்துகிறீர்கள். வரலாற்றை சேமிக்க உள்நுழையவும்.",
  },
};

export default function App() {
  const [language, setLanguage] = useState("en");
  const [docType, setDocType] = useState("lab");
  const [page, setPage] = useState("landing"); // landing | analyze | records
  const [chooserOpen, setChooserOpen] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [showAuth, setShowAuth] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [historyRefresh, setHistoryRefresh] = useState(0);
  const { auth, login, signup, logout, authHeaders } = useAuth();

  const labels = LABELS[language];
  const isPrescription = docType === "prescription";
  const authName = auth?.email || "";

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [page]);

  const autoSave = useCallback(
    (data, kind) => {
      if (!auth?.token || !data) return;
      fetch("/api/history/save", {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ kind, language, analysis: data }),
      })
        .then((res) => {
          if (res.ok) {
            setSavedFlash(true);
            setHistoryRefresh((n) => n + 1);
            setTimeout(() => setSavedFlash(false), 4000);
          }
        })
        .catch(() => {});
    },
    [auth, authHeaders, language]
  );

  const handleAnalysisComplete = useCallback(
    (data) => {
      setResults(data);
      setError(null);
      autoSave(data, docType);
    },
    [autoSave, docType]
  );

  const handleError = useCallback((message) => {
    setError(message);
    setResults(null);
  }, []);

  const handleReset = useCallback(() => {
    setResults(null);
    setError(null);
  }, []);

  const selectDocType = useCallback(
    (type) => {
      setDocType(type);
      setResults(null);
      setError(null);
      setChooserOpen(false);
      setPage("analyze");
    },
    []
  );

  const navigate = useCallback((target) => {
    setPage(target);
    setError(null);
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-b from-medibridge-50 via-white to-slate-50">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <button
            type="button"
            onClick={() => navigate("landing")}
            className="flex items-center gap-3 text-left"
            aria-label={labels.navHome}
          >
            <div className="drop-shadow-sm">
              <Logo size={40} />
            </div>
            <div>
              <h1 className="flex items-center gap-2 text-xl font-bold tracking-tight text-medibridge-900">
                Medi<span className="text-medibridge-500">Bridge</span>
              </h1>
            </div>
          </button>

          <nav className="flex items-center gap-2" aria-label="Main navigation">
            <button
              type="button"
              onClick={() => navigate("landing")}
              className={`rounded-xl px-3 py-2 text-sm font-medium transition ${
                page === "landing"
                  ? "bg-medibridge-100 text-medibridge-800"
                  : "text-slate-600 hover:bg-medibridge-50 hover:text-medibridge-800"
              }`}
            >
              {labels.navHome}
            </button>
            <button
              type="button"
              onClick={() => setChooserOpen(true)}
              className={`rounded-xl px-3 py-2 text-sm font-medium transition ${
                page === "analyze"
                  ? "bg-medibridge-100 text-medibridge-800"
                  : "text-slate-600 hover:bg-medibridge-50 hover:text-medibridge-800"
              }`}
            >
              {labels.navAnalyze}
            </button>
            <button
              type="button"
              onClick={() => navigate("records")}
              className={`rounded-xl px-3 py-2 text-sm font-medium transition ${
                page === "records"
                  ? "bg-medibridge-100 text-medibridge-800"
                  : "text-slate-600 hover:bg-medibridge-50 hover:text-medibridge-800"
              }`}
            >
              {labels.navRecords}
            </button>

            <label htmlFor="language" className="sr-only">
              Language
            </label>
            <select
              id="language"
              value={language}
              onChange={(event) => {
                setLanguage(event.target.value);
                handleReset();
              }}
              className="mx-1 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 focus:border-medibridge-500 focus:outline-none focus:ring-2 focus:ring-medibridge-500"
            >
              <option value="en">English</option>
              <option value="hi">हिन्दी</option>
              <option value="ta">தமிழ்</option>
            </select>

            {auth ? (
              <>
                <span className="hidden text-sm text-slate-500 lg:inline">{authName}</span>
                <button
                  type="button"
                  onClick={() => logout()}
                  className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:border-medibridge-400"
                >
                  {labels.logout}
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => setShowAuth(true)}
                className="rounded-xl bg-medibridge-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-medibridge-700"
              >
                {labels.signIn}
              </button>
            )}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8 sm:py-12">
        {page === "landing" && (
          <ErrorBoundary>
            <section className="mx-auto max-w-3xl text-center">
              <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-medibridge-500 to-medibridge-700 shadow-lg">
                <Logo size={56} />
              </div>
              <h2 className="text-4xl font-extrabold tracking-tight text-medibridge-900 sm:text-5xl">
                {labels.heroTitle}
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-lg text-slate-600">
                {labels.heroSubtitle}
              </p>

              <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
                <button
                  type="button"
                  onClick={() => setChooserOpen(true)}
                  className="btn-primary !px-6 !py-3 !text-base"
                >
                  {labels.heroStart}
                </button>
                <button
                  type="button"
                  onClick={() => setShowAuth(true)}
                  className="btn-secondary !px-6 !py-3 !text-base"
                >
                  {labels.signIn}
                </button>
                <button
                  type="button"
                  onClick={() => setChooserOpen(true)}
                  className="rounded-xl px-4 py-3 text-sm font-medium text-slate-500 underline-offset-4 hover:text-medibridge-700 hover:underline"
                >
                  {labels.heroSkip}
                </button>
              </div>

              <p className="mt-6 text-sm font-medium text-amber-700">
                {labels.heroTrust}
              </p>

              <div className="mx-auto mt-12 grid max-w-3xl grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="card !p-5">
                  <div className="mb-2 text-2xl" aria-hidden="true">📷</div>
                  <h3 className="font-semibold text-medibridge-900">{labels.feat1Title}</h3>
                  <p className="mt-1 text-sm text-slate-500">{labels.feat1Desc}</p>
                </div>
                <div className="card !p-5">
                  <div className="mb-2 text-2xl" aria-hidden="true">🗣️</div>
                  <h3 className="font-semibold text-medibridge-900">{labels.feat2Title}</h3>
                  <p className="mt-1 text-sm text-slate-500">{labels.feat2Desc}</p>
                </div>
                <div className="card !p-5">
                  <div className="mb-2 text-2xl" aria-hidden="true">🔊</div>
                  <h3 className="font-semibold text-medibridge-900">{labels.feat3Title}</h3>
                  <p className="mt-1 text-sm text-slate-500">{labels.feat3Desc}</p>
                </div>
              </div>

              <div className="mx-auto mt-12 max-w-xl text-left">
                <h3 className="text-center text-lg font-bold text-medibridge-900">{labels.howTitle}</h3>
                <ol className="mt-4 space-y-3">
                  {[labels.how1, labels.how2, labels.how3].map((step, i) => (
                    <li key={step} className="flex items-center gap-3 text-slate-700">
                      <span className="flex h-7 w-7 flex-none items-center justify-center rounded-full bg-medibridge-600 text-sm font-bold text-white">
                        {i + 1}
                      </span>
                      {step}
                    </li>
                  ))}
                </ol>
              </div>
            </section>
          </ErrorBoundary>
        )}

        {page === "analyze" && (
          <ErrorBoundary>
            {savedFlash && (
              <p className="mb-6 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
                ✓ {labels.savedFlash}
              </p>
            )}

            {!auth && (
              <p className="mb-6 rounded-xl border border-sky-200 bg-sky-50 px-4 py-2 text-sm text-sky-800">
                {labels.unsignedNote}
              </p>
            )}

            <p className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {isPrescription ? labels.rxDisclaimer : labels.disclaimer}
            </p>

            <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm font-medium text-slate-700">
                {labels.reportType}:{" "}
                <span className="font-semibold text-medibridge-700">
                  {isPrescription ? labels.rxType : labels.labType}
                </span>
              </p>
              <button
                type="button"
                onClick={() => setChooserOpen(true)}
                className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:border-medibridge-400"
              >
                {labels.changeType}
              </button>
            </div>

            {error && (
              <div
                role="alert"
                className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
              >
                {error}
              </div>
            )}

            {!results ? (
              <UploadZone
                language={language}
                docType={docType}
                title={isPrescription ? labels.rxTitle : labels.uploadTitle}
                onComplete={handleAnalysisComplete}
                onError={handleError}
              />
            ) : (
              <div className="space-y-6">
                {isPrescription ? (
                  <PrescriptionDashboard results={results} language={language} />
                ) : (
                  <>
                    {results.emergency_trigger && (
                      <div
                        role="alert"
                        className="rounded-2xl border border-red-300 bg-red-50 p-5 text-red-900"
                      >
                        <h2 className="text-lg font-semibold">{labels.emergencyTitle}</h2>
                        <p className="mt-2 text-sm">{labels.emergencyBody}</p>
                      </div>
                    )}

                    <Dashboard results={results} language={language} />
                  </>
                )}

                <div className="flex justify-center pt-2">
                  <button type="button" onClick={handleReset} className="btn-secondary">
                    {isPrescription ? labels.rxNewUpload : labels.newUpload}
                  </button>
                </div>
              </div>
            )}
          </ErrorBoundary>
        )}

        {page === "records" && (
          <ErrorBoundary>
            <h2 className="mb-6 text-2xl font-bold text-medibridge-900">
              {labels.navRecords}
            </h2>
            <HistoryPanel
              language={language}
              authHeaders={authHeaders}
              refreshKey={historyRefresh}
            />
          </ErrorBoundary>
        )}

        {showAuth && (
          <AuthModal
            language={language}
            onClose={() => setShowAuth(false)}
            onAuthed={{ login, signup }}
            onLogout={logout}
            onSuccess={() => setChooserOpen(true)}
          />
        )}

        {chooserOpen && (
          <ReportChooser
            language={language}
            onSelect={selectDocType}
            onClose={() => setChooserOpen(false)}
          />
        )}
      </main>

      <footer className="mx-auto max-w-5xl px-4 pb-10 text-center text-xs text-slate-500">
        MediBridge v1.0 — For educational support only. Not a substitute for professional medical advice.
      </footer>
    </div>
  );
}