import { useCallback, useEffect, useState } from "react";
import { localizedMetric } from "../translations";
import Dashboard from "./Dashboard.jsx";
import PrescriptionDashboard from "./PrescriptionDashboard.jsx";

const LABELS = {
  en: {
    empty: "No saved reports yet. Upload a report while signed in to start your history.",
    load: "History isn't available offline. Connected to the internet, sign in and try again.",
    view: "View",
    close: "Close",
    trends: "Changes vs your last report",
    noTrend: "First saved report — no previous data to compare.",
    refreshed: "This report was saved automatically after analysis.",
    prescription: "Prescription",
    lab: "Lab report",
    trendDecrease: "down",
    trendIncrease: "up",
  },
  hi: {
    empty: "अभी कोई सहेजी गई रिपोर्ट नहीं है। अपना इतिहास शुरू करने के लिए साइन इन करके रिपोर्ट अपलोड करें।",
    load: "ऑफ़लाइन इतिहास उपलब्ध नहीं है। इंटरनेट से जुड़े रहें, साइन इन करें और फिर से कोशिश करें।",
    view: "देखें",
    close: "बंद करें",
    trends: "आपकी पिछली रिपोर्ट की तुलना में बदलाव",
    noTrend: "पहली सहेजी गई रिपोर्ट — तुलना के लिए कोई पिछला डेटा नहीं।",
    refreshed: "विश्लेषण के बाद यह रिपोर्ट स्वतः सहेजी गई।",
    prescription: "दवा पर्ची",
    lab: "लैब रिपोर्ट",
    trendDecrease: "कम",
    trendIncrease: "अधिक",
  },
  ta: {
    empty: "இன்னும் சேமித்த அறிக்கைகள் இல்லை. உள்நுழைந்து ஒரு அறிக்கையைப் பதிவேற்றவும், உங்கள் வரலாறு தொடங்கும்.",
    load: "ஆஃப்லைனில் வரலாறு கிடைக்காது. இணையத்துடன் இணைத்து உள்நுழைந்து மீண்டும் முயற்சிக்கவும்.",
    view: "பார்க்க",
    close: "மூடு",
    trends: "உங்கள் கடந்த அறிக்கையுடன் ஒப்பிடும்போது மாற்றங்கள்",
    noTrend: "முதல் சேமித்த அறிக்கை — ஒப்பிட முந்தைய தரவு இல்லை.",
    refreshed: "பகுப்பாய்வு செய்த பிறகு இந்த அறிக்கை தானாகச் சேமிக்கப்பட்டது.",
    prescription: "மருந்து பரிந்துரை",
    lab: "ஆய்வக அறிக்கை",
    trendDecrease: "குறைந்தது",
    trendIncrease: "அதிகரித்தது",
  },
};

