import { useCallback, useEffect, useRef, useState } from "react";

const LANG_MAP = { en: "en-IN", hi: "hi-IN", ta: "ta-IN" };

/**
 * Reliable, professional text-to-speech.
 *
 * Primary path is server-side neural TTS (`POST /api/tts`, Microsoft Edge
 * voices via edge-tts): identical high-quality female voice in en/hi/ta on
 * every browser and OS, and it reads Devanagari/Tamil script perfectly. When
 * the server TTS is unavailable (edge-tts not installed or offline) it falls
 * back to the browser's build-in speechSynthesis using a script-capable,female
 * voice when present.
 *
 * `speak(sectionId, textBuilder)` — textBuilder is called with `true` to build
 * text in the native script (server voices read it) and with `false ` for the
 * romanized fallback the browser path needs.
 */
export default function useSpeech(language) {
  const [activeSection, setActiveSection] = useState(null);
  const audioRef = useRef(null);
  const voicesRef = useRef([]);
  const tokenRef = useRef(0);

  const loadVoices = useCallback(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    const available = window.speechSynthesis.getVoices() || [];
    if (available.length) voicesRef.current = available;
  }, []);

  useEffect(() => {
    loadVoices();
    window.speechSynthesis?.addEventListener?.("voiceschanged", loadVoices);
    return () => window.speechSynthesis?.removeEventListener?.("voiceschanged", loadVoices);
  }, [loadVoices]);

  const stop = useCallback(() => {
    tokenRef.current += 1;
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.removeAttribute("src");
      audioRef.current = null;
    }
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setActiveSection(null);
  }, []);

  useEffect(() => () => stop(), [stop]);

  const playServerAudio = useCallback(
    (sectionId, text, token) =>
      new Promise((resolve, reject) => {
        fetch("/api/tts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, language }),
        })
          .then(async (res) => {
            if (!res.ok) throw new Error(`tts-unavailable (${res.status})`);
            return res.blob();
          })
          .then((blob) => {
            if (tokenRef.current !== token) return; // superseded
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);
            audioRef.current = audio;
            setActiveSection(sectionId);
            const cleanup = () => {
              URL.revokeObjectURL(url);
              if (audioRef.current === audio) audioRef.current = null;
              setActiveSection(null);
            };
            audio.onended = () => cleanup();
            audio.onerror = () => {
              cleanup();
              reject(new Error("audio decode failed"));
            };
            audio.play().catch((err) => {
              cleanup();
              reject(err);
            });
          })
          .catch(reject);
      }),
    [language]
  );

  const playBrowserSpeech = useCallback(
    (sectionId, text, token) =>
      new Promise((resolve) => {
        if (typeof window === "undefined" || !window.speechSynthesis) {
          setActiveSection(null);
          resolve();
          return;
        }
        const wanted = LANG_MAP[language] || "en-IN";
        const prefix = wanted.split("-")[0].toLowerCase();
        const femaleHint =
          /(female|women|woman|zira|hazel|samantha|aria|jenny|amy|natalie|susan|karen|moira|tessa|veena|heera|kalpana|shweta|lekha)/i;
        const score = (v) => {
          const name = v.name || "";
          const ok = (v.lang || "").replace("_", "-").toLowerCase().startsWith(prefix);
          const female = femaleHint.test(name);
          const local = !!v.localService;
          return (ok ? 1000 : 0) + (female ? 50 : 0) + (local ? 5 : 0);
        };
        const voice = [...voicesRef.current].sort((a, b) => score(b) - score(a))[0];
        const utterance = new SpeechSynthesisUtterance(text);
        if (voice) utterance.voice = voice;
        utterance.lang = voice?.lang || LANG_MAP[language] || "en-IN";
        utterance.rate = 0.95;
        utterance.onend = () => {
          if (tokenRef.current !== token) return;
          setActiveSection(null);
          resolve();
        };
        utterance.onerror = () => {
          if (tokenRef.current !== token) return;
          setActiveSection(null);
          resolve();
        };
        if (tokenRef.current !== token) return;
        setActiveSection(sectionId);
        window.speechSynthesis.speak(utterance);
      }),
    [language]
  );

  /**
   * @param {string} sectionId  – section key, used to toggle stop when re-clicked
   * @param {(useNativeScript:boolean)=>string} textBuilder
   */
  const speak = useCallback(
    (sectionId, textBuilder) => {
      if (!textBuilder) return;
      if (activeSection === sectionId) {
        stop();
        return;
      }
      stop();
      const nativeText = textBuilder(true);
      if (!nativeText) return;
      const token = ++tokenRef.current;
      setActiveSection(sectionId);
      playServerAudio(sectionId, nativeText, token).catch(() => {
        if (tokenRef.current !== token) return;
        const fallbackText = textBuilder(false) || nativeText;
        playBrowserSpeech(sectionId, fallbackText, token);
      });
    },
    [activeSection, stop, playServerAudio, playBrowserSpeech]
  );

  return { activeSection, speak, stop };
}