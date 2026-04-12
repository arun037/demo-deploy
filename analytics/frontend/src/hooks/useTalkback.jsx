/**
 * useTalkback Hook
 * Main orchestration for talkback sessions
 * Coordinates: talkback toggle state, TTS reading, option selection, session lifecycle
 */

import { useState, useCallback, useEffect } from 'react';
import { config } from '../config.js';
import useSpeechSynthesis from './useSpeechSynthesis.jsx';
import { debugLog, generateMessageId } from '../utils/talkbackUtils.js';

export const useTalkback = () => {
  // Talkback toggle state
  const [talkbackEnabled, setTalkbackEnabled] = useState(() => {
    // Load from sessionStorage on mount, fallback to config default
    const saved = sessionStorage.getItem('talkback_enabled');
    if (saved !== null) {
      return saved === 'true';
    }
    return config.TALKBACK.DEFAULT_STATE;
  });

  // Session state
  const [isActiveTalkbackSession, setIsActiveTalkbackSession] = useState(false);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [allQuestions, setAllQuestions] = useState([]);

  // Input method tracking
  const [lastInputMethod, setLastInputMethod] = useState('keyboard');
  const [messageIdForTracking, setMessageIdForTracking] = useState(null);

  // TTS
  const tts = useSpeechSynthesis();

  // UI state
  const [readingState, setReadingState] = useState(null); // 'reading_question', 'reading_summary', null
  const [listeningState, setListeningState] = useState(null); // 'listening', null

  /**
   * Toggle talkback (RED <-> GREEN)
   */
  const toggleTalkback = useCallback(() => {
    const newState = !talkbackEnabled;
    setTalkbackEnabled(newState);

    debugLog('Talkback', `Toggled to ${newState ? 'GREEN' : 'RED'}`);

    // If toggled to RED, always stop TTS (whether in session or reading summary)
    if (!newState) {
      tts.stop();
      setIsActiveTalkbackSession(false);
      setReadingState(null);
    }

    // Persist to localStorage for this session
    sessionStorage.setItem('talkback_enabled', newState.toString());
}, [talkbackEnabled, tts]);

  /**
   * Mark input method for next message
   */
  const markInputMethod = useCallback((method) => {
    if (!['voice', 'keyboard'].includes(method)) {
      console.warn('Invalid input method:', method);
      return;
    }

    setLastInputMethod(method);
    setMessageIdForTracking(generateMessageId());

    debugLog('Talkback', `Input method marked: ${method}`, {
      messageId: messageIdForTracking,
    });
  }, []);

  /**
   * Determine if talkback should activate for this message
   */
  const shouldActivateTalkback = useCallback(() => {
    const should =
      talkbackEnabled && // Toggle is GREEN
      lastInputMethod === 'voice'; // Message was voice input

    debugLog('Talkback', `Should activate: ${should}`, {
      talkbackEnabled,
      lastInputMethod,
      messageId: messageIdForTracking,
    });

    return should;
  }, [talkbackEnabled, lastInputMethod]);

  /**
   * Start a talkback session with clarification questions
   */
  const startTalkbackSession = useCallback((questions) => {
    if (!questions || questions.length === 0) {
      return false;
    }

    debugLog('Talkback', 'Starting session', { questionCount: questions.length });

    setAllQuestions(questions);
    setCurrentQuestionIndex(0);
    setCurrentQuestion(questions[0]);
    setIsActiveTalkbackSession(true);
    setReadingState('reading_question');

    // Immediately read first question
    readQuestion(questions[0], 0, questions.length);

    return true;
  }, []);

  /**
   * Read a question aloud
   */
  const readQuestion = useCallback((question, index, total) => {
    if (!question) {
      console.error('Talkback: Question is null/undefined');
      return;
    }
    
    const text = question.question || question.text || JSON.stringify(question);
    const questionNum = index + 1;

    debugLog('Talkback', 'Reading question', {
      index: questionNum,
      total,
      text: text.substring(0, 50),
    });

    setReadingState('reading_question');

    const onReadComplete = () => {
      setReadingState(null);
      debugLog('Talkback', 'Question read complete', { index: questionNum });
    };

    const textToRead = `Question ${questionNum} of ${total}: ${text}`;
    tts.speak(textToRead, onReadComplete);
  }, [tts, allQuestions, currentQuestionIndex]);

  /**
   * Handle answer selection (user clicked an option)
   */
  const handleAnswerSelected = useCallback((answer) => {
    debugLog('Talkback', 'Answer selected', {
      index: currentQuestionIndex,
      answer: answer.substring(0, 50),
    });

    // Stop current TTS gracefully
    tts.stop();
    setReadingState(null);

    // Move to next question
    const nextIndex = currentQuestionIndex + 1;

    if (nextIndex < allQuestions.length) {
      // More questions
      setCurrentQuestionIndex(nextIndex);
      setCurrentQuestion(allQuestions[nextIndex]);

      // Brief pause before reading next question
      setTimeout(() => {
        readQuestion(allQuestions[nextIndex], nextIndex, allQuestions.length);
      }, config.TALKBACK.PAUSE_BEFORE_LISTENING);
    } else {
      // All questions answered - session will end when summary is read
      debugLog('Talkback', 'All questions answered');
      setReadingState(null);
      setIsActiveTalkbackSession(false);
    }
  }, [currentQuestionIndex, allQuestions, readQuestion, tts]);

  /**
   * Read final summary aloud (end of session)
   */
  const readSummary = useCallback((summaryText) => {
    debugLog('Talkback', 'Reading summary', { length: summaryText?.length });

    // Ensure any previous TTS is stopped before starting summary
    tts.stop();
    
    // Brief delay to ensure TTS is stopped before starting again
    setTimeout(() => {
      setReadingState('reading_summary');

      const onReadComplete = () => {
        debugLog('Talkback', 'Summary read complete');
        setReadingState(null);
        stopTalkbackSession();
      };

      tts.speak(summaryText, onReadComplete);
    }, 100);
  }, [tts]);

  /**
   * Stop talkback session
   */
  const stopTalkbackSession = useCallback(() => {
    debugLog('Talkback', 'Stopping session');

    tts.stop();
    setIsActiveTalkbackSession(false);
    setReadingState(null);
    setListeningState(null);
    setCurrentQuestionIndex(0);
    setCurrentQuestion(null);
    setAllQuestions([]);
}, [tts]);

  /**
   * Load talkback state from storage on mount
   */
  useEffect(() => {
    const saved = sessionStorage.getItem('talkback_enabled');
    if (saved !== null) {
      setTalkbackEnabled(saved === 'true');
    }
  }, []);

  return {
    // Toggle
    talkbackEnabled,
    toggleTalkback,

    // Session state
    isActiveTalkbackSession,
    currentQuestionIndex,
    currentQuestion,
    allQuestions,

    // Input tracking
    lastInputMethod,
    markInputMethod,
    shouldActivateTalkback,

    // Session control
    startTalkbackSession,
    readQuestion,
    handleAnswerSelected,
    readSummary,
    stopTalkbackSession,

    // UI states
    readingState,
    listeningState,

    // Sub-hooks
    tts,
  };
};

export default useTalkback;