function TrendRow({ previous, current, language, labels }) {
  if (!previous?.analysis) {
    return (
      <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-500">
        {labels.noTrend}
      </p>
    );
  }
  const map = { previous: previous.analysis, current: current.analysis };
  const prev = map.previous?.numerical_context || [];
  const cur = map.current?.numerical_context || [];
  const byPrev = {};
  prev.forEach((p) => (byPrev[p.metric] = p.value));
  const shared = cur.filter((c) => byPrev[c.metric] !== undefined && c.value !== "Could not read");

  if (!shared.length) return <p className="text-sm text-slate-500">{labels.noTrend}</p>;

  const deltaSigned = (prevStr, curl) => {
    const a = parseFloat(prevStr);
    const b = parseFloat(curl);
    if (Number.isNaN(a) || Number.isNaN(b)) return null;
    return +(b - a).toFixed(2);
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
            <th className="py-2 pr-3">{labels.view}</th>
            <th className="py-2 pr-3">Previous</th>
            <th className="py-2 pr-3">Now</th>
            <th className="py-2">Change</th>
          </tr>
        </thead>
        <tbody>
          {shared.map((c) => {
            const prevVal = byPrev[c.metric];
            const delta = deltaSigned(prevVal, c.value);
            const isUp = delta && delta > 0;
            const isDown = delta && delta < 0;
            return (
              <tr key={c.metric} className="border-b border-slate-100">
                <td className="py-2 pr-3 font-medium text-medibridge-800">
                  {localizedMetric(c.metric, language)}
                </td>
                <td className="py-2 pr-3 text-slate-600">{prevVal}</td>
                <td className="py-2 pr-3 text-slate-900">{c.value}</td>
                <td className="py-2 text-slate-700">
                  {delta === null ? (
                    "—"
                  ) : (
                    <span className={isUp ? "text-red-700" : isDown ? "text-emerald-700" : "text-slate-500"}>
                      {isUp ? "▲" : isDown ? "▼" : "•"} {delta > 0 ? "+" : ""}
                      {delta}{" "}
                      {isUp
                        ? labels.trendIncrease
                        : isDown
                          ? labels.trendDecrease
                          : "same"}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function HistoryPanel({ language, authHeaders, refreshKey = 0 }) {
  const labels = LABELS[language] || LABELS.en;
  const [reports, setReports] = useState([]);
  const [msg, setMsg] = useState("");
  const [openIds, setOpenIds] = useState({});
  const [loading, setLoading] = useState(false);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setMsg("");
    try {
      const res = await fetch("/api/history", {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: "{}",
      });
      if (!res.ok) throw new Error("load");
      const data = await res.json();
      setReports(data.reports || []);
    } catch {
      setMsg(labels.load);
    } finally {
      setLoading(false);
    }
  }, [authHeaders, labels]);

  useEffect(() => {
    if (authHeaders().Authorization) loadHistory();
  }, [authHeaders, loadHistory, refreshKey]);

  const toggle = async (id, kind, lang) => {
    if (openIds[id]) {
      setOpenIds((m) => {
        const next = { ...m };
        delete next[id];
        return next;
      });
      return;
    }
    try {
      const res = await fetch(`/api/history/${id}`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: "{}",
      });
      if (!res.ok) throw new Error("load");
      const data = await res.json();
      setOpenIds((m) => ({ ...m, [id]: data }));
    } catch {
      setMsg(labels.load);
    }
  };

  if (loading) return <p className="text-sm text-slate-500">…</p>;
  if (!authHeaders().Authorization) {
    return (
      <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        {labels.load}
      </p>
    );
  }

  return (
    <section className="card space-y-2">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-medibridge-900">My history</h2>
        {msg && <span className="text-xs text-amber-700">{msg}</span>}
      </div>

      {reports.length === 0 ? (
        <p className="text-sm text-slate-500">{labels.empty}</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {reports.map((r) => (
            <li key={r.id} className="py-2">
              <button
                type="button"
                onClick={() => toggle(r.id, r.kind, r.language)}
                className="flex w-full items-center justify-between gap-3 text-left"
              >
                <span className="flex min-w-0 flex-col">
                  <span className="truncate text-sm font-medium text-medibridge-800">
                    {r.kind === "prescription" ? labels.prescription : labels.lab}
                  </span>
                  <span className="text-xs text-slate-400">
                    {new Date(r.created_at).toLocaleString()}
                  </span>
                </span>
                <span className="text-xs font-semibold text-medibridge-600">
                  {openIds[r.id] ? labels.close : labels.view}
                </span>
              </button>
              {openIds[r.id] && (
                <div className="mt-3 rounded-xl border border-slate-100 bg-slate-50/50 p-3 space-y-3">
                  {r.kind === "lab" && (
                    <TrendRow
                      previous={openIds[r.id].previous}
                      current={{ analysis: openIds[r.id].report.analysis }}
                      language={language}
                      labels={{
                        view: labels.lab,
                        noTrend: labels.noTrend,
                        trendIncrease: labels.trendIncrease,
                        trendDecrease: labels.trendDecrease,
                      }}
                    />
                  )}
                  {r.kind === "lab" ? (
                    <Dashboard
                      results={openIds[r.id].report.analysis}
                      language={openIds[r.id].report.language || language}
                    />
                  ) : (
                    <PrescriptionDashboard
                      results={openIds[r.id].report.analysis}
                      language={openIds[r.id].report.language || language}
                    />
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}