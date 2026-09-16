/* MediBridge Offline Engine — faithful JS port of the Python pipeline.
   Loads engine-data.json (generated from the backend knowledge base) and
   re-implements biomarker extraction + the U.I.P. mock analysis entirely
   in the browser. No network, no server, no API keys. */
(function (global) {
  "use strict";

  var DATA = null;
  function setData(d) { DATA = d; }

  /* ---------- regex helpers (Python re -> JS) ---------- */
  var FLAG_I = 2, FLAG_M = 8, FLAG_S = 16;
  function makeFlags(spec, extra) {
    extra = extra || "";
    var f = [];
    if (extra.indexOf("g") !== -1) f.push("g");
    if (spec.flags & FLAG_I) f.push("i");
    if (spec.flags & FLAG_M) f.push("m");
    if (spec.flags & FLAG_S) f.push("s");
    return f.join("");
  }
  function reFrom(spec, extra) {
    return new RegExp(spec.pattern, makeFlags(spec, extra || ""));
  }
  /* Python re.search semantics (scan, not anchored) */
  function search(spec, str) {
    var r = reFrom(spec);
    return r.exec(str);
  }
  /* Python re.match semantics (anchored at start) */
  function match(spec, str) {
    var r = new RegExp("^(?:" + spec.pattern + ")", makeFlags(spec));
    var m = r.exec(str);
    return m;
  }
  /* iterate all matches like re.finditer */
  function findIter(spec, str) {
    var r = reFrom(spec, "g");
    var out = [], m;
    r.lastIndex = 0;
    while ((m = r.exec(str)) !== null) {
      out.push({ match: m, index: m.index });
      if (m[0].length === 0) r.lastIndex++;
    }
    return out;
  }

  /* ---------- LCS-based similarity (stands in for difflib ratio) ---------- */
  function lcsLen(a, b) {
    var n = a.length, m = b.length;
    var prev = new Array(m + 1).fill(0), cur = new Array(m + 1).fill(0);
    for (var i = 1; i <= n; i++) {
      for (var j = 1; j <= m; j++) {
        cur[j] = (a[i - 1] === b[j - 1]) ? prev[j - 1] + 1 : Math.max(prev[j], cur[j - 1]);
      }
      var t = prev; prev = cur; cur = t;
      cur[0] = 0;
    }
    return prev[m];
  }
  function seqRatio(a, b) {
    var n = a.length + b.length;
    if (n === 0) return 1.0;
    return (2 * lcsLen(a, b)) / n;
  }

  function _canonicalKey(raw) { return raw.toLowerCase().replace(/[^a-z0-9]/g, ""); }

  function _cleanName(name) { return name.replace(/\s+/g, " ").replace(/^[\s:=*-]+|[\s:=*-]+$/g, "").trim(); }

  /* ---------- ADMIN / filtering ---------- */
  function _isAdminLine(line) {
    var stripped = line.trim();
    if (!stripped || stripped.length < 3) return true;
    var admin = DATA.admin_line_patterns;
    for (var i = 0; i < admin.length; i++) {
      if (search(admin[i], stripped)) return true;
    }
    var lowered = _cleanName(stripped).toLowerCase();
    if (DATA.admin_metric_names.indexOf(lowered) !== -1) return true;
    if (/^(investigation|result|reference|test name|parameter)\s*$/i.test(stripped)) return false;
    return false;
  }

  function normalizeBiomarkerName(rawName) {
    var cleaned = _cleanName(rawName);
    if (!cleaned) return cleaned;
    var lowered = cleaned.toLowerCase();
    var canon = DATA.canonical_biomarkers;
    for (var key in canon) {
      if (lowered === key.toLowerCase()) return key;
      var aliases = canon[key];
      for (var a = 0; a < aliases.length; a++) {
        if (lowered === aliases[a]) return key;
      }
    }
    var bestName = cleaned, bestScore = 0.55;
    for (var key2 in canon) {
      var score = seqRatio(key2.toLowerCase(), lowered);
      if (score > bestScore) { bestScore = score; bestName = key2; }
    }
    return bestName;
  }

  function _buildKnownNames() {
    var names = {};
    var canon = DATA.canonical_biomarkers;
    for (var key in canon) {
      names[key.toLowerCase()] = true;
      var aliases = canon[key];
      for (var a = 0; a < aliases.length; a++) names[aliases[a]] = true;
    }
    return names;
  }
  var _KNOWN_NAMES = null;
  function knownNames() { if (!_KNOWN_NAMES) _KNOWN_NAMES = _buildKnownNames(); return _KNOWN_NAMES; }

  function isRecognizedBiomarker(rawName) {
    var cleaned = _cleanName(rawName);
    if (!cleaned) return false;
    var lowered = cleaned.toLowerCase();
    if (knownNames()[lowered]) return true;
    return normalizeBiomarkerName(cleaned).toLowerCase() !== lowered;
  }

  /* ---------- value helpers ---------- */
  function _parseNumeric(valueStr) {
    var m = /([\d.]+)/.exec(valueStr.replace(/,/g, ""));
    if (!m) return null;
    var n = parseFloat(m[1]);
    return isNaN(n) ? null : n;
  }

  function _splitGluedValue(valueStr) {
    valueStr = valueStr.trim();
    valueStr = valueStr.replace(/^[^\w.\d+]+/, "");
    var pats = DATA.extractor_patterns;
    var mt = search(pats.sci_unit, valueStr);
    if (!mt) mt = search(pats.sci_unit_degenerate, valueStr);
    if (mt && mt.index > 0) return valueStr.slice(0, mt.index).trim();
    return valueStr;
  }

  function _normalizeSciUnit(line) {
    var pats = DATA.extractor_patterns;
    var a = reFrom(pats.sci_unit, "g");
    line = line.replace(a, " $1");
    var b = reFrom(pats.sci_unit_degenerate, "g");
    return line.replace(b, " $1");
  }

  function _cleanReference(raw) {
    var text = (raw || "").trim().replace(/^[()\[\]\s\t.\n]+|[()\[\]\s\t.\n]+$/g, "");
    if (!text) return "See lab report";
    var pats = DATA.extractor_patterns;
    var labelled = search(pats.inline_range, text);
    if (labelled) return (labelled[1] || "").trim();
    var numeric = search(pats.generic_range, text);
    if (numeric) return ((numeric[1] || "").trim() + "-" + numeric[2]).trim();
    var single = search(pats.single_value, text);
    if (single) return single[0].trim();
    return text;
  }

  function _parseReferenceBounds(reference) {
    reference = reference.trim();
    var rl = reference.toLowerCase();
    if (!reference || rl === "see your lab report" || rl === "n/a" || reference === "-") {
      return [null, null, null];
    }
    var lt = /^<\s*([\d.]+)/.exec(reference);
    if (lt) return [null, parseFloat(lt[1]), "less_than"];
    var gt = /^>\s*([\d.]+)/.exec(reference);
    if (gt) return [parseFloat(gt[1]), null, "greater_than"];
    var rm = /([\d.]+)\s*[-–—]\s*([\d.]+)/.exec(reference);
    if (rm) return [parseFloat(rm[1]), parseFloat(rm[2]), "range"];
    return [null, null, null];
  }

  function _compareToReference(valueStr, reference) {
    var value = _parseNumeric(valueStr);
    if (value === null) return "unknown";
    var b = _parseReferenceBounds(reference);
    var low = b[0], high = b[1], type = b[2];
    if (type === "less_than" && high !== null) return value >= high ? "high" : "within_range";
    if (type === "greater_than" && low !== null) return value <= low ? "low" : "within_range";
    if (type === "range" && low !== null && high !== null) {
      if (value < low) return "low";
      if (value > high) return "high";
      return "within_range";
    }
    return "unknown";
  }

  function _isPlausibleValue(canonical, valueStr) {
    var numeric = _parseNumeric(valueStr);
    if (numeric === null) return false;
    var bounds = DATA.value_plausible[canonical];
    if (!bounds) return numeric > 0;
    return numeric >= bounds[0] && numeric <= bounds[1];
  }

  function _candidateJunk(value) {
    var ok = new Set("0123456789.,x^/uLdlmgk% -+µ".split(""));
    var n = 0;
    for (var i = 0; i < value.length; i++) if (!ok.has(value[i])) n++;
    return n;
  }

  function _detectByShortcode(line) {
    var head = /^([A-Za-z][A-Za-z0-9#\-#]*)/.exec(line.trim());
    if (!head) return null;
    var token = head[0].toLowerCase();
    return DATA.shortcode_to_canonical[token] || null;
  }

  /* ---------- main extraction ---------- */
  function extractBiomarkerRows(text) {
    var rows = {};           // key -> row
    var seenScores = {};     // key -> score tuple
    var adminNames = DATA.admin_metric_names;
    var pats = DATA.extractor_patterns;
    var lines = text.split("\n");

    for (var li = 0; li < lines.length; li++) {
      var rawLine = lines[li];
      if (_isAdminLine(rawLine)) continue;
      var line = _normalizeSciUnit(rawLine);

      var colonMatch = search(pats.metric_value, line);
      var tableMatch = match(pats.biomarker_line, line);

      var yieldName = null, yieldValue = null, yieldReference = null;

      if (tableMatch) {
        yieldName = normalizeBiomarkerName(tableMatch[1]);
        yieldValue = _splitGluedValue(tableMatch[2]);
        yieldReference = _cleanReference(tableMatch[3]);
      } else if (colonMatch) {
        yieldName = normalizeBiomarkerName(colonMatch[1]);
        yieldValue = _splitGluedValue(colonMatch[2]);
        yieldReference = _cleanReference(colonMatch[3]);
        if (!yieldReference || yieldReference === "See lab report") {
          yieldReference = _cleanReference(line);
        }
      } else {
        yieldName = _detectByShortcode(line);
        if (yieldName === null) continue;
        yieldValue = null;
        yieldReference = null;
      }

      var name = yieldName;
      if (!name || name.length < 2) continue;
      if (adminNames.indexOf(name.toLowerCase()) !== -1) continue;
      if (!isRecognizedBiomarker(name)) continue;

      var key = name.toLowerCase();
      var candidate, score;

      if (yieldValue === null || !/\d/.test(yieldValue)) {
        candidate = { name: name, value: "Could not read", reference: yieldReference || "See your lab report", status: "unknown" };
        score = [0, 0];
      } else {
        var status = _compareToReference(yieldValue, yieldReference);
        if (!_isPlausibleValue(name, yieldValue)) {
          candidate = { name: name, value: "Could not read", reference: yieldReference || "See your lab report", status: "unknown" };
          score = [0, 0];
        } else {
          candidate = { name: name, value: yieldValue, reference: yieldReference, status: status };
          score = [1, -_candidateJunk(yieldValue)];
        }
      }

      if (!(key in rows) || score[0] > seenScores[key][0] || (score[0] === seenScores[key][0] && score[1] > seenScores[key][1])) {
        rows[key] = candidate;
        seenScores[key] = score;
      }
    }

    var result = [];
    for (var k in rows) result.push(rows[k]);

    if (result.length < 2) {
      var iter = findIter(pats.metric_value, text);
      for (var it = 0; it < iter.length; it++) {
        var entry = iter[it];
        var mm = entry.match;
        var nm = normalizeBiomarkerName(mm[1]);
        if (adminNames.indexOf(nm.toLowerCase()) !== -1) continue;
        if (nm.toLowerCase() in rows) continue;
        if (!isRecognizedBiomarker(nm)) continue;
        var v = (mm[2] || "").trim();
        if (!/\d/.test(v)) continue;
        var lineEnd = text.indexOf("\n", entry.index + mm[0].length);
        var sliceEnd = lineEnd !== -1 ? lineEnd : entry.index + mm[0].length + 120;
        var lineSlice = text.slice(entry.index, Math.min(sliceEnd, text.length));
        var ref = _cleanReference(lineSlice);
        if (ref === "See lab report") ref = _cleanReference(mm[0]);
        rows[nm.toLowerCase()] = {
          name: nm,
          value: v,
          reference: ref,
          status: _compareToReference(v, ref)
        };
      }
      result = [];
      for (var k2 in rows) result.push(rows[k2]);
    }

    return result;
  }

  /* ---------- U.I.P. analysis (mirrors uip_framework mock path) ---------- */
  function _cleanMetricName(name) { return name.replace(/\s+/g, " ").replace(/^[ \-*]+|[ \-*]+$/g, "").trim(); }

  function parseLabMetrics(scrubbedText) {
    var metrics = [];
    var seen = {};
    var pap = DATA.uip.metric_pattern;
    var irp = DATA.uip.inline_range_pattern;
    var iter = findIter(pap, scrubbedText);
    for (var i = 0; i < iter.length; i++) {
      var entry = iter[i];
      var m = entry.match;
      var metric = _cleanMetricName(m[1]);
      var value = (m[2] || "").trim();
      if (!metric || metric.length < 2) continue;
      if (!isRecognizedBiomarker(metric)) continue;
      var key = metric.toLowerCase();
      if (seen[key]) continue;
      seen[key] = true;

      var lineEnd = scrubbedText.indexOf("\n", entry.index + m[0].length);
      var sliceEnd = lineEnd !== -1 ? lineEnd : entry.index + m[0].length + 120;
      var lineSlice = scrubbedText.slice(entry.index, Math.min(sliceEnd, scrubbedText.length));
      var rm = search(irp, lineSlice);
      var normalRange = rm ? rm[1].trim() : "See your lab report";

      if (normalRange && !/^\d/.test(normalRange)) {
        var num = /(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)/.exec(normalRange);
        if (num) normalRange = num[1] + "-" + num[2];
      }

      metrics.push([metric, value, normalRange]);
    }
    return metrics;
  }

  function _extractNumber(text) {
    var m = /-?\d+(?:\.\d+)?/.exec(text.replace(/,/g, ""));
    if (!m) return null;
    var n = parseFloat(m[0]);
    return isNaN(n) ? null : n;
  }

  function _parseRangeNumbers(normalRange) {
    var lt = /^<\s*([\d.]+)/.exec(normalRange);
    if (lt) return [null, parseFloat(lt[1])];
    var gt = /^>\s*([\d.]+)/.exec(normalRange);
    if (gt) return [parseFloat(gt[1]), null];
    var rm = /([\d.]+)\s*[-–—~]\s*([\d.]+)/.exec(normalRange);
    if (rm) return [parseFloat(rm[1]), parseFloat(rm[2])];
    return [null, null];
  }

  function compareValueToRange(valueStr, normalRange) {
    var num = _extractNumber(valueStr);
    if (num === null) return "unknown";
    var r = _parseRangeNumbers(normalRange);
    if (r[0] === null || r[1] === null) return "within_range";
    if (num < r[0]) return "low";
    if (num > r[1]) return "high";
    return "within_range";
  }

  function _conditionTerms(ids, language) {
    var out = [];
    var terms = DATA.uip.condition_terms;
    for (var i = 0; i < ids.length; i++) {
      var t = terms[ids[i]];
      if (!t) continue;
      out.push(t[language] || t.en || ids[i]);
    }
    return out;
  }

  function possibleConditionsFor(metric, status, language) {
    var key = metric.toLowerCase();
    var pc = DATA.uip.possible_conditions;
    var ids = (pc[key] || {})[status];
    if (ids && ids.length) return _conditionTerms(ids, language);
    for (var ek in pc) {
      if (key.indexOf(ek) !== -1 || ek.indexOf(key) !== -1) {
        ids = (pc[ek] || {})[status];
        if (ids && ids.length) return _conditionTerms(ids, language);
      }
    }
    return [];
  }

  function getClinicalHint(metric, status, language) {
    var key = metric.toLowerCase();
    var hints = DATA.uip.clinical_hints;
    var lang = language;
    if (lang !== "en" && lang !== "hi" && lang !== "ta") lang = "en";

    var exact = (hints[key] || {})[status];
    if (exact) {
      var v = exact[lang] || exact["en"] || ["", ""];
      if (v[0]) return v;
    }
    for (var ek in hints) {
      if (key.indexOf(ek) !== -1 || ek.indexOf(key) !== -1) {
        var variant = (hints[ek] || {})[status];
        if (variant) {
          var vv = variant[lang] || variant["en"] || ["", ""];
          if (vv[0]) return vv;
        }
      }
    }
    var generic = {
      en: ["A " + status.replace(/_/g, " ") + " result may be a sign worth understanding — your doctor can explain it best.",
           "Ask your doctor what this result means for you and whether any follow-up test is needed. Do not start or stop medicines yourself."],
      hi: [metric + " का परिणाम समझने लायक हो सकता है — आपका डॉक्टर इसे सबसे अच्छे से समझाएगा।",
           "अपने डॉक्टर से पूछें कि इसका क्या मतलब है और क्या अनुवर्ती जांच जरूरी है। बिना सलाह दवा शुरू या बंद न करें।"],
      ta: [metric + " முடிவு புரிந்து கொள்ள வேண்டியதாக இருக்கலாம் — உங்கள் மருத்துவர் சிறப்பாக விளக்குவார்.",
           "இது என்ன அர்த்தம் மற்றும் மேலும் பரிசோதனை தேவையா என மருத்துவரிடம் கேளுங்கள். மருந்தை நீங்களே தொடங்கவோ நிறுத்தவோ வேண்டாம்."]
    };
    return generic[lang] || generic["en"];
  }

  function _metricGroup(metric) {
    var m = metric.toLowerCase();
    if (/(hemoglobin|haemoglobin| hb|packed cell|pcv|corpuscular|rbc)/.test(m)) return "anemia";
    if (/(white blood|wbc|neutrophil|leukocyte)/.test(m)) return "infection";
    if (/(glucose|sugar|hba1c)/.test(m)) return "diabetes";
    if (/(cholesterol|triglyceride|ldl|hdl)/.test(m)) return "lipids";
    if (/(tsh|thyroid)/.test(m)) return "thyroid";
    if (/(creatinine|urea|bun|uric acid)/.test(m)) return "kidney";
    if (/platelet/.test(m)) return "platelets";
    return null;
  }

  function _buildMockOverallPrediction(parsed, statuses, language) {
    var scores = {};
    var overallHints = DATA.uip.overall_hints;
    for (var i = 0; i < parsed.length; i++) {
      var metric = parsed[i][0], status = statuses[i];
      var group = _metricGroup(metric);
      if (!group || status === "within_range") continue;
      if (group === "anemia" && status === "low") scores["anemia"] = (scores["anemia"] || 0) + 1;
      else if (group === "infection" && status === "high") scores["infection"] = (scores["infection"] || 0) + 1;
      else if (group === "diabetes" && status === "high") scores["diabetes"] = (scores["diabetes"] || 0) + 1;
      else if (group === "lipids" && (status === "high" || (metric.toLowerCase().indexOf("hdl") === 0 && status === "low"))) scores["lipids"] = (scores["lipids"] || 0) + 1;
      else if (group === "thyroid") {
        if (status === "high") scores["thyroid-high"] = (scores["thyroid-high"] || 0) + 1;
        else if (status === "low") scores["thyroid-low"] = (scores["thyroid-low"] || 0) + 1;
      }
      else if (group === "kidney" && status === "high") scores["kidney"] = (scores["kidney"] || 0) + 1;
      else if (group === "platelets") {
        if (status === "low") scores["platelets-low"] = (scores["platelets-low"] || 0) + 1;
        else if (status === "high") scores["platelets-high"] = (scores["platelets-high"] || 0) + 1;
      }
    }
    var keys = Object.keys(scores);
    if (!keys.length) {
      if (statuses.indexOf("unknown") !== -1) {
        return language === "hi"
          ? "कुल मिलाकर, हम जिन मानों को पढ़ सके वे सामान्य सीमा के भीतर दिख रहे हैं, लेकिन हम हर परीक्षण को स्पष्ट रूप से नहीं पढ़ सके — कृपया पूरी रिपोर्ट डॉक्टर से पुष्टि करवाएं।"
          : language === "ta"
          ? "ஒட்டுமொத்தமாக, நாங்கள் படிக்கக் கூடிய மதிப்புகள் சாதாரண வரம்பிற்குள் உள்ளன, ஆனால் ஒவ்வொரு சோதனையையும் தெளிவாக படிக்க முடியவில்லை — முழு அறிக்கையையும் மருத்துவரிடம் உறுதிப்படுத்தவும்."
          : "Overall, the values we could read look like they are inside the typical range, but we couldn't clearly read every test — please verify the full report with your doctor.";
      }
      return language === "hi"
        ? "समग्र रूप से, आपके दर्ज मान सामान्य सीमा के भीतर दिख रहे हैं — कोई स्पष्ट चेतावनी पैटर्न नहीं मिला।"
        : language === "ta"
        ? "ஒட்டுமொத்தமாக, உங்கள் மதிப்புகள் சாதாரண வரம்பிற்குள் உள்ளன — தெளிவான எச்சரிக்கை முறை எதுவும் கண்டறியப்படவில்லை."
        : "Overall, the values you entered look like they are inside the typical range — no clear warning pattern was detected.";
    }
    keys.sort(function (a, b) { return scores[b] - scores[a]; });
    var picked = keys.slice(0, 2);
    var hints = [];
    for (var j = 0; j < picked.length; j++) {
      if (overallHints[picked[j]] && overallHints[picked[j]][language]) hints.push(overallHints[picked[j]][language]);
    }
    if (!hints.length) {
      return language === "hi"
        ? "आपकी रिपोर्ट में कुछ ऐसे मान हैं जो सामान्य सीमा से बाहर हैं, और यह किसी समस्या से जुड़ा हो सकता है।"
        : language === "ta"
        ? "உங்கள் அறிக்கையில் சில மதிப்புகள் சாதாரண வரம்பிற்கு வெளியே உள்ளன, இது ஒரு பிரச்சனையுடன் தொடர்புடையதாக இருக்கலாம்."
        : "Your report shows some values outside the typical range, which may be linked to a health problem.";
    }
    return hints.join(" ");
  }

  function buildMockSummary(parsed, statuses, language) {
    var low = [], high = [];
    for (var i = 0; i < parsed.length; i++) {
      if (statuses[i] === "low") low.push(parsed[i][0]);
      else if (statuses[i] === "high") high.push(parsed[i][0]);
    }
    var overall = _buildMockOverallPrediction(parsed, statuses, language);
    if (language === "hi") {
      if (!low.length && !high.length) return overall + " फिर भी, कृपया पूरी रिपोर्ट अपने डॉक्टर को दिखाएं।";
      var parts = ["आपकी रिपोर्ट के विस्तृत मान:"];
      if (low.length) parts.push("सामान्य से कम: " + low.join(" और ") + "।");
      if (high.length) parts.push("सामान्य से अधिक: " + high.join(" और ") + "।");
      parts.push("यह कोई निदान नहीं है — कृपया अपने डॉक्टर से इस पर चर्चा करें।");
      return overall + " " + parts.join(" ");
    }
    if (language === "ta") {
      if (!low.length && !high.length) return overall + " இருப்பினும், முழு அறிக்கையையும் உங்கள் மருத்துவரிடம் காட்டுங்கள்.";
      var tparts = ["உங்கள் அறிக்கையின் விரிவான மதிப்புகள்:"];
      if (low.length) tparts.push("வழக்கத்தை விட குறைவு: " + low.join(" மற்றும் ") + ".");
      if (high.length) tparts.push("வழக்கத்தை விட அதிகம்: " + high.join(" மற்றும் ") + ".");
      tparts.push("இது நோயறிதல் அல்ல — மருத்துவரிடம் விவாதிக்கவும்.");
      return overall + " " + tparts.join(" ");
    }
    if (!low.length && !high.length) return overall + " Still, please show the full report to your doctor.";
    var eparts = ["Here are the detailed values:"];
    if (low.length) eparts.push("Lower than typical: " + low.join(", ") + ".");
    if (high.length) eparts.push("Higher than typical: " + high.join(", ") + ".");
    eparts.push("This is not a diagnosis — please discuss it with your doctor.");
    return overall + " " + eparts.join(" ");
  }

  function buildMockNextSteps(emergencyTrigger, language) {
    var urgent = language === "hi"
      ? ["यदि आपको सीने में दर्द, सांस लेने में तकलीफ, या बेहोशी लगे, तो तुरंत आपातकालीन सेवाओं से संपर्क करें।"]
      : language === "ta"
      ? ["நெஞ்சு வலி, மூச்சுத் திணறல் அல்லது மயக்கம் ஏற்பட்டால் உடனே அவசர சேவையை அழைக்கவும்."]
      : ["If you feel chest pain, severe breathlessness, or faintness, contact emergency services right away."];
    var base = language === "hi"
      ? ["इस रिपोर्ट और सवालों की सूची अपने अगले डॉक्टर की नियुक्ति पर साथ ले जाएं।", "बिना डॉक्टर की सलाह के कोई दवा की खुराक न बदलें और न ही कोई नुस्खा आज़माएं।", "घबराएं नहीं — यह केवल जानकारी है। अपने डॉक्टर से इस पर चर्चा करें।"]
      : language === "ta"
      ? ["இந்த அறிக்கையையும் கேள்விகளையும் அடுத்த மருத்துவர் சந்திப்புக்கு எடுத்துச் செல்லுங்கள்.", "மருத்துவரின் ஆலோசனை இல்லாமல் மருந்தை மாற்றவோ அல்லது வீட்டு வைத்தியம் முயற்சிக்கவோ வேண்டாம்.", "பயப்பட வேண்டாம் — இது தகவல் மட்டுமே. உங்கள் மருத்துவரிடம் பேசுங்கள்."]
      : ["Bring this report and the question list to your next doctor's appointment.", "Do not change any medicine dose or try home remedies without your doctor's advice.", "Stay calm — this is information only. Talk it through with your doctor."];
    var out = [];
    out.push.apply(out, base);
    if (emergencyTrigger) { var u2 = []; u2.push(urgent[0]); out = u2.concat(out); }
    return out;
  }

  function mockAnalysisFromText(scrubbedText, language) {
    var parsed = parseLabMetrics(scrubbedText);
    if (!parsed.length) {
      throw new Error("We couldn't clearly read the test names and values from this document. Try a clearer, closer photo, or type the values using the 'Type your test values instead' option.");
    }
    var lowered = scrubbedText.toLowerCase();
    var emergency = false;
    var ekeys = DATA.uip.emergency_keywords;
    for (var i = 0; i < ekeys.length; i++) {
      if (lowered.indexOf(ekeys[i]) !== -1) { emergency = true; break; }
    }
    var statuses = parsed.map(function (p) { return compareValueToRange(p[1], p[2]); });

    var lang = language;
    if (lang !== "hi" && lang !== "ta") lang = "en";
    var U = DATA.uip;

    var simplifiedTerms = parsed.slice(0, 3).map(function (p) {
      return { term: p[0], explanation: U.term_expl[lang], analogy: U.term_analogy[lang] };
    });

    var numericalContext = [];
    for (var j = 0; j < parsed.length; j++) {
      var metric = parsed[j][0], value = parsed[j][1], range = parsed[j][2];
      var status = statuses[j];
      var causes = "", guidance = "", conditions = [];
      if (status === "high" || status === "low") {
        var hint = getClinicalHint(metric, status, lang);
        causes = hint[0]; guidance = hint[1];
        conditions = possibleConditionsFor(metric, status, lang);
        if (!causes) causes = "";
      }
      numericalContext.push({
        metric: metric, value: value, normal_range: range, status: status,
        calm_explanation: U.num_expl[lang], possible_causes: causes,
        doctor_guidance: guidance, possible_conditions: conditions
      });
    }

    var primary = parsed[0];
    var qs = U.q_templates[lang];
    var doctorQuestions = [
      qs[0].replace("{metric}", primary[0]).replace("{value}", primary[1]),
      qs[1], qs[2]
    ];

    return {
      emergency_trigger: emergency,
      report_summary: buildMockSummary(parsed, statuses, lang),
      simplified_terms: simplifiedTerms,
      numerical_context: numericalContext,
      doctor_questions: doctorQuestions,
      next_steps: buildMockNextSteps(emergency, lang)
    };
  }

  /* ---------- safety & privacy (in-browser ports) ---------- */
  function rejectImagingDocument(filename, contentType) {
    var fname = (filename || "").toLowerCase();
    var sf = DATA.safety;
    for (var i = 0; i < sf.imaging_extensions.length; i++) {
      if (fname.endsWith(sf.imaging_extensions[i])) {
        throw new Error("This file appears to be a medical imaging scan (DICOM/NIfTI). MediBridge only supports text-based lab reports, not X-rays or MRIs.");
      }
    }
    if (contentType === "application/dicom" || contentType === "application/x-dicom") {
      throw new Error("DICOM imaging files are not supported. Please upload a photo of a text-based lab report.");
    }
    for (var k = 0; k < sf.imaging_keywords.length; k++) {
      if (fname.indexOf(sf.imaging_keywords[k]) !== -1) {
        throw new Error("This upload appears to be a medical imaging file ('" + sf.imaging_keywords[k] + "'). MediBridge only processes text-based lab result sheets, not X-rays or MRIs.");
      }
    }
  }

  function scrubPii(text) {
    if (!text) return text;
    var s = text;
    var sf = DATA.safety;
    s = s.replace(reFrom(sf.email, "g"), "[EMAIL_REDACTED]");
    s = s.replace(reFrom(sf.phone, "g"), "[PHONE_REDACTED]");
    s = s.replace(reFrom(sf.ssn, "g"), "[SSN_REDACTED]");
    s = s.replace(reFrom(sf.dob, "g"), "DOB: [DATE_REDACTED]");
    s = s.replace(reFrom(sf.patient_name, "g"), "Patient Name: [NAME_REDACTED]");
    s = s.replace(reFrom(sf.mrn, "g"), function (m0) {
      return m0.replace(/[\w-]+$/, "[ID_REDACTED]");
    });
    s = s.replace(reFrom(sf.address, "g"), "[ADDRESS_REDACTED]");
    s = s.replace(/(?:Dr\.|Doctor)[ \t]+[A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+)?/g, "Dr. [NAME_REDACTED]");
    return s;
  }

  function validateLabReportText(text) {
    var sf = DATA.safety;
    if (!text || text.trim().length < 20) {
      throw new Error("Not enough text was found. Please upload a clear photo of a full lab report page.");
    }
    var lowered = text.toLowerCase();
    var keywordHits = 0;
    for (var i = 0; i < sf.lab_report_keywords.length; i++) {
      if (lowered.indexOf(sf.lab_report_keywords[i]) !== -1) keywordHits++;
    }
    var labValues = findIter(sf.lab_value, text).length;
    var columnValues = findIter(sf.column_value, text).length;
    var valueHits = labValues + columnValues;
    var numericLines = findIter({ pattern: "[:=]\\s*[\\d.]+\\s*(?:mg/dL|g/dL|mmol/L|U/L|/dL|/uL|%)", flags: 2 }, text).length;
    var hasReportContext = /(lab|laboratory|report|result|pathology|diagnostic|panel)/.test(lowered);

    if (keywordHits < 2) {
      throw new Error("This does not look like a laboratory report. Please upload a photo of a real text-based lab result sheet — not random notes, homework, receipts, or other documents.");
    }
    if (valueHits < 2 && numericLines < 2) {
      throw new Error("No lab test values were detected in this image. Please upload a clearer photo of a lab report that shows test names and numbers.");
    }
    if (!hasReportContext && valueHits < 3) {
      throw new Error("The text found does not appear to be from a medical lab report. MediBridge only analyzes laboratory result documents.");
    }
  }

  /* ---------- typed-text convenience: build colon text from a manual list ---------- */
  function buildTypedText(entries) {
    // entries: [{name, value, reference?}]  -> "Name: value (Ref: range)"
    return entries.map(function (e) {
      var line = e.name + ": " + e.value;
      if (e.reference) line += " (Ref: " + e.reference + ")";
      return line;
    }).join("\n");
  }

  global.OfflineEngine = {
    setData: setData,
    extractBiomarkerRows: extractBiomarkerRows,
    mockAnalysisFromText: mockAnalysisFromText,
    buildTypedText: buildTypedText,
    rejectImagingDocument: rejectImagingDocument,
    scrubPii: scrubPii,
    validateLabReportText: validateLabReportText,
    compareValueToRange: compareValueToRange,
    normalizeBiomarkerName: normalizeBiomarkerName,
    isRecognizedBiomarker: isRecognizedBiomarker
  };
})(typeof window !== "undefined" ? window : globalThis);