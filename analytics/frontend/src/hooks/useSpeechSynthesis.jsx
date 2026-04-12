/**
 * useSpeechSynthesis Hook
 * Manages text-to-speech (TTS) playback using Web Speech API
 * Handles queue management, playback control, and voice settings
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { config } from '../config.js';
import {
  isTTSSupported,
  findVoiceByName,
  sanitizeForTTS,
  cancelAllSpeech,
  isSpeaking,
} from '../utils/talkbackUtils.js';

export const useSpeechSynthesis = () => {
  const [isReading, setIsReading] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [currentUtterance, setCurrentUtterance] = useState(null);
  const [queue, setQueue] = useState([]);
  const synthesisRef = useRef(window.speechSynthesis || window.webkitSpeechSynthesis);
  const onCompleteRef = useRef(null);

  /**
   * Speak text with optional callback when complete
   */
  const speak = useCallback((text, onComplete = null) => {
    if (!isTTSSupported()) {
      console.warn('TTS not supported');
      return false;
    }

    try {
      const sanitized = sanitizeForTTS(text);

      if (!sanitized || sanitized.trim().length === 0) {
        // Fall back to original if sanitization removes everything
        var textToSpeak = text;
      } else {
        var textToSpeak = sanitized;
      }

      const utterance = new SpeechSynthesisUtterance(textToSpeak);

      // Apply talkback settings
      utterance.rate = config.TALKBACK.TTS_PLAYBACK_RATE;
      utterance.pitch = config.TALKBACK.TTS_PITCH;
      utterance.lang = 'en-US';
      utterance.voice = findVoiceByName('Zira', 'en-US');

      // Event handlers
      utterance.onstart = () => {
        setIsReading(true);
        setIsPaused(false);
      };

      utterance.onend = () => {
        setIsReading(false);
        setCurrentUtterance(null);
        if (onComplete) onComplete();
      };

      utterance.onerror = (event) => {
        // 'interrupted' is expected when user cancels/clicks next, not a real error
        if (event.error !== 'interrupted') {
          console.error('TTS error:', event.error);
        }
        setIsReading(false);
        if (onComplete) onComplete();
      };

      setCurrentUtterance(utterance);
      onCompleteRef.current = onComplete;

      // Cancel any pending utterances first
      synthesisRef.current.cancel();
      synthesisRef.current.speak(utterance);

      return true;
    } catch (error) {
      console.error('Failed to speak:', error);
      return false;
    }
  }, []);

  /**
   * Pause current speech
   */
  const pause = useCallback(() => {
    if (synthesisRef.current && synthesisRef.current.paused === false) {
      synthesisRef.current.pause();
      setIsPaused(true);
    }
  }, []);

  /**
   * Resume paused speech
   */
  const resume = useCallback(() => {
    if (synthesisRef.current && synthesisRef.current.paused === true) {
      synthesisRef.current.resume();
      setIsPaused(false);
    }
  }, []);

  /**
   * Stop all speech and clear queue
   */
  const stop = useCallback(() => {
    cancelAllSpeech();
    setIsReading(false);
    setIsPaused(false);
    setCurrentUtterance(null);
    setQueue([]);
    onCompleteRef.current = null;
  }, []);

  /**
   * Add text to queue and speak sequentially
   */
  const addToQueue = useCallback((text, onComplete = null) => {
    setQueue((prev) => [...prev, { text, onComplete }]);
  }, []);

  /**
   * Process queue one item at a time
   */
  useEffect(() => {
    if (!isReading && queue.length > 0) {
      const next = queue[0];
      setQueue((prev) => prev.slice(1));
      speak(next.text, next.onComplete);
    }
  }, [isReading, queue, speak]);

  /**
   * Get current state
   */
  const getState = useCallback(() => {
    return {
      isReading: isSpeaking(),
      isPaused: synthesisRef.current?.paused || false,
      queueLength: queue.length,
    };
  }, [queue.length]);

  return {
    speak,
    pause,
    resume,
    stop,
    addToQueue,
    getState,
    isReading,
    isPaused,
    queueLength: queue.length,
  };
};

export default useSpeechSynthesis;
