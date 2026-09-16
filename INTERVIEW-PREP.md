# MediBridge — Interview Prep & Presentation Playbook

Use this to (1) present the project from scratch, and (2) handle any question
they might ask. Every claim below is TRUE of the actual code in this repo.

---

## 1. The 60-second pitch (memorize this)

> "MediBridge is a web app that lets everyday patients understand their
> **lab reports and prescriptions** in plain language, in English, Hindi and
> Tamil. You upload a photo of the report — we reject anything that isn't a
> lab sheet, OCR it with Tesseract, redact personal data, extract every test
> value, and generate a **safe, non-diagnosing summary** with exactly three
> questions to ask a doctor. Each result can be **read out loud** using
> text-to-speech, and, if signed in, reports are **saved with trend
> comparison** over time. The backend is Python/FastAPI, the frontend is
> React/Vite, and the whole thing ships as Docker containers."

---

## 2. The story from scratch (narrate this)

**Problem.** Patients get lab reports full of medical vocabulary and unit
values, with phone numbers and identities scattered over the sheet. Doctors
have no time to explain each number. Non-English speakers get even less help.

**Solution.** One photo in → a safe, language-localized, spoken explanation →
and a set of prepared doctor questions → history so they can watch trends.

**How (the 6 stages, in order):**
1. **Safety filter** — refuse X-rays/MRIs/CTs (extension, content-type, filename,
   header bytes) and make sure the upload actually looks like a lab report.
2. **OCR** — Tesseract, 3 preprocessing passes run concurrently, merged with a
   union-style merge so each row is read by at least one pass.
3. **PII redaction** — regex scrub of email, phone, SSN, DOB, patient name,
   MRN, address, doctor name before anything else touches the text.
4. **Biomarker extractor** — map messy OCR lines to a canonical metric
   (aliases → canonical name) with value + unit + reference range.
5. **U.I.P. engine** — Understand/Interpret/Prepare: simplified explanation +
   analogy per metric, status (high/low/normal/unknown), possible causes
   ("may be linked to…", never a diagnosis), exactly 3 doctor questions,
   hard-coded critical thresholds → emergency flag, next steps.
6. **Output** — JSON to the React UI, TTS audio on demand, auto-save to
   history when signed in.

**Prescription path** is the twin flow: same upload → OCR → medicine-name
extraction → pharmacist questions (also exactly 3).

---

## 3. Architecture (draw this on the whiteboard)

```
Browser (React + Vite + Tailwind)
        │  /api/*  (same-origin through nginx / Vite proxy)
        ▼
nginx (port 80)  ──proxy──▶  FastAPI / Uvicorn (port 8000)
                                 │
        ┌────────────────────────┼───────────────────────────┐
        ▼                        ▼                           ▼
 safety_filter           ocr_engine                  db.py (SQLite)
 + pii scrub         (Tesseract 3 passes)        users / sessions / reports
        │                        │                 PBKDF2-120k, bearer tokens
        ▼                        ▼                           │
 biomarker_extractor     prescription_extractor      history + trends API
        │                        │
        ▼                        ▼
  uip_framework.py        prescriptions → pharmacist questions
  (summary, 3 questions,
   emergency flag)
        │
        ▼
  tts_engine (edge-tts + gTTS fallback + disk cache)
```

**Data flow (lab):**
`image → reject Imaging? → Tesseract OCR ×3 → validate lab text → scrub PII →
extract rows → UIP analyze → {summary, contexts, 3 questions, next_steps,
emergency_trigger} → UI card + 🔊 audio`

---

## 4. Component deep-dive (know each cold)

