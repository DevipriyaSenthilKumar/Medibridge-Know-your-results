import { useState } from "react";

const LABELS = {
  en: {
    signIn: "Sign in",
    createAccount: "Create account",
    email: "Email",
    password: "Password (min 6 chars)",
    submit: "Continue",
    switchToSignup: "New here? Create an account",
    switchToLogin: "Already have an account? Sign in",
    welcome: "Welcome back",
    logout: "Log out",
    error: "Something went wrong. Please try again.",
    saving: "Your reports are saved so you can see changes over time.",
  },
  hi: {
    signIn: "साइन इन करें",
    createAccount: "नया खाता बनाएं",
    email: "ईमेल",
    password: "पासवर्ड (कम से कम 6 अक्षर)",
    submit: "जारी रखें",
    switchToSignup: "नए हैं? खाता बनाएं",
    switchToLogin: "पहले से खाता है? साइन इन करें",
    welcome: "वापसी पर स्वागत है",
    logout: "लॉग आउट",
    error: "कुछ गलत हो गया। कृपया पुनः प्रयास करें।",
    saving: "आपकी रिपोर्ट सहेजी जाती हैं ताकि आप समय के साथ बदलाव देख सकें।",
  },
  ta: {
    signIn: "உள்நுழைக",
    createAccount: "கணக்கை உருவாக்கு",
    email: "மின்னஞ்சல்",
    password: "கடவுச்சொல் (குறைந்தது 6 எழுத்துகள்)",
    submit: "தொடரவும்",
    switchToSignup: "புதியவரா? கணக்கை உருவாக்கவும்",
    switchToLogin: "ஏற்கனவே கணக்கு உள்ளதா? உள்நுழைக",
    welcome: "மீண்டும் வரவேற்கிறோம்",
    logout: "வெளியேறு",
    error: "ஏதோ பிழை ஏற்பட்டது. மீண்டும் முயற்சிக்கவும்.",
    saving: "உங்கள் அறிக்கைகள் சேமிக்கப்படுகின்றன, காலப்போக்கில் மாற்றங்களைக் காணலாம்.",
  },
};

export default function AuthModal({ language, onClose, onAuthed, auth, onLogout, onSuccess }) {
  const labels = LABELS[language] || LABELS.en;
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const fn = mode === "login" ? onAuthed.login : onAuthed.signup;
      await fn(email, password);
      onSuccess && onSuccess();
      onClose();
    } catch (e) {
      setError(e.message || labels.error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <h2 className="text-xl font-bold text-medibridge-900">
          {mode === "login" ? labels.signIn : labels.createAccount}
        </h2>
        <p className="mt-1 text-sm text-slate-500">{labels.saving}</p>

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700">{labels.email}</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-medibridge-500 focus:outline-none focus:ring-2 focus:ring-medibridge-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">{labels.password}</label>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-medibridge-500 focus:outline-none focus:ring-2 focus:ring-medibridge-500"
            />
          </div>

          {error && (
            <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-xl bg-medibridge-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-medibridge-700 disabled:opacity-50"
          >
            {busy ? "…" : labels.submit}
          </button>
        </form>

        <button
          type="button"
          onClick={() => {
            setMode(mode === "login" ? "signup" : "login");
            setError("");
          }}
          className="mt-4 text-sm font-medium text-medibridge-600 hover:underline"
        >
          {mode === "login" ? labels.switchToSignup : labels.switchToLogin}
        </button>
      </div>
    </div>
  );
}