import { useCallback, useRef, useState } from "react";
import CameraModal from "./CameraModal.jsx";

const STAGE_LABELS = {
  en: {
    idle: "Drag & drop or tap to upload a photo of your lab report",
    rxIdle: "Drag & drop or tap to upload a photo of the prescription",
    hint: "JPEG, PNG, or WebP • Text-based lab sheets only • No X-rays or MRIs",
    rxHint: "JPEG, PNG, or WebP • Clear photo of the medicine list",
    camera: "Use Camera",
    browse: "Browse Files",
    uploading: "Uploading image…",
    ocr: "Reading text from your report…",
    analyzing: "Simplifying medical terms safely…",
    done: "Analysis complete",
    errorGeneric: "Something went wrong. Please try again.",
    invalidFile: "Please upload an image (JPEG or PNG), not a text or document file.",
    typeInstead: "Couldn't read the photo? Type the medicine names instead",
    textPlaceholder: "e.g. Dolo 650, Omez, Pan 40, Shelcal 500",
    textButton: "Check Medicines",
    typing: "Checking medicines…",
    labTypeInstead: "Couldn't read the photo? Type your test values instead",
    labTextPlaceholder: "e.g. Hemoglobin 11.2 (Ref: 12-16), Platelets 180 (Ref: 150-410)",
    labTextButton: "Analyze Values",
    labTyping: "Analyzing values…",
  },
  hi: {
    idle: "अपनी लैब रिपोर्ट की फोटो खींचें या अपलोड करें",
    rxIdle: "दवा पर्ची की फोटो खींचें या अपलोड करें",
    hint: "JPEG, PNG, WebP • केवल टेक्स्ट लैब शीट • X-ray/MRI नहीं",
    rxHint: "JPEG, PNG, WebP • दवाइयों की सूची की साफ़ फोटो",
    camera: "कैमरा उपयोग करें",
    browse: "फ़ाइल चुनें",
    uploading: "छवि अपलोड हो रही है…",
    ocr: "रिपोर्ट से टेक्स्ट पढ़ा जा रहा है…",
    analyzing: "चिकित्सा शब्द सरल बनाए जा रहे हैं…",
    done: "विश्लेषण पूर्ण",
    errorGeneric: "कुछ गलत हुआ। कृपया पुनः प्रयास करें।",
    invalidFile: "कृपया छवि (JPEG/PNG) अपलोड करें, टेक्स्ट या दस्तावेज़ फ़ाइल नहीं।",
    typeInstead: "फ़ोटो नहीं पढ़ी गई? दवाइयों के नाम लिखकर भेजें",
    textPlaceholder: "जैसे: Dolo 650, Omez, Pan 40, Shelcal 500",
    textButton: "दवाइयाँ जाँचें",
    typing: "दवाइयाँ जाँची जा रही हैं…",
    labTypeInstead: "फ़ोटो नहीं पढ़ी गई? अपनी टेस्ट वैल्यू लिखकर भेजें",
    labTextPlaceholder: "जैसे: Hemoglobin 11.2 (Ref: 12-16), Platelets 180 (Ref: 150-410)",
    labTextButton: "वैल्यू विश्लेषित करें",
    labTyping: "वैल्यू विश्लेषित हो रही हैं…",
  },
  ta: {
    idle: "உங்கள் ஆய்வக அறிக்கை புகைப்படத்தை பதிவேற்றுங்கள்",
    rxIdle: "மருந்து பரிந்துரையின் புகைப்படத்தை பதிவேற்றுங்கள்",
    hint: "JPEG, PNG, WebP • உரை அடிப்படையிலான அறிக்கை மட்டும் • X-ray/MRI இல்லை",
    rxHint: "JPEG, PNG, WebP • மருந்து பட்டியலின் தெளிவான புகைப்படம்",
    camera: "கேமரா பயன்படுத்து",
    browse: "கோப்பு தேர்வு",
    uploading: "படம் பதிவேற்றப்படுகிறது…",
    ocr: "அறிக்கையிலிருந்து உரை படிக்கப்படுகிறது…",
    analyzing: "மருத்துவ சொற்கள் எளிமைப்படுத்தப்படுகின்றன…",
    done: "பகுப்பாய்வு முடிந்தது",
    errorGeneric: "ஏதோ தவறு நடந்தது. மீண்டும் முயற்சிக்கவும்.",
    invalidFile: "JPEG/PNG படத்தை பதிவேற்றுங்கள், உரை அல்லது ஆவண கோப்பு அல்ல.",
    typeInstead: "புகைப்படத்தை படிக்க முடியவில்லையா? மருந்து பெயர்களை தட்டச்சு செய்யவும்",
    textPlaceholder: "எ.கா: Dolo 650, Omez, Pan 40, Shelcal 500",
    textButton: "மருந்துகளை சரிபார்",
    typing: "மருந்துகள் சரிபார்க்கப்படுகின்றன…",
    labTypeInstead: "புகைப்படத்தை படிக்க முடியவில்லையா? உங்கள் சோதனை மதிப்புகளை தட்டச்சு செய்யவும்",
    labTextPlaceholder: "எ.கா: Hemoglobin 11.2 (Ref: 12-16), Platelets 180 (Ref: 150-410)",
    labTextButton: "மதிப்புகளை பகுப்பாய்வு செய்",
    labTyping: "மதிப்புகள் பகுப்பாய்வு செய்யப்படுகின்றன…",
  },
};

const STAGES = ["uploading", "ocr", "analyzing", "done"];

function ProgressBar({ stage, labels }) {
  const currentIndex = STAGES.indexOf(stage);

  return (
    <div className="mt-6 space-y-3">
      <div className="flex justify-between text-xs font-medium text-slate-500">
        {STAGES.slice(0, 3).map((key, index) => (
          <span
            key={key}
            className={index <= currentIndex ? "text-medibridge-700" : ""}
          >
            {labels[key]}
          </span>
        ))}
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-200">
        <div
          className="h-full rounded-full bg-medibridge-600 transition-all duration-500 ease-out"
          style={{ width: `${Math.min(100, ((currentIndex + 1) / 3) * 100)}%` }}
        />
      </div>
      <p className="text-center text-sm font-medium text-medibridge-800">
        {labels[stage]}
      </p>
    </div>
  );
}

export default function UploadZone({ language, title, docType, onComplete, onError }) {
  const labels = STAGE_LABELS[language] || STAGE_LABELS.en;
  const isPrescription = docType === "prescription";
  const endpoint = isPrescription ? "/api/analyze-prescription" : "/api/analyze";
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [stage, setStage] = useState("uploading");
  const [showCamera, setShowCamera] = useState(false);
  const [showTextInput, setShowTextInput] = useState(false);
  const fileInputRef = useRef(null);
  const textInputRef = useRef(null);

  const processText = useCallback(
    async (rawText) => {
      const text = (rawText || "").trim();
      if (!text) return;
      setIsProcessing(true);
      setStage("analyzing");
      const textEndpoint = isPrescription
        ? "/api/analyze-prescription-text"
        : "/api/analyze-lab-text";
      try {
        const response = await fetch(
          `${textEndpoint}?lang=${language}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text }),
          }
        );
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          const detail = data.detail;
          const message = Array.isArray(detail)
            ? detail.map((item) => item.msg || item).join(", ")
            : detail || labels.errorGeneric;
          throw new Error(message);
        }
        setStage("done");
        await new Promise((resolve) => setTimeout(resolve, 300));
        onComplete(data);
      } catch (err) {
        onError(err.message || labels.errorGeneric);
      } finally {
        setIsProcessing(false);
        setStage("uploading");
      }
    },
    [isPrescription, language, labels.errorGeneric, onComplete, onError]
  );

  const handleTextSubmit = useCallback(() => {
    const value = textInputRef.current?.value || "";
    if (value.trim()) processText(value);
  }, [processText]);

  const processFile = useCallback(
    async (file) => {
      if (!file || !file.type.startsWith("image/")) {
        onError(labels.invalidFile);
        return;
      }

      setIsProcessing(true);
      setStage("uploading");

      const formData = new FormData();
      formData.append("file", file);

      try {
        setStage("ocr");
        await new Promise((resolve) => setTimeout(resolve, 400));

        setStage("analyzing");
        const response = await fetch(`${endpoint}?lang=${language}`, {
          method: "POST",
          body: formData,
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
          const detail = data.detail;
          const message = Array.isArray(detail)
            ? detail.map((item) => item.msg || item).join(", ")
            : detail || labels.errorGeneric;
          throw new Error(message);
        }

        setStage("done");
        await new Promise((resolve) => setTimeout(resolve, 300));
        onComplete(data);
      } catch (err) {
        onError(err.message || labels.errorGeneric);
      } finally {
        setIsProcessing(false);
        setStage("uploading");
      }
    },
    [endpoint, language, labels.errorGeneric, onComplete, onError]
  );

  const handleDrop = useCallback(
    (event) => {
      event.preventDefault();
      setIsDragging(false);
      const file = event.dataTransfer.files?.[0];
      if (file) processFile(file);
    },
    [processFile]
  );

  const handleDragOver = useCallback((event) => {
    event.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleFileChange = useCallback(
    (event) => {
      const file = event.target.files?.[0];
      if (file) processFile(file);
      event.target.value = "";
    },
    [processFile]
  );

  return (
    <section className="card">
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>

      <div
        role="button"
        tabIndex={0}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            fileInputRef.current?.click();
          }
        }}
        className={`mt-4 flex min-h-[220px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-4 py-8 text-center transition ${
          isDragging
            ? "border-medibridge-500 bg-medibridge-50"
            : "border-slate-300 bg-slate-50 hover:border-medibridge-400 hover:bg-medibridge-50/50"
        } ${isProcessing ? "pointer-events-none opacity-70" : ""}`}
        onClick={() => !isProcessing && fileInputRef.current?.click()}
        aria-busy={isProcessing}
        aria-label={isPrescription ? labels.rxIdle : labels.idle}
      >
        <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-medibridge-100 text-medibridge-700">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-7 w-7"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
            />
          </svg>
        </div>

        <p className="text-sm font-medium text-slate-700">
          {isPrescription ? labels.rxIdle : labels.idle}
        </p>
        <p className="mt-2 max-w-sm text-xs text-slate-500">
          {isPrescription ? labels.rxHint : labels.hint}
        </p>

        {!isProcessing && (
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            <button
              type="button"
              className="btn-primary"
              onClick={(event) => {
                event.stopPropagation();
                setShowCamera(true);
              }}
            >
              {labels.camera}
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={(event) => {
                event.stopPropagation();
                fileInputRef.current?.click();
              }}
            >
              {labels.browse}
            </button>
          </div>
        )}
      </div>

      {isProcessing && <ProgressBar stage={stage} labels={labels} />}

      <div className="mt-5 border-t border-slate-200 pt-4">
        <button
          type="button"
          onClick={() => setShowTextInput((v) => !v)}
          className="text-sm font-medium text-medibridge-700 underline-offset-2 hover:underline"
        >
          {isPrescription ? labels.typeInstead : labels.labTypeInstead}
        </button>

        {showTextInput && (
          <div className="mt-3 space-y-3">
            <textarea
              ref={textInputRef}
              rows={3}
              placeholder={
                isPrescription ? labels.textPlaceholder : labels.labTextPlaceholder
              }
              className="w-full rounded-xl border border-slate-300 bg-white p-3 text-sm text-slate-800 focus:border-medibridge-500 focus:outline-none focus:ring-2 focus:ring-medibridge-500"
            />
            <button
              type="button"
              onClick={handleTextSubmit}
              disabled={isProcessing}
              className="btn-primary"
            >
              {isPrescription ? labels.textButton : labels.labTextButton}
            </button>
          </div>
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/jpg"
        className="hidden"
        onChange={handleFileChange}
        aria-hidden="true"
      />

      {showCamera && (
        <CameraModal
          language={language}
          onCapture={processFile}
          onClose={() => setShowCamera(false)}
          onError={onError}
        />
      )}
    </section>
  );
}