| Component | What it does | Why it's worth mentioning |
|---|---|---|
| `safety_filter.py` | Refuses imaging files (`.dcm`, "x-ray"/"mri" in name, DICOM content-type, suspicious bytes) and validates the text looks like a lab sheet | "LLM-like apps must have a gate; we never let a medical scan into the pipeline." |
| `ocr_engine.py` | `asyncio.gather` runs Tesseract 3 ways: `--psm 3`, `--psm 6`, and a binarized high-contrast pass (threshold 140); union-merges lines, keeping the highest-yield variant | "Parallelism + dedup instead of one fragile pass; subprocess to the tesseract binary, no pytesseract." |
| PII scrub | Regex for email/phone/SSN/DOB/name/MRN/address + `Dr.` names | "Data minimization even before any AI layer." |
| `biomarker_extractor.py` | Decanonical aliases → canonical metric (e.g. `hgb`/`hb` → "Hemoglobin (Hb)"), value+unit+range; ~40 biomarkers across CBC, lipid, thyroid, renal, hepatic panels | "OCR noise is absorbed by alias matching; canonical names power localization & trends." |
| `uip_framework.py` | Status per metric vs reference range; "may be linked to" causes; critical-threshold emergency flag; exactly 3 doctor questions | "Safety by architecture: every sentence comes from a curated template/hint — the engine physically cannot invent a diagnosis or a drug." |
| `tts_engine.py` | edge-tts neural voices (en/hi/ta), gTTS fallback, disk cache keyed by text hash | "Cache avoids re-paying the network for the same sentence." |
| `db.py` (SQLite) | `users`, `sessions`, `reports`; PBKDF2-HMAC-SHA256 120k iterations + salt, `hmac.compare_digest`; bearer token sessions; per-user SQL (`WHERE user_id = ?`) | "Passwords never stored; `?` placeholders block SQL injection; RLock serializes writes." |
| Frontend | React 18 + Vite 5 + Tailwind; pages: Landing → sign-in/skip → Report chooser (Lab/Prescription) → analysis page → Previous Records | "State-driven routing, no router dependency; every component is a box; ErrorBoundary catches render crashes." |

---

## 5. "Why did you pick…" — the Qs they ALWAYS ask

**FastAPI?**
- Async (`async def`, `asyncio`), Pydantic validation (lab values, exactly-3
  questions enforced by `Field(min_length=3, max_length=3)`), automatic Swagger
  docs at `/docs`, typed responses.

**SQLite?**
- Zero-ops, file-based, transactional, built into Python. Perfect for a
  single-machine app. Honest limitation: single-writer, one instance —
  upgrade path is Postgres; the `db.py` layer isolates that change.

**React/Vite?**
- Component model + unidirectional state (`useState`/`useCallback`) keeps the
  wizard-like flow readable; Vite gives fast HMR and a tiny bundle
  (~208 KB JS, ~68 KB gzip).

**Tesseract vs cloud OCR?**
- Free, local (text never leaves the machine → privacy), fine-grained control
  (we own the preprocessing). Cloud OCR (Google/AWS) is the upgrade path for
  harder images.

**edge-tts?**
- Deep-neural voices in hi/ta with no API key; fallback gTTS; offline mock
  works without the network for analysis.

**Mock AI provider?**
- `AI_PROVIDER=mock` uses a curated medical knowledge base → deterministic,
  offline, free, and safe to demo. The code supports `openai`/`anthropic` via
  env vars for production; swap without touching the API.

---

## 6. Numbers to quote

- 3 OCR passes, merged concurrently; ~1–3 s end-to-end on a clear photo.
- 40+ recognized biomarkers; sample sheet extracts ~32 clean rows.
- Exactly 3 doctor questions (Pydantic-enforced), 3 languages (en/hi/ta).
- 10 MB upload cap; 422 on rejected/failed input; 401/409/413/500 semantics.
- Frontend: ~208 KB JS (~68 KB gzip); backend Python 3.9 + FastAPI.
- PBKDF2 120,000 iterations, 192-bit salt, constant-time compare.

---

## 7. Honest weak points (have answers ready)

1. **OCR isn't perfect.** Answer: 3-pass preprocessor reduces this; low-quality
   photos get a clear error, plus a "type the values instead" fallback in the UI.
2. **Mock AI ≠ real medical judgement.** Answer: it's deliberately
   non-diagnosing by design; provider is swappable and the safety contract
   doesn't change.
3. **SQLite doesn't scale horizontally.** Answer: correct; designed for single
   instance; schema/query layer is isolated behind `db.py` so Postgres is a
   contained swap.
4. **TTS needs internet** (edge-tts/gTTS). Answer: analysis itself is offline;
   audio is best-effort with fallback + cache.
5. **Hindi/Tamil script voices may mangle metric names.** Answer: METRIC_ROMAN
   gives phonetic Latin forms for speech when no script voice exists.
6. **Data is stored only in the container DB.** Answer: Docker volume
   `backend-data` persists it; we redact PII before it ever enters the DB.

---

## 8. Demo script (if they ask for one)

1. Open `http://localhost:5173`. Say: "Landing page, three languages."
2. **Get Started → Lab Result** → upload `clean_report.png`. Narrate the
   stages appearing ("uploading → OCR → analyzing").
