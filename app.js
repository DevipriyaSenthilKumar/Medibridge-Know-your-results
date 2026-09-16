(function () {
  "use strict";

  var E = null; // OfflineEngine after data load

  var state = {
    lang: "en",
    lastColonText: null,
    lastRows: [],
    lastAnalysis: null
  };

  /* ---------- tiny helpers ---------- */
  var $ = function (id) { return document.getElementById(id); };
  function lsGet(k, d) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
  function lsSet(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode */ } }

  var STRINGS = {
    en: {
      dropText: "Tap to add a lab result photo", dropSub: "JPG / PNG / WEBP — a clear, close-up photo works best",
      ocrBusy: "Reading the photo…", analyzeBusy: "Analyzing the tests…",
      invalid: "We could not read that document. Please upload a clear photo of a full lab result sheet.",
      noRows: "We could not recognize any lab tests from that input. Try a closer photo, or type the values using “Type values”.",
      emergency: "Emergency words detected (e.g. chest pain, fainting). If you or the patient feels seriously unwell, seek urgent medical help now.",
      summary: "What this may mean", terms: "In simple words", details: "Test by test", questions: "3 questions to ask your doctor",
      steps: "What to do next", speak: "Speak", save: "Save to my records", saved: "Saved to your records.",
      trendTitle: "Trend for", clearErr: "No metric to track yet. Save at least one report."
    },
    hi: {
      dropText: "लैब रिपोर्ट की फोटो चुनें", dropSub: "JPG / PNG / WEBP — साफ़ और करीब से ली गई फोटो सबसे अच्छी होती है",
      ocrBusy: "फोटो पढ़ा जा रहा है…", analyzeBusy: "परीक्षणों का विश्लेषण किया जा रहा है…",
      invalid: "हम उस दस्तावेज़ को नहीं पढ़ सके। कृपया पूरी लैब रिपोर्ट शीट की साफ़ फोटो अपलोड करें।",
      noRows: "हम उस जानकारी से कोई लैब परीक्षण नहीं पहचान सके। करीब से फोटो लें, या 'Type values' में मान लिखें।",
      emergency: "आपातकालीन शब्द मिले (जैसे सीने में दर्द, बेहोशी)। अगर मरीज़ बहुत अस्वस्थ महसूस करता है, तो तुरंत चिकित्सकीय सहायता लें।",
      summary: "इसका क्या मतलब हो सकता है", terms: "सरल शब्दों में", details: "एक-एक कर परीक्षण", questions: "डॉक्टर से पूछने लायक 3 सवाल",
      steps: "आगे क्या करें", speak: "सुनें", save: "अपने रिकॉर्ड में सहेजें", saved: "आपके रिकॉर्ड में सहेज लिया गया।",
      trendTitle: "का रुझान", clearErr: "अभी कोई परीक्षण नहीं। कम से कम एक रिपोर्ट सहेजें।"
    },
    ta: {
      dropText: "லேப் அறிக்கை புகைப்படத்தைத் தேர்ந்தெடுக்கவும்", dropSub: "JPG / PNG / WEBP — தெளிவான, அருகிலிருந்து எடுத்த புகைப்படம் சிறந்தது",
      ocrBusy: "புகைப்படம் படிக்கப்படுகிறது…", analyzeBusy: "பரிசோதனைகள் ஆய்வு செய்யப்படுகின்றன…",
      invalid: "அந்த ஆவணத்தை எங்களால் படிக்க முடியவில்லை. முழு லேப் அறிக்கை தாளின் தெளிவான புகைப்படத்தை பதிவேற்றவும்.",
      noRows: "அந்த உள்ளீட்டில் இருந்து எந்த லேப் பரிசோதனையையும் அடையாளம் காண முடியவில்லை. நெருக்கமான புகைப்படம் எடுக்கவும் அல்லது 'Type values' இல் மதிப்புகளை உள்ளிடவும்.",
      emergency: "அவசர வார்த்தைகள் கண்டறியப்பட்டன (எ.கா. நெஞ்சு வலி, மயக்கம்). நோயாளி மிகவும் உடல்நிலை சரியில்லாமல் இருந்தால் உடனடி மருத்துவ உதவியை நாடுங்கள்.",
      summary: "இதன் பொருள் என்னவாக இருக்கலாம்", terms: "எளிய வார்த்தைகளில்", details: "ஒவ்வொரு சோதனையாக", questions: "மருத்துவரிடம் கேட்க 3 கேள்விகள்",
      steps: "அடுத்து என்ன செய்வது", speak: "கேட்க", save: "எனது பதிவுகளில் சேமிக்க", saved: "உங்கள் பதிவுகளில் சேமிக்கப்பட்டது.",
      trendTitle: "போக்கு", clearErr: "இன்னும் எந்த சோதனையும் இல்லை. குறைந்தது ஒரு அறிக்கையை சேமிக்கவும்."
    }
  };
  function T(name, lang) { lang = lang || state.lang; return STRINGS[lang][name] || STRINGS.en[name]; }

  function toast(msg) {
    var el = $("toast");
    el.textContent = msg;
    el.style.display = "block";
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { el.style.display = "none"; }, 2600);
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function statusChip(status) {
    var label = status;
    if (state.lang === "hi") label = { high: "अधिक", low: "कम", within_range: "सामान्य", unknown: "पढ़ नहीं पाए" }[status] || status;
    else if (state.lang === "ta") label = { high: "அதிகம்", low: "குறைவு", within_range: "சாதாரணம்", unknown: "படிக்க முடியவில்லை" }[status] || status;
    return '<span class="chip ' + esc(status) + '">' + esc(label) + "</span>";
  }

  /* ---------- language ---------- */
  var LANG_STORE = "mb_lang_v1";
  function detectLang() {
    var n = (navigator.language || "en").toLowerCase();
    if (n.indexOf("hi") === 0) return "hi";
    if (n.indexOf("ta") === 0) return "ta";
    return "en";
  }
  function setLang(lang) {
    state.lang = lang;
    $("lang").value = lang;
    lsSet(LANG_STORE, lang);
    if (state.lastColonText) try { renderAnalysis(analyzeColon(state.lastColonText)); } catch (e) { /* keep last */ }
  }

  /* ---------- analysis flow ---------- */
  function analyzeText(text) {
    var scrubbed = E.scrubPii(text);
    E.validateLabReportText(scrubbed);
    var rows = E.extractBiomarkerRows(scrubbed);
    if (!rows.length) throw new Error(T("noRows"));
    var colon = E.buildTypedText(rows);
    return analyzeColon(colon, rows);
  }

  function analyzeColon(colon, rowsOpt) {
    var analysis = E.mockAnalysisFromText(colon, state.lang);
    var rows = rowsOpt || E.extractBiomarkerRows(colon);
    return { analysis: analysis, rows: rows, colon: colon };
  }

  function renderAnalysis(payload) {
    var a = payload.analysis, rows = payload.rows;
    state.lastRows = rows;
    state.lastAnalysis = a;
    state.lastColonText = payload.colon;

    var html = "";
    html += '<div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px; flex-wrap:wrap;">';
    html += '<h2 style="margin-bottom:4px;">' + esc(T("summary")) + "</h2>";
    html += "<button class='btn btn-ghost' id='speakBtn'>🔊 " + esc(T("speak")) + "</button></div>";
    if (a.emergency_trigger) {
      html += '<div class="chip emo" style="display:block;">⚠️ ' + esc(T("emergency")) + "</div>";
    }
    html += '<p class="summary" id="summaryText">' + esc(a.report_summary) + "</p>";

    if (a.simplified_terms && a.simplified_terms.length) {
      html += '<h2 style="margin-top:14px;">' + esc(T("terms")) + "</h2>";
      a.simplified_terms.forEach(function (t) {
        html += '<div class="term"><b>' + esc(t.term) + "</b><br>" + esc(t.explanation) + "<br><i>" + esc(t.analogy) + "</i></div>";
      });
    }

    html += '<h2 style="margin-top:14px;">' + esc(T("details")) + "</h2>";
    a.numerical_context.forEach(function (ctx) {
      html += '<div class="metric"><div class="m-head"><span class="m-name">' + esc(ctx.metric) + "</span>" + statusChip(ctx.status) + "</div>";
      html += '<div class="m-vals">Value: <b>' + esc(ctx.value) + "</b> &nbsp;·&nbsp; Reference: <b>" + esc(ctx.normal_range) + "</b></div>";
      if (ctx.possible_causes) {
        html += '<div class="m-body"><span class="lbl">' + (state.lang === "hi" ? "संभावित कारण: " : state.lang === "ta" ? "சாத்தியமான காரணம்: " : "Possible cause: ") + "</span>" + esc(ctx.possible_causes) + "</div>";
      }
      if (ctx.possible_conditions && ctx.possible_conditions.length) {
        html += '<div class="cond-wrap">' + ctx.possible_conditions.map(function (c) { return '<span class="cond">' + esc(c) + "</span>"; }).join("") + "</div>";
      }
      if (ctx.doctor_guidance) {
        html += '<div class="m-body"><span class="lbl">💬 </span>' + esc(ctx.doctor_guidance) + "</div>";
      }
      html += '</div>';
    });

    html += '<h2 style="margin-top:14px;">' + esc(T("questions")) + "</h2>";
    a.doctor_questions.forEach(function (q, i) { html += '<div class="q">' + (i + 1) + ". " + esc(q) + "</div>"; });

    html += '<h2 style="margin-top:14px;">' + esc(T("steps")) + "</h2><ol class='steps'>";
    a.next_steps.forEach(function (s) { html += "<li>" + esc(s) + "</li>"; });
    html += "</ol>";

    html += '<div style="margin-top:14px; display:flex; gap:8px; flex-wrap:wrap;">';
    html += "<button class='btn btn-primary block' id='saveBtn'>💾 " + esc(T("save")) + "</button></div>";
    html += '<p class="small" style="margin-top:8px;">Read <b>' + esc(String(rows.length)) + "</b> tests from " + (state.lastInputKind === "type" ? "your typed values" : "the photo") + ".</p>";

    $("resCard").innerHTML = html;
    $("results").classList.remove("hidden");
    $("results").scrollIntoView({ behavior: "smooth", block: "start" });

    $("speakBtn").onclick = speakAnalysis;
    $("saveBtn").onclick = saveRecord;
  }

  /* ---------- TTS ---------- */
  function pickVoice(lang) {
    var want = { en: "en-IN", hi: "hi-IN", ta: "ta-IN" }[lang] || (lang + "-IN");
    var all = window.speechSynthesis ? speechSynthesis.getVoices() : [];
    var f = all.filter(function (v) { return v.lang && v.lang.replace("_", "-").toLowerCase() === want.toLowerCase(); });
    if (f.length) return f[0];
    var loose = all.filter(function (v) { return v.lang && v.lang.toLowerCase().indexOf(lang.toLowerCase().split("-")[0]) === 0; });
    if (loose.length) return loose[0];
    return all[0] || null;
  }

  function speakAnalysis() {
    if (!("speechSynthesis" in window) || !state.lastAnalysis) return;
    speechSynthesis.cancel();
    var a = state.lastAnalysis;
    var parts = [a.report_summary];
    a.numerical_context.forEach(function (c) {
      parts.push(c.metric + " value " + c.value + ". " + (state.lang === "en" ? "My normal range " + c.normal_range + ". Status " : "") + String(c.status).replace(/_/g, " "));
      if (c.possible_causes) parts.push(c.possible_causes);
    });
    a.doctor_questions.forEach(function (q) { parts.push(q); });
    var u = new SpeechSynthesisUtterance(parts.join(". "));
    u.lang = { en: "en-IN", hi: "hi-IN", ta: "ta-IN" }[state.lang] || "en-IN";
    var v = pickVoice(state.lang);
    if (v) u.voice = v;
    u.rate = 0.98;
    speechSynthesis.speak(u);
  }

  /* ---------- save / history / trend ---------- */
  function saveRecord() {
    if (!state.lastRows || !state.lastAnalysis) return;
    var rec = {
      id: Date.now(),
      date: new Date().toISOString(),
      lang: state.lang,
      rows: state.lastRows.map(function (r) { return { name: r.name, value: r.value, reference: r.reference, status: r.status }; }),
      summary: state.lastAnalysis.report_summary
    };
    var all = lsGet("mb_history_v1", []);
    all.unshift(rec);
    if (all.length > 50) all.length = 50;
    lsSet("mb_history_v1", all);
    toast(T("saved"));
    renderHistory();
  }

  function renderHistory() {
    var all = lsGet("mb_history_v1", []);
    var box = $("records");
    if (!all.length) { box.innerHTML = '<div class="empty">No saved reports yet.</div>'; return; }
    var names = {};
    all.forEach(function (r) { r.rows.forEach(function (m) { names[m.name] = true; }); });
    var sel = $("trendMetric");
    var cur = sel.value;
    var opts = Object.keys(names).sort();
    sel.innerHTML = '<option value="">' + (state.lang === "hi" ? "परीक्षण चुनें…" : state.lang === "ta" ? "சோதனையைத் தேர்ந்தெடுக்கவும்…" : "Select a test…") + "</option>" +
      opts.map(function (o) { return '<option value="' + esc(o) + '">' + esc(o) + "</option>"; }).join("");
    if (cur && opts.indexOf(cur) !== -1) sel.value = cur;
    renderTrend();

    box.innerHTML = all.map(function (r) {
      var d = new Date(r.date);
      var ds = d.toLocaleDateString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
      var vals = r.rows.map(function (m) { return '<span class="chip ' + esc(m.status) + '">' + esc(m.name) + " " + esc(m.value) + "</span>"; }).join("");
      return '<div class="record"><div class="r-head"><b>' + esc(ds) + "</b><a class='link' data-id='" + r.id + "'>" + (state.lang === "hi" ? "देखें" : state.lang === "ta" ? "பார்க்க" : "View") + "</a></div>" +
        '<div class="r-vals">' + vals + "</div></div>";
    }).join("");

    box.querySelectorAll(".link").forEach(function (el) {
      el.onclick = function () {
        var rec = lsGet("mb_history_v1", []).filter(function (x) { return String(x.id) === el.getAttribute("data-id"); })[0];
        if (!rec) return;
        var colon = E.buildTypedText(rec.rows.map(function (m) { var o = { name: m.name, value: m.value }; if (m.reference) o.reference = m.reference; return o; }));
        setLang(rec.lang); /* re-render in record language */
        setTimeout(function () { try { renderAnalysis(analyzeColon(colon)); } catch (e) { toast(e.message); } }, 30);
      };
    });
  }

  function renderTrend() {
    var mName = $("trendMetric").value;
    var box = $("trend");
    if (!mName) { box.classList.add("hidden"); return; }
    var all = lsGet("mb_history_v1", []);
    var hits = [];
    all.forEach(function (r) {
      r.rows.forEach(function (m) { if (m.name.toLowerCase() === mName.toLowerCase()) hits.push({ d: r.date, value: m.value, status: m.status }); });
    });
    if (!hits.length) { box.classList.add("hidden"); return; }
    box.classList.remove("hidden");
    var html = "<h2>" + esc(mName) + " — " + esc(T("trendTitle")) + "</h2>";
    hits.reverse().forEach(function (h) {
      var d = new Date(h.d);
      html += '<div style="display:flex; justify-content:space-between; gap:8px; border-bottom:1px solid var(--line); padding:6px 0; font-size:13.5px;">' +
        '<span>' + esc(d.toLocaleDateString(undefined, { day: "numeric", month: "short" })) + "</span>" +
        "<b>" + esc(h.value) + "</b>" + statusChip(h.status) + "</div>";
    });
    box.innerHTML = html;
  }

  /* ---------- photo (Tesseract OCR) ---------- */
  var worker = null;
  async function ensureWorker() {
    if (worker) { try { await worker.getParameters(); return worker; } catch (e) { worker = null; } }
    worker = await Tesseract.createWorker("eng", 1, {
      corePath: "vendor/core/tesseract-core-simd.wasm.js",
      langPath: "vendor/tessdata",
      workerPath: "vendor/worker.min.js",
      logger: function (m) {
        if (m.status === "recognizing text") setProgress(m.progress);
      }
    });
    await worker.setParameters({ tessedit_pageseg_mode: "6", preserve_interword_spaces: "0" });
    return worker;
  }

  function setProgress(f) {
    $("fill").style.width = Math.round(f * 100) + "%";
    $("pct").textContent = Math.round(f * 100) + "%";
  }

  function showProgress(on) { $("progress").classList.toggle("hidden", !on); if (on) setProgress(0); else setProgress(0); }

  async function ocrAnalyze(file) {
    try {
      E.rejectImagingDocument(file.name, file.type);
    } catch (err) {
      toast(err.message);
      return;
    }
    $("dropText").textContent = T("ocrBusy");
    $("drop").classList.add("busy");
    showProgress(true);
    try {
      var w = await ensureWorker();
      var { data } = await w.recognize(file);
      if (!data || !data.text || !data.text.trim()) throw new Error(T("invalid"));
      showProgress(false);
      var payload = analyzeText(data.text);
      state.lastInputKind = "photo";
      renderAnalysis(payload);
    } catch (err) {
      showProgress(false);
      var msg = (err && err.message && err.message.indexOf("Failed to dispatch") !== -1) ? T("ocrBusy") + " (" + (err.message || "worker error") + ")" : (err && err.message) || T("invalid");
      toast(msg);
    } finally {
      $("dropText").textContent = T("dropText");
      $("drop").classList.remove("busy");
    }
  }

  /* ---------- typed input ---------- */
  function rowTemplate() {
    var div = document.createElement("div");
    div.className = "rowfit";
    div.innerHTML =
      '<div><label class="lbl-sm">' + (state.lang === "hi" ? "परीक्षण का नाम" : state.lang === "ta" ? "சோதனை பெயர்" : "Test name") + '</label><input list="metricNames" class="t-name" placeholder="Hemoglobin"></div>' +
      '<div><label class="lbl-sm">' + (state.lang === "hi" ? "आपका मान" : state.lang === "ta" ? "உங்கள் மதிப்பு" : "Your value") + '</label><input class="t-value" placeholder="11.5"></div>' +
      '<div><label class="lbl-sm">' + (state.lang === "hi" ? "सामान्य सीमा" : state.lang === "ta" ? "சாதாரண வரம்பு" : "Ref range") + '</label><input class="t-ref" placeholder="11.5-15.5"></div>' +
      '<button class="del" title="Remove">&times;</button>';
    div.querySelector(".del").onclick = function () { div.remove(); };
    $("rows").appendChild(div);
  }

  function typedAnalyze() {
    var rowsEls = $("rows").querySelectorAll(".rowfit");
    var entries = [];
    rowsEls.forEach(function (rEl) {
      var name = rEl.querySelector(".t-name").value.trim();
      var value = rEl.querySelector(".t-value").value.trim();
      var ref = rEl.querySelector(".t-ref").value.trim();
      if (!name && !value) return;
      if (!name || !value) { toast(state.lang === "hi" ? "हर परीक्षण में नाम और मान भरें।" : state.lang === "ta" ? "ஒவ்வொரு சோதனையிலும் பெயரையும் மதிப்பையும் நிரப்பவும்." : "Fill both name and value for every row."); throw new Error("fill"); }
      var entry = { name: name, value: value };
      if (ref) entry.reference = ref;
      entries.push(entry);
    });
    if (!entries.length) { toast(state.lang === "hi" ? "कम से कम एक परीक्षण भरें।" : state.lang === "ta" ? "குறைந்தது ஒரு சோதனையை நிரப்பவும்." : "Add at least one test."); return; }
    var colon = E.buildTypedText(entries);
    var payload = analyzeColon(colon);
    state.lastInputKind = "type";
    renderAnalysis(payload);
  }

  /* ---------- tabs ---------- */
  function switchTab(tab) {
    ["photo", "type", "history"].forEach(function (t) {
      $("panel-" + t).classList.toggle("hidden", t !== tab);
      $("tabBtn" + t[0].toUpperCase() + t.slice(1)).classList.toggle("active", t === tab);
    });
    if (tab === "history") renderHistory();
  }

  /* ---------- init ---------- */
  function initLangSelect() {
    var sel = $("lang");
    sel.value = state.lang;
    sel.onchange = function () { setLang(sel.value); };
  }

  function fillMetricNames() {
    var dl = $("metricNames");
    var canon = E ? Object.keys(offlineMetaCanonical()) : [];
    dl.innerHTML = canon.map(function (c) { return '<option value="' + esc(c) + '">'; }).join("");
  }
  function offlineMetaCanonical() {
    var d = window.__MB_DATA__;
    return d ? d.canonical_biomarkers : {};
  }

  function bindEvents() {
    $("drop").onclick = function () { $("file").click(); };
    $("file").onchange = function () {
      var f = $("file").files[0];
      if (!f) return;
      var img = $("preview");
      if (/^image\//.test(f.type)) {
        img.src = URL.createObjectURL(f);
        img.hidden = false;
      }
      ocrAnalyze(f);
    };
    $("addRow").onclick = rowTemplate;
    $("multiAnalyze").onclick = typedAnalyze;
    $("clearHistory").onclick = function () {
      if (lsGet("mb_history_v1", []).length && confirm(state.lang === "hi" ? "सभी रिकॉर्ड हटाएं?" : state.lang === "ta" ? "அனைத்து பதிவுகளையும் நீக்கவா?" : "Delete all saved records?")) {
        localStorage.removeItem("mb_history_v1");
        renderHistory();
        $("trend").classList.add("hidden");
      }
    };
    $("trendMetric").onchange = renderTrend;
    document.querySelectorAll(".tabs button").forEach(function (b) {
      b.onclick = function () { switchTab(b.getAttribute("data-tab")); };
    });
    if ("speechSynthesis" in window) {
      speechSynthesis.getVoices(); /* warm */
      speechSynthesis.onvoiceschanged = function () { speechSynthesis.getVoices(); };
    }
  }

  function initData() {
    return fetch("engine-data.json", { cache: "reload" })
      .then(function (r) { if (!r.ok) throw new Error("engine-data"); return r.json(); })
      .then(function (d) {
        window.__MB_DATA__ = d;
        E = window.OfflineEngine;
        E.setData(d);
        fillMetricNames();
      });
  }

  function initSW() {
    if ("serviceWorker" in navigator && location.protocol === "https:") {
      navigator.serviceWorker.register("sw.js", { scope: "./" }).catch(function (e) { console.warn("SW:", e); });
    }
  }

  (function boot() {
    state.lang = lsGet(LANG_STORE, detectLang());
    initLangSelect();
    bindEvents();
    rowTemplate();
    initData().then(function () {
      /* prime trend select */
      renderHistory();
    }).catch(function (e) {
      toast("Could not load engine data: " + e.message);
    });
    initSW();
  })();
})();