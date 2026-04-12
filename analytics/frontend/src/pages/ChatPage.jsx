import React, { useState, useRef, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import MessageList from '../components/MessageList.jsx';
import ToastNotification from '../components/ToastNotification.jsx';
import ProcessingModal from '../components/ProcessingModal.jsx';
import ReportNameModal from '../components/ReportNameModal.jsx';
import { Send, Mic, Paperclip, Square, Loader2, MessageSquarePlus } from 'lucide-react';

import { config } from '../config.js';
import { useTalkback } from '../hooks/useTalkback.jsx';
import { useContainerWidth } from '../hooks/useContainerWidth.js';


function ChatPage({ isAdmin = false }) {
  const WELCOME_MESSAGE = {
    role: 'assistant',
    content: `**Welcome to Data Analytics Platform!**

I'm your AI-powered Business Analyst, ready to help you explore and analyze your business data.
Feel free to ask me anything about your data!`,
    timestamp: new Date().toISOString(),
    isWelcome: true
  };

  // Session state
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([WELCOME_MESSAGE]);

  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [notification, setNotification] = useState(null);
  const bottomRef = useRef(null);
  const location = useLocation();

  // WebSocket state
  const [showProcessingModal, setShowProcessingModal] = useState(false);
  const [processingLogs, setProcessingLogs] = useState([]);
  const [processingComplete, setProcessingComplete] = useState(false);
  const [processingError, setProcessingError] = useState(null);
  const wsRef = useRef(null);

  // Clarification state
  const [showClarificationModal, setShowClarificationModal] = useState(false);
  const [clarificationQuestions, setClarificationQuestions] = useState([]);
  const [clarificationContext, setClarificationContext] = useState(null);
  const [originalQuery, setOriginalQuery] = useState('');

  // Report name modal state
  const [showReportNameModal, setShowReportNameModal] = useState(false);
  // pendingReport holds query_id + SQL fallback fields set when user clicks Bookmark
  const [pendingReport, setPendingReport] = useState(null);
  const [suggestedReportName, setSuggestedReportName] = useState('');
  const [isSavingReport, setIsSavingReport] = useState(false);

  // Talkback state
  const {
    talkbackEnabled,
    startTalkbackSession,
    handleAnswerSelected,
    readSummary,
    markInputMethod,
  } = useTalkback();
  const { isNarrow } = useContainerWidth();

  const showNotification = (message, type = 'info') => {
    setNotification({ message, type, id: Date.now() });
  };

  // Session Management Functions
  const createNewSession = async () => {
    try {
      const res = await fetch(`${config.API.SESSIONS_ENDPOINT}/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      const data = await res.json();

      if (data.success) {
        setCurrentSessionId(data.session_id);
        localStorage.setItem('app_current_session_id', data.session_id);
        setMessages([WELCOME_MESSAGE]);
        console.log('Created new session:', data.session_id);
      }
    } catch (error) {
      console.error('Failed to create session:', error);
      showNotification('Failed to create chat session', 'error');
    }
  };

  const loadSession = async (sessionId) => {
    try {
      const res = await fetch(`${config.API.SESSIONS_ENDPOINT}/${sessionId}`);
      const data = await res.json();

      if (data.success) {
        setCurrentSessionId(data.session_id);
        localStorage.setItem('app_current_session_id', data.session_id);
        setMessages(data.messages.length > 0 ? data.messages : [WELCOME_MESSAGE]);
        console.log('Loaded session:', sessionId);
      } else {
        // Session not found, create new one
        await createNewSession();
      }
    } catch (error) {
      console.error('Failed to load session:', error);
      await createNewSession();
    }
  };

  // Helper to trim message data for storage (keep only 50 rows)
  const trimMessageForStorage = (message) => {
    if (message.role !== 'assistant' || !message.sqlData) {
      return message;
    }

    // Create a copy and trim data to 50 rows
    const trimmed = {
      ...message,
      sqlData: {
        ...message.sqlData,
        data: message.sqlData.data.slice(0, 50) // Only keep first 50 rows
      }
    };

    return trimmed;
  };

  const saveMessageToSession = async (message, sessionId = null) => {
    const idToUse = sessionId || currentSessionId;
    if (!idToUse) {
      console.warn('Cannot save message - no session ID');
      return;
    }

    try {
      console.log('Saving message to session:', idToUse, message.role);

      // Trim data before saving
      const messageToSave = trimMessageForStorage(message);

      const response = await fetch(`${config.API.SESSIONS_ENDPOINT}/${idToUse}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: messageToSave })
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Failed to save message - HTTP error:', response.status, errorText);
      } else {
        console.log('Message saved successfully');
      }
    } catch (error) {
      console.error('Failed to save message to session:', error);
    }
  };

  const handleNewChat = async () => {
    await createNewSession();
  };

  // Listen for 'app-new-chat' event from Layout
  useEffect(() => {
    const handleNewChatEvent = () => {
      handleNewChat();
    };

    window.addEventListener('app-new-chat', handleNewChatEvent);
    return () => {
      window.removeEventListener('app-new-chat', handleNewChatEvent);
    };
  }, []);

  // Session management: Create or load session on mount AND on navigation back
  useEffect(() => {
    const initializeSession = async () => {
      // Skip if coming from Popular page with initialMessage (auto-send will handle it)
      if (location.state?.initialMessage) {
        return;
      }

      // Check if we have a session from navigation (e.g., from chat history page)
      if (location.state?.sessionId) {
        await loadSession(location.state.sessionId);
        return;
      }

      // Check localStorage for current session and reload it
      const savedSessionId = localStorage.getItem('app_current_session_id');
      if (savedSessionId) {
        await loadSession(savedSessionId);
      } else {
        await createNewSession();
      }
    };

    initializeSession();
  }, [location.pathname]); // Re-run when navigating back to chat

  // Streaming API handler
  const sendQueryViaAPI = async (queryText, overrideSessionId = null) => {
    // Use provided session ID or fall back to current state
    const sessionIdForSaving = overrideSessionId || currentSessionId;

    try {
      // Reset processing state
      setProcessingLogs([]);
      setProcessingComplete(false);
      setProcessingError(null);
      // setShowProcessingModal(true); // Don't show immediately for Chat

      // Call Streaming API
      const response = await fetch(`${config.API.QUERY_STREAM_ENDPOINT}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: queryText,
          session_id: sessionIdForSaving
        })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;

        // Split by double newline (SSE format)
        const lines = buffer.split('\n\n');
        buffer = lines.pop(); // Keep incomplete chunk

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.replace('data: ', '');
            try {
              const event = JSON.parse(dataStr);

              // Check for Request Type to convert to Modal
              if (event.type === 'log') {
                // Don't show modal during insights phase - it runs in background
                if (event.phase !== 'INSIGHTS') {
                  if (event.phase === 'ROUTER' && event.data?.request_type === 'DATA') {
                    setShowProcessingModal(true);
                  }
                  // Also open for heavy phases if missed (legacy support)
                  if (['PLANNER', 'SQL_GENERATION', 'VALIDATOR'].includes(event.phase)) {
                    setShowProcessingModal(true);
                  }
                }
                setProcessingLogs(prev => [...prev, {
                  phase: event.phase,
                  message: event.message,
                  data: event.data,
                  receivedAt: Date.now()
                }]);
              } else if (event.type === 'clarification_needed') {
                // Sequential clarification  backend sends only 1 question at a time
                setProcessingLogs(prev => [...prev, {
                  phase: 'CLARIFICATION',
                  message: 'Need more details to ensure accuracy',
                  data: event
                }]);

                // Store clarification metadata for re-evaluation
                setClarificationContext(event.context);
                setOriginalQuery(event.original_query);

                const firstQuestion = event.questions[0];
                const clarificationMessage = {
                  role: 'assistant',
                  content: `**Question:**\n${firstQuestion.question}`,
                  clarificationState: {
                    answeredPairs: [],  // No answers yet
                    context: event.context,
                    originalQuery: event.original_query,
                    currentQuestion: firstQuestion,
                    intent: event.intent || 'AGGREGATION',
                    schemaContext: event.schema_context || '',
                    sessionId: event.session_id || sessionIdForSaving
                  },
                  clarificationOptions: firstQuestion.options || [],
                  timestamp: new Date().toISOString(),
                  isAwaitingClarification: true
                };

                setMessages(prev => [...prev, clarificationMessage]);
                await saveMessageToSession(clarificationMessage, sessionIdForSaving);
                setShowProcessingModal(false);
                setIsLoading(false);

                // Talkback: Start session if enabled
                if (talkbackEnabled && event.questions.length > 0) {
                  setTimeout(() => {
                    startTalkbackSession(event.questions);
                  }, 500);
                }

                // Talkback: Start session if enabled
                if (talkbackEnabled && event.questions.length > 0) {
                  setTimeout(() => {
                    startTalkbackSession(event.questions);
                  }, 500);
                }

                // Don't continue  wait for user input
                return;
              } else if (event.type === 'clarification') {
                // Show clarification questions
                const clarificationMessage = {
                  role: 'assistant',
                  content: event.message,
                  clarificationQuestions: event.questions,
                  timestamp: new Date().toISOString()
                };
                setMessages(prev => [...prev, clarificationMessage]);

                // Save clarification message to session
                await saveMessageToSession(clarificationMessage, sessionIdForSaving);

                setPendingClarification(event.questions);
                setIsLoading(false);

                // Don't continue processing - wait for user input
                return;
              } else if (event.type === 'error') {
                setProcessingError(event.message);
                setProcessingComplete(true);
              } else if (event.type === 'result') {
                setProcessingComplete(true);

                const isDetailedReport = event.metadata?.intent === 'DETAILED_REPORT';

                // Add assistant message with results
                const assistantMessage = {
                  role: 'assistant',
                  content: event.ai_response || 'Query completed successfully.',
                  sqlData: {
                    data: event.data || [],
                    columns: event.data && event.data.length > 0 ? Object.keys(event.data[0]) : [],
                    count: event.row_count || 0
                  },
                  responseMeta: {
                    showGenerateReportButton: false, // Hide "Generate Report" (assuming legacy button)
                    showSaveButton: true, // Always true, controlled by classification in MessageList
                    classification: event.classification || event.metadata?.classification || 'NON_REPORT',
                    query_id: event.query_id || event.metadata?.query_id,
                    responseType: 'sql_result',
                    userQuery: queryText,
                    generatedSql: event.sql,
                    intent: event.metadata?.intent,
                    //  NEW: Full conversational context
                    schemaContext: event.metadata?.schemaContext || null,
                    schemaHash: event.metadata?.schemaHash || null,
                    tablesUsed: event.metadata?.tablesUsed || [],
                    plan: event.metadata?.plan || null,
                    rowCount: event.metadata?.rowCount || 0,
                    executionTimeMs: event.metadata?.executionTimeMs || 0
                  },
                  timestamp: new Date().toISOString(),
                  insight: event.insight // Capture insight from result payload
                };
                console.log("Response Meta:", assistantMessage.responseMeta); // Debugging
                setMessages(prev => [...prev, assistantMessage]);

                // Save assistant message to session
                await saveMessageToSession(assistantMessage, sessionIdForSaving);

                // Talkback: Read final response if talkback is enabled (regardless of input method)
                if (talkbackEnabled) {
                  setTimeout(() => {
                    readSummary(event.ai_response || 'Query completed successfully.');
                  }, 500);
                }

                // Mark as complete and close modal immediately to show results
                setProcessingComplete(true);
                // Close modal immediately after results - insights will run in background
                if (config.APP.AUTO_CLOSE_PROCESSING_MODAL) {
                  setTimeout(() => {
                    setShowProcessingModal(false);
                  }, 500);
                }
              } else if (event.type === 'insight') {
                // Update the last assistant message with insight data
                // event.data contains { charts: [...], summary: ... } directly
                // Insights run in background - no modal, just update the message silently
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMsgIndex = newMessages.findLastIndex(m => m.role === 'assistant');
                  if (lastMsgIndex !== -1) {
                    const updatedMessage = {
                      ...newMessages[lastMsgIndex],
                      insight: event.data // Save the insight data directly
                    };
                    newMessages[lastMsgIndex] = updatedMessage;

                    // Save the updated message with charts (using IIFE to call async)
                    (async () => {
                      await saveMessageToSession(updatedMessage, sessionIdForSaving);
                    })();
                  }
                  return newMessages;
                });
                // Don't show modal for insights - they run silently in background
              }
            } catch (e) {
              console.error('Error parsing SSE event:', e);
            }
          }
        }
      }

    } catch (error) {
      console.error('API error:', error);
      setProcessingError(error.message);
      setProcessingComplete(true);
      setShowProcessingModal(false); // keep open on error to show error state? No, error state handled in state
      // If modal is closed, error toast maybe?
      // Actually ProcessingModal stays open and shows error if we don't close it
    }
  };

  // --- Voice Input Logic ---
  const [isRecording, setIsRecording] = useState(false);
  const recognitionRef = useRef(null);
  const silenceTimer = useRef(null);

  // Helper to reset the silence timer
  const resetSilenceTimer = () => {
    if (silenceTimer.current) clearTimeout(silenceTimer.current);
    silenceTimer.current = setTimeout(() => {
      stopRecording();
      showNotification('Voice input stopped due to silence', 'info');
    }, 6000); // 6 seconds silence timeout
  };

  useEffect(() => {
    // Initialize SpeechRecognition if available
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        resetSilenceTimer();
      };

      recognition.onresult = (event) => {
        resetSilenceTimer(); // Reset timer on speech activity

        const currentSessionTranscript = Array.from(event.results)
          .map(result => result[0].transcript)
          .join('');

        // Logic: Input = (Prefix + ' ' + Transcript).trim()
        const prefix = textBeforeRecordingRef.current;
        const spacer = (prefix && !prefix.endsWith(' ')) ? ' ' : '';
        setInput(prefix + spacer + currentSessionTranscript);
      };

      recognition.onerror = (event) => {
        console.error('Speech recognition error', event.error);
        if (event.error !== 'no-speech') {
          stopRecording();
          showNotification('Voice input error: ' + event.error, 'error');
        }
      };

      recognition.onend = () => {
        setIsRecording(false);
        if (silenceTimer.current) clearTimeout(silenceTimer.current);
      };

      recognitionRef.current = recognition;
    }
  }, []); // Init once

  // We need to handle the "Append vs Replace" logic better.
  const [textBeforeRecording, setTextBeforeRecording] = useState('');
  // We use a ref to capture the text input state at the moment recording starts.
  // This avoids the issue where `input` state updates during recording causing recursive duplication.
  const textBeforeRecordingRef = useRef('');

  const startRecording = () => {
    if (recognitionRef.current) {
      textBeforeRecordingRef.current = input; // Snapshot current text ONCE
      try {
        recognitionRef.current.start();
        setIsRecording(true);
      } catch (e) {
        console.error("Failed to start", e);
      }
    } else {
      showNotification('Voice input not supported in this browser.', 'error');
    }
  };

  const stopRecording = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      setIsRecording(false);
    }
    if (silenceTimer.current) clearTimeout(silenceTimer.current);
  };

  const toggleRecording = () => {
    if (isRecording) {
      stopRecording();
    } else {
      // Snapshot happens in startRecording now, but we can do it here too for safety if we pass input 
      // but startRecording uses the closure 'input' which might be stale if startRecording isn't recreated.
      // Wait, startRecording IS recreated on every render because correct deps aren't listed (it's inside component).
      startRecording();
    }
  };


  // Auto-fill and send if coming from Popular page
  useEffect(() => {
    if (location.state?.initialMessage) {
      const message = location.state.initialMessage;

      // Auto-send the message
      const sendMessage = async () => {
        // First ensure we have a session
        let sessionId = currentSessionId;
        if (!sessionId) {
          const savedSessionId = localStorage.getItem('app_current_session_id');
          if (savedSessionId) {
            await loadSession(savedSessionId);
            sessionId = savedSessionId;
          } else {
            // Create new session and wait for it
            const res = await fetch(`${config.API.SESSIONS_ENDPOINT}/create`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({})
            });
            const data = await res.json();
            if (data.success) {
              sessionId = data.session_id;
              setCurrentSessionId(sessionId);
              localStorage.setItem('app_current_session_id', sessionId);
              setMessages([WELCOME_MESSAGE]);
            }
          }
        }

        // Add User Message to state first
        const userMessage = {
          role: 'user',
          content: message,
          timestamp: new Date().toISOString()
        };

        setMessages((prev) => [...prev, userMessage]);

        // Save to session using the sessionId we just got
        if (sessionId) {
          try {
            await fetch(`${config.API.SESSIONS_ENDPOINT}/${sessionId}/messages`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ message: userMessage })
            });
          } catch (error) {
            console.error('Failed to save user message:', error);
          }
        }

        setIsLoading(true);

        // Send via API with the session ID we just got
        await sendQueryViaAPI(message, sessionId);

        setIsLoading(false);
      };

      sendMessage();

      // Clear the location state to prevent re-sending on re-render
      window.history.replaceState({}, document.title);
    }
  }, [location.state]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const processUserResponse = async (text) => {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;

    // Stop recording if active
    if (isRecording) {
      stopRecording();
    }

    // Mark input method for talkback
    const inputMethod = isRecording ? 'voice' : 'keyboard';
    markInputMethod(inputMethod);

    // Check if we're in clarification mode
    const lastMessage = messages[messages.length - 1];
    const isAnsweringClarification = lastMessage && lastMessage.isAwaitingClarification;

    // 1. Add User Message
    const userMessage = {
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString(),
      inputMethod: inputMethod
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');

    // Save user message to session
    await saveMessageToSession(userMessage);

    // 2. If answering clarification  call backend for next question
    if (isAnsweringClarification) {
      const state = lastMessage.clarificationState;
      const currentQ = state.currentQuestion;

      // Build updated answered pairs
      const updatedPairs = [
        ...state.answeredPairs,
        {
          id: (state.answeredPairs.length + 1),
          question: currentQ.question,
          answer: trimmed,
          category: currentQ.category || `q${state.answeredPairs.length + 1}`
        }
      ];

      // Show thinking indicator
      setIsLoading(true);

      try {
        // Call backend to decide next question
        const response = await fetch(`${config.API.QUERY_CLARIFY_NEXT_ENDPOINT}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            original_query: state.originalQuery,
            answered_pairs: updatedPairs,
            context: state.context,
            intent: state.intent,
            schema_context: state.schemaContext,
            session_id: state.sessionId || currentSessionId
          })
        });

        // Check content type to determine if it's JSON (next question) or SSE (pipeline)
        const contentType = response.headers.get('content-type') || '';

        if (contentType.includes('application/json')) {
          // Backend returned a next question
          const data = await response.json();

          if (data.type === 'next_question' && data.question) {
            const nextQ = data.question;
            const nextMessage = {
              role: 'assistant',
              content: `**Question:**\n${nextQ.question}`,
              clarificationState: {
                answeredPairs: updatedPairs,
                context: state.context,
                originalQuery: state.originalQuery,
                currentQuestion: nextQ,
                intent: state.intent,
                schemaContext: state.schemaContext,
                sessionId: state.sessionId
              },
              clarificationOptions: nextQ.options || [],
              timestamp: new Date().toISOString(),
              isAwaitingClarification: true
            };

            setMessages(prev => [...prev, nextMessage]);
            await saveMessageToSession(nextMessage);
            setIsLoading(false);
          }
        } else {
          // Backend returned streaming pipeline response (clarification done)
          const processingMessage = {
            role: 'assistant',
            content: '[OK] Got it! Processing your request now...',
            timestamp: new Date().toISOString()
          };
          setMessages(prev => [...prev, processingMessage]);
          await saveMessageToSession(processingMessage);

          setShowProcessingModal(true);
          setProcessingLogs([]);
          setProcessingComplete(false);
          setProcessingError(null);

          // Parse the SSE stream
          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';

          while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop();

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const event = JSON.parse(line.replace('data: ', ''));

                  if (event.type === 'log') {
                    // Don't show modal during insights phase - it runs in background
                    if (event.phase !== 'INSIGHTS') {
                      setShowProcessingModal(true);
                    }
                    setProcessingLogs(prev => [...prev, {
                      phase: event.phase,
                      message: event.message,
                      data: event.data,
                      receivedAt: Date.now()
                    }]);
                  } else if (event.type === 'error') {
                    setProcessingError(event.message);
                    setProcessingComplete(true);
                  } else if (event.type === 'result') {
                    setProcessingComplete(true);
                    const assistantMessage = {
                      role: 'assistant',
                      content: event.ai_response || 'Query completed successfully.',
                      sqlData: {
                        data: event.data || [],
                        columns: event.data && event.data.length > 0 ? Object.keys(event.data[0]) : [],
                        count: event.row_count || 0
                      },
                      responseMeta: {
                        showGenerateReportButton: false,
                        showSaveButton: true,
                        ...(event.metadata || {}),
                        userQuery: state.originalQuery,
                        generatedSql: event.sql
                      },
                      timestamp: new Date().toISOString(),
                      insight: event.insight
                    };
                    setMessages(prev => [...prev, assistantMessage]);
                    await saveMessageToSession(assistantMessage);
                  } else if (event.type === 'insight') {
                    setMessages(prev => {
                      const newMsgs = [...prev];
                      const idx = newMsgs.findLastIndex(m => m.role === 'assistant');
                      if (idx !== -1) {
                        const updated = { ...newMsgs[idx], insight: event.data };
                        newMsgs[idx] = updated;
                        (async () => { await saveMessageToSession(updated); })();
                      }
                      return newMsgs;
                    });
                    // Auto-close modal if configured to do so (after insights complete)
                    if (config.APP.AUTO_CLOSE_PROCESSING_MODAL) {
                      setTimeout(() => {
                        setShowProcessingModal(false);
                      }, 1000);
                    }
                  }
                } catch (e) {
                  console.error('Error parsing SSE:', e);
                }
              }
            }
          }

          setIsLoading(false);
        }
      } catch (error) {
        console.error('Clarification next error:', error);
        setIsLoading(false);

        const errorMessage = {
          role: 'assistant',
          content: '[FAIL] Something went wrong processing your answer. Please try again.',
          timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, errorMessage]);
      }

      return; // Don't process as normal query
    }

    // 3. Normal query processing
    setIsLoading(true);
    await sendQueryViaAPI(trimmed);

    setIsLoading(false);
  };

  const handleSend = async (e) => {
    e.preventDefault();
    await processUserResponse(input);
  };

  const handleOptionSelect = async (optionText) => {
    // Stop talkback for current question and move to next
    handleAnswerSelected(optionText);
    await processUserResponse(optionText);
  };

  const submitClarifications = async (originalQuery, clarifications, context) => {
    // Capture session ID for saving messages
    const sessionIdForSaving = currentSessionId;

    setIsLoading(true);
    setShowProcessingModal(true);
    setProcessingLogs([]);
    setProcessingComplete(false);
    setProcessingError(null);

    try {
      const response = await fetch(`${config.API.QUERY_CLARIFY_ENDPOINT}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          original_query: originalQuery,
          clarifications: clarifications,
          context: context,
          session_id: sessionIdForSaving
        })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;

        // Split by double newline (SSE format)
        const lines = buffer.split('\n\n');
        buffer = lines.pop(); // Keep incomplete chunk

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.replace('data: ', '');
            try {
              const event = JSON.parse(dataStr);

              if (event.type === 'log') {
                // Don't show modal during insights phase - it runs in background
                if (event.phase !== 'INSIGHTS' && !showProcessingModal) {
                  // Only open modal for non-insights phases
                }
                setProcessingLogs(prev => [...prev, {
                  phase: event.phase,
                  message: event.message,
                  data: event.data,
                  receivedAt: Date.now()
                }]);
              } else if (event.type === 'error') {
                setProcessingError(event.message);
                setProcessingComplete(true);
              } else if (event.type === 'result') {
                setProcessingComplete(true);

                const isDetailedReport = event.metadata?.intent === 'DETAILED_REPORT';

                // Add assistant message with results
                const assistantMessage = {
                  role: 'assistant',
                  content: event.ai_response || 'Query completed successfully.',
                  sqlData: {
                    data: event.data || [],
                    columns: event.data && event.data.length > 0 ? Object.keys(event.data[0]) : [],
                    count: event.row_count || 0
                  },
                  responseMeta: {
                    // UI control flags
                    showGenerateReportButton: false,
                    showSaveButton: true,
                    responseType: 'sql_result',

                    // Copy ALL metadata from backend automatically
                    ...(event.metadata || {}),

                    // Override/add frontend-specific fields
                    userQuery: originalQuery,
                    generatedSql: event.sql
                  },
                  timestamp: new Date().toISOString(),
                  insight: event.insight
                };
                setMessages(prev => [...prev, assistantMessage]);

                // Save assistant message to session
                await saveMessageToSession(assistantMessage, sessionIdForSaving);

                // Talkback: Read final response from clarification flow
                if (talkbackEnabled) {
                  setTimeout(() => {
                    readSummary(event.ai_response || 'Query completed successfully.');
                  }, 500);
                }

                // Mark as complete and close modal immediately to show results
                setProcessingComplete(true);
                // Close modal immediately after results - insights will run in background
                if (config.APP.AUTO_CLOSE_PROCESSING_MODAL) {
                  setTimeout(() => {
                    setShowProcessingModal(false);
                  }, 500);
                }
              } else if (event.type === 'insight') {
                // Update the last assistant message with insight data and save
                // Insights run in background - no modal, just update silently
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMsgIndex = newMessages.findLastIndex(m => m.role === 'assistant');
                  if (lastMsgIndex !== -1) {
                    const updatedMessage = {
                      ...newMessages[lastMsgIndex],
                      insight: event.data // Save insight data directly
                    };
                    newMessages[lastMsgIndex] = updatedMessage;

                    // Save the updated message with charts
                    (async () => {
                      await saveMessageToSession(updatedMessage, sessionIdForSaving);
                    })();
                  }
                  return newMessages;
                });
                // Don't show modal for insights - they run silently in background
              }
            } catch (e) {
              console.error('Error parsing SSE event:', e);
            }
          }
        }
      }

    } catch (error) {
      console.error('Clarification API error:', error);
      setProcessingError(error.message);
      setProcessingComplete(true);
    } finally {
      setIsLoading(false);
    }
  };

  // queryId, suggestedTitle, generatedSql, userQuery, columns all come from MessageList Bookmark click
  const handleSaveReport = async (queryId, suggestedTitle, generatedSql, userQuery, columns, charts) => {
    if (!queryId && !generatedSql) {
      showNotification('Cannot save report: No query ID or SQL available', 'error');
      return;
    }

    // Store everything needed for the save path
    setPendingReport({ queryId, generatedSql, userQuery, columns, charts: charts || [] });

    // Set suggested name instantly from prop/fallback context
    setSuggestedReportName(suggestedTitle || '');

    setShowReportNameModal(true);
  };

  const handleConfirmSaveReport = async (reportName) => {
    if (!pendingReport) {
      showNotification('Cannot save report: No pending report data', 'error');
      return;
    }

    setIsSavingReport(true);
    const { queryId, generatedSql, userQuery, columns, charts } = pendingReport;

    try {
      if (!generatedSql) {
        throw new Error('No SQL available to save the report.');
      }

      const res = await fetch(`${config.API.REPORTS_ENDPOINT}/save-from-sql`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sql: generatedSql,
          user_query: userQuery || 'Saved Report',
          columns: columns || [],
          classification: 'STRONG_REPORT',
          custom_title: reportName || null,
          user_id: 'default_user',
          charts: charts || []
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to save report');
      }

      setShowReportNameModal(false);
      setPendingReport(null);
      setIsSavingReport(false);
      showNotification('Report saved successfully!', 'success');

    } catch (error) {
      console.error('Save failed', error);
      showNotification(`Failed to save: ${error.message}`, 'error');
      setIsSavingReport(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gradient-to-br from-gray-50 to-brand-teal/10">



      {/* Messages Area - Full Width */}
      <div className="flex-1 overflow-hidden relative flex flex-col">
        <div className="flex-1 overflow-y-auto w-full px-2 sm:px-4 pr-2 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
          <div className="flex-1 overflow-y-auto w-full px-2 sm:px-4">
            <MessageList messages={messages} onGenerateReport={handleSaveReport} onOptionSelect={handleOptionSelect} isAdmin={isAdmin} />
            <div ref={bottomRef} />
          </div>
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Voice Input Active Card */}
      {isRecording && (
        <div className={`${isNarrow ? 'px-2' : 'px-4'} pb-2`}>
          <div className={`bg-white rounded-xl shadow-lg border border-brand-teal/20 ${isNarrow ? 'p-2' : 'p-4'} ${isNarrow ? 'flex-col' : 'flex items-center justify-between'} animate-in slide-in-from-bottom-2 fade-in duration-300`}>
            <div className={`flex items-center ${isNarrow ? 'gap-2' : 'gap-4'} ${isNarrow ? 'mb-2' : ''}`}>
              <img src="/logo/logo.png" alt="Company Logo" className={`${isNarrow ? 'h-8 w-8' : 'h-12 w-12'} object-contain bg-white p-1 rounded-md`} />
              <div className={isNarrow ? 'flex-1 min-w-0' : ''}>
                {!isNarrow && (
                  <div className="logo-text">
                    <div className="company-name">DATA ANALYTICS PLATFORM</div>
                    <div className="tagline">BUSINESS INTELLIGENCE</div>
                  </div>
                )}
                <div>
                  <h3 className={`font-semibold text-brand-navy ${isNarrow ? 'text-xs' : 'text-sm'}`}>Voice Input Active</h3>
                  <p className={`text-brand-navy/60 ${isNarrow ? 'text-[10px]' : 'text-xs'}`}>Speak clearly into your microphone</p>
                </div>
              </div>
            </div>

            <div className={`flex items-center ${isNarrow ? 'justify-between' : 'justify-center'} gap-1 h-8 ${isNarrow ? 'px-2' : 'px-4'} ${isNarrow ? '' : 'flex-1 max-w-[120px]'}`}>
              {/* Visualizer / Waveform (CSS Simulated) */}
              <div className="flex items-center justify-center gap-1 h-8">
                <div className="w-1 bg-brand-teal h-3 animate-[pulse_1s_ease-in-out_infinite]"></div>
                <div className="w-1 bg-brand-teal h-6 animate-[pulse_1.2s_ease-in-out_infinite]"></div>
                <div className="w-1 bg-brand-teal h-4 animate-[pulse_0.8s_ease-in-out_infinite]"></div>
                <div className="w-1 bg-brand-teal h-7 animate-[pulse_1.1s_ease-in-out_infinite]"></div>
                <div className="w-1 bg-brand-teal h-3 animate-[pulse_0.9s_ease-in-out_infinite]"></div>
              </div>

              <button
                onClick={stopRecording}
                className={`${isNarrow ? 'p-1.5' : 'p-2'} bg-red-100 hover:bg-red-200 text-red-600 rounded-lg transition-colors border border-red-200`}
                title="Stop recording"
              >
                <Square size={isNarrow ? 16 : 20} fill="currentColor" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="bg-white border-t border-brand-teal/20 p-1.5 sm:p-2">
        <div className="w-full">
          <form onSubmit={handleSend} className="relative flex items-center gap-2">
            <div className="relative flex-1">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask for reports, business guidance, or data analysis..."
                className="w-full rounded-2xl border border-brand-teal/30 bg-white pl-3 sm:pl-4 pr-10 sm:pr-12 py-2 text-xs sm:text-sm shadow-sm outline-none focus:ring-2 focus:ring-brand-teal/50 focus:border-brand-teal transition"
                disabled={isLoading}
              />
              <button
                type="button"
                onClick={toggleRecording}
                className={`absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-full transition ${isRecording ? 'text-red-500 bg-red-50 ring-2 ring-red-200' : 'text-brand-navy/40 hover:text-brand-teal hover:bg-brand-teal/10'}`}
                title="Voice input"
              >
                <Mic size={18} />
              </button>
            </div>

            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="flex items-center justify-center p-2 sm:p-3 rounded-full bg-brand-green text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-brand-green-light transition shadow-md"
            >
              {isLoading ? (
                <div className="h-4 w-4 sm:h-5 sm:w-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <Send size={16} className="sm:w-[18px] sm:h-[18px]" />
              )}
            </button>
          </form>
        </div>
      </div>

      {notification && (
        <ToastNotification
          key={notification.id}
          message={notification.message}
          type={notification.type}
          onClose={() => setNotification(null)}
        />
      )}

      {/* Processing Modal */}
      <ProcessingModal
        isOpen={showProcessingModal}
        onClose={() => setShowProcessingModal(false)}
        logs={processingLogs}
        isComplete={processingComplete}
        error={processingError}
        isAdmin={isAdmin}
      />

      {/* Report Name Modal */}
      <ReportNameModal
        isOpen={showReportNameModal}
        onClose={() => {
          setShowReportNameModal(false);
          setPendingQueryId(null);
          setSuggestedReportName('');
        }}
        onSave={handleConfirmSaveReport}
        suggestedName={suggestedReportName}
        isLoading={isSavingReport}
      />
    </div>
  );
}

export default ChatPage;

