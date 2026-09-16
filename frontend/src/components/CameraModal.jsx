import { useCallback, useEffect, useRef, useState } from "react";

const LABELS = {
  en: {
    title: "Take a photo of your lab report",
    capture: "Capture photo",
    cancel: "Cancel",
    noCamera: "No camera found on this device. Use Browse Files instead.",
    permissionDenied: "Camera permission denied. Allow camera access in browser settings.",
    cameraError: "Could not open camera. Try Browse Files instead.",
  },
  hi: {
    title: "अपनी लैब रिपोर्ट की फोटो लें",
    capture: "फोटो लें",
    cancel: "रद्द करें",
    noCamera: "इस डिवाइस पर कैमरा नहीं मिला। फ़ाइल चुनें का उपयोग करें।",
    permissionDenied: "कैमरा अनुमति अस्वीकृत। ब्राउज़र सेटिंग में कैमरा की अनुमति दें।",
    cameraError: "कैमरा नहीं खुल सका। फ़ाइल चुनें का उपयोग करें।",
  },
  ta: {
    title: "உங்கள் ஆய்வக அறிக்கை புகைப்படம் எடுங்கள்",
    capture: "புகைப்படம் எடு",
    cancel: "ரத்து",
    noCamera: "இந்த சாதனத்தில் கேமரா இல்லை. கோப்பு தேர்வை பயன்படுத்துங்கள்.",
    permissionDenied: "கேமரா அனுமதி மறுக்கப்பட்டது. உலாவி அமைப்புகளில் அனுமதி கொடுங்கள்.",
    cameraError: "கேமரா திறக்க முடியவில்லை. கோப்பு தேர்வை பயன்படுத்துங்கள்.",
  },
};

export default function CameraModal({ language, onCapture, onClose, onError }) {
  const labels = LABELS[language] || LABELS.en;
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [isReady, setIsReady] = useState(false);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsReady(false);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function startCamera() {
      if (!navigator.mediaDevices?.getUserMedia) {
        onError(labels.noCamera);
        onClose();
        return;
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: { ideal: "environment" },
            width: { ideal: 1920 },
            height: { ideal: 1080 },
          },
          audio: false,
        });

        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }

        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
          setIsReady(true);
        }
      } catch (err) {
        if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
          onError(labels.permissionDenied);
        } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
          onError(labels.noCamera);
        } else {
          onError(labels.cameraError);
        }
        onClose();
      }
    }

    startCamera();

    return () => {
      cancelled = true;
      stopCamera();
    };
  }, [labels, onClose, onError, stopCamera]);

  const handleCapture = useCallback(() => {
    const video = videoRef.current;
    if (!video || !isReady) return;

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    context.drawImage(video, 0, 0);

    canvas.toBlob(
      (blob) => {
        if (!blob) {
          onError(labels.cameraError);
          return;
        }
        const file = new File([blob], `lab-report-${Date.now()}.jpg`, {
          type: "image/jpeg",
        });
        stopCamera();
        onCapture(file);
        onClose();
      },
      "image/jpeg",
      0.92
    );
  }, [isReady, labels.cameraError, onCapture, onClose, onError, stopCamera]);

  const handleClose = useCallback(() => {
    stopCamera();
    onClose();
  }, [onClose, stopCamera]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={labels.title}
    >
      <div className="w-full max-w-lg rounded-2xl bg-white p-4 shadow-xl">
        <h3 className="mb-3 text-lg font-semibold text-slate-900">{labels.title}</h3>

        <div className="overflow-hidden rounded-xl bg-black">
          <video
            ref={videoRef}
            className="aspect-[4/3] w-full object-cover"
            playsInline
            muted
            autoPlay
          />
        </div>

        <div className="mt-4 flex flex-wrap justify-end gap-3">
          <button type="button" className="btn-secondary" onClick={handleClose}>
            {labels.cancel}
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={handleCapture}
            disabled={!isReady}
          >
            {labels.capture}
          </button>
        </div>
      </div>
    </div>
  );
}