3. Point at a metric card: "Hemoglobin → low, 'may be linked to anaemia…',
   and the safe guidance — no prescription claimed."
4. Click a **Hear** button: "That's edge-tts, cached after first call."
5. **Sign in → upload again → Previous Records**: "You see the trend table —
   previous value vs now, delta, direction — per user, via SQLite."
6. Show `/health` on the backend to prove `ai_provider: mock`, `ocr_available: true`.

Have open: `backend/main.py`, `backend/pipeline/*.py`, `frontend/src/App.jsx`,
an expanded browser tab. Being able to jump to the exact file = instant credibility.

---

## 9. Q&A BANK (read every answer out loud)

**Security & safety**
- How do you prevent a wrong/malicious file? → Extension `.dcm`, imaging
  keywords in filename, content-type, first 8 KB header scan; then the
  lab-text validator must find ≥2 unit-bearing values + report keywords.
- Password storage? → PBKDF2-HMAC-SHA256, 120k iterations, per-user salt; only
  the hash is stored; verification via `hmac.compare_digest` (timing-safe).
- SQL injection? → Parameterized `?` queries everywhere, no string-built SQL.
- Token handling? → Random bearer token in `sessions`; sent as
  `Authorization: Bearer …`; revoked on logout; per-user rows filtered by
  `user_id`.
- Can user A see user B's reports? → No — every history query is scoped by
  `user_id`; a wrong-owner id returns 404.
- Why do you restrict to exactly 3 questions? → Deterministic output contract,
  enforced by Pydantic — the frontend and TTS rely on an exact shape.

**Analysis**
- How do you make sure it never diagnoses? → There is no code path that emits
  a condition as fact: templates say "may be linked to", guidance always ends
  in "ask your doctor", and the model refuses imaging.
- What happens on a critical value? → `emergency_trigger` becomes true and the
  UI shows a red "seek urgent care" banner — from hard-coded thresholds (e.g.
  Hb < 7), not from the AI's opinion.
- How do you handle a garbled OCR line? → Alias/canonical mapping absorbs
  spelling noise; unrecognized rows are excluded by `is_recognized_biomarker`;
  if nothing valid parses → 422 with a clear message.

**Engineering**
- How does the frontend talk to the backend? → Dev: Vite proxy `/api` →
  `127.0.0.1:8000`. Prod: nginx reverse-proxies `/api` to the backend service,
  same origin → no CORS at all.
- State management? → Local component state + callback props; two levels of
  ErrorBoundary; no Redux needed at this size.
- How would you scale? → Postgres for the DB, object storage + presigned URLs
  for images, Redis for TTS/file cache, horizontal backend behind nginx,
  static frontend on a CDN.
- How would you test? → We validate each stage with a scripted end-to-end
  check (OCR → extract → UIP), plus REST-level tests for auth (409 dup, 401
  bad login, 401 no-token) and history (save/list/detail/trend).
- Known issue you fixed? → Column-layout lab sheets ("Hemoglobin 13.2 g/dL")
  failed the value validator because it only accepted `name: value`; I added a
  unit-required column pattern so real sheets pass while junk still fails.

**SMART/rare ones**
- "What's the biggest risk?" → OCR accuracy on poor photos; mitigated by
  preprocessing, fallback typing, and honest errors.
- "Why not one endpoint for everything?" → Separation of concerns; the safety
  filter must exist before OCR, validation before interpretation — each in its
  own module, each unit-testable.
- "How long did it take / what did YOU build?" → You built the end-to-end
  feature set; emphasize the layout-validation bug you found and fixed in the
  real validator, and the multi-page UX restructure.

---

## 10. Presentation structure (12 minutes)

1. Hook — the problem (30 s)
2. Demo — one photo through the whole pipeline (3 min, narrate stages)
3. Architecture diagram + data flow (2 min)
4. The 3 hard parts: safety gate, ambiguity handling (OCR→canonical), and
   "no-diagnosis" enforcement (3 min)
5. Personal contribution + an honest known limitation (2 min)
6. Close: "It's deployable today as 2 Docker containers behind nginx." (30 s)

## Extra: every real endpoint to name-drop
- `POST /api/analyze` (lab photo), `POST /api/analyze-prescription`,
  `POST /api/analyze-lab-text`, `POST /api/analyze-prescription-text`
- `POST /api/tts` (text+lang → mp3)
- `POST /api/auth/signup|login|logout`, `POST /api/history`,
  `POST /api/history/save`, `POST /api/history/{id}`
- `GET /health`, `GET /docs`