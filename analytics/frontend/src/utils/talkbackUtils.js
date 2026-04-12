/**
 * Talkback Utilities
 * Helper functions for text-to-speech, voice input, and talkback orchestration
 */

/**
 * Check if browser supports Web Speech API (SpeechSynthesis)
 */
export const isTTSSupported = () => {
  return 'speechSynthesis' in window || 'webkitSpeechSynthesis' in window;
};

/**
 * Check if browser supports Web Speech API (SpeechRecognition)
 */
export const isSTRSupported = () => {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  return !!SpeechRecognition;
};

/**
 * Request microphone permission (user-initiated)
 * Returns true if permission granted, false otherwise
 */
export const requestMicPermission = async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    // Stop the stream immediately - we just needed to request permission
    stream.getTracks().forEach(track => track.stop());
    return true;
  } catch (error) {
    console.warn('Microphone permission denied:', error);
    return false;
  }
};

/**
 * Get list of available voices for TTS
 */
export const getAvailableVoices = () => {
  const synthesis = window.speechSynthesis || window.webkitSpeechSynthesis;
  if (!synthesis) return [];
  return synthesis.getVoices();
};

/**
 * Find voice by language code
 */
export const findVoiceByLanguage = (lang = 'en-US') => {
  const voices = getAvailableVoices();
  return voices.find(v => v.lang.startsWith(lang)) || voices[0];
};

/**
 * Find voice by name (partial, case-insensitive), fallback to language
 */
export const findVoiceByName = (name, fallbackLang = 'en-US') => {
  const voices = getAvailableVoices();
  const byName = voices.find(v => v.name.toLowerCase().includes(name.toLowerCase()));
  return byName || findVoiceByLanguage(fallbackLang);
};

/**
 * Cancel all pending TTS utterances
 */
export const cancelAllSpeech = () => {
  const synthesis = window.speechSynthesis || window.webkitSpeechSynthesis;
  if (synthesis) {
    synthesis.cancel();
  }
};

/**
 * Check if TTS is currently speaking
 */
export const isSpeaking = () => {
  const synthesis = window.speechSynthesis || window.webkitSpeechSynthesis;
  return synthesis ? synthesis.speaking : false;
};

/**
 * Add a message to browser console (debug)
 */
export const debugLog = (tag, message, data = null) => {
  if (data) {
    console.log(`[${tag}] ${message}`, data);
  } else {
    console.log(`[${tag}] ${message}`);
  }
};

/**
 * Validate input method
 */
export const isValidInputMethod = (method) => {
  return ['voice', 'keyboard'].includes(method);
};

/**
 * Format question number display
 */
export const formatQuestionNumber = (current, total) => {
  return `Question ${current} of ${total}`;
};

/**
 * Sanitize text for TTS (remove special characters, emojis, markdown)
 */
export const sanitizeForTTS = (text) => {
  // Remove markdown formatting
  let cleaned = text.replace(/\*\*/g, '').replace(/__/g, '').replace(/~~(.*?)~~/g, '$1');
  // Remove emojis
  cleaned = cleaned.replace(/[\u{1F300}-\u{1F9FF}]/gu, '');
  // Remove extra whitespace
  cleaned = cleaned.replace(/\s+/g, ' ').trim();
  return cleaned;
};

/**
 * Browser permission status check
 */
export const checkBrowserSupport = () => {
  return {
    tts: isTTSSupported(),
    str: isSTRSupported(),
    mediaDevices: !!navigator.mediaDevices?.getUserMedia,
  };
};

/**
 * Generate unique message ID (timestamp-based)
 */
export const generateMessageId = () => {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
};
