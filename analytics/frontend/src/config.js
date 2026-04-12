/**
 * Application Configuration
 * Centralized environment variables and configuration
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
const WS_BASE_URL =
  window.location.protocol === 'https:'
    ? `wss://${window.location.host}/api`
    : `ws://${window.location.host}/api`;

export const config = {
  // API Configuration
  API: {
    BASE_URL: API_BASE_URL,
    QUERY_ENDPOINT: `${API_BASE_URL}/query`,
    QUERY_STREAM_ENDPOINT: `${API_BASE_URL}/query/stream`,
    QUERY_CLARIFY_ENDPOINT: `${API_BASE_URL}/query/clarify`,
    QUERY_CLARIFY_NEXT_ENDPOINT: `${API_BASE_URL}/query/clarify/next`,
    REPORTS_ENDPOINT: `${API_BASE_URL}/reports`,
    SESSIONS_ENDPOINT: `${API_BASE_URL}/sessions`,
    DASHBOARD_ENDPOINT: `${API_BASE_URL}/dashboard`,
    HISTORY_ENDPOINT: `${API_BASE_URL}/history`,
    WS_ENDPOINT: WS_BASE_URL,
  },

  // Application Settings
  APP: {
    NAME: 'SQL Swarm - Supply Chain Intelligence',
    VERSION: '1.0.0',
    AUTO_CLOSE_PROCESSING_MODAL: true, // Automatically close modal and show results after pipeline completes
  },

  // API Timeouts (in milliseconds)
  TIMEOUTS: {
    QUERY: 300000, // 5 minutes
    REPORT: 60000, // 1 minute
    DASHBOARD: 120000, // 2 minutes
  },

  // Talkback Settings (Hands-free conversational AI)
  TALKBACK: {
    ENABLED: true,
    DEFAULT_STATE: false, // RED (disabled) by default
    VOICE_INPUT_TIMEOUT: 5000, // 5 seconds - timeout for manual voice input
    VOICE_INPUT_SILENCE_TIMEOUT: 6000, // 6 seconds - stop listening after silence
    TTS_VOICE: 'en-US',
    TTS_PLAYBACK_RATE: 1.0, // 0.5 - 2.0
    TTS_PITCH: 1.0, // 0.5 - 2.0
    PAUSE_BEFORE_LISTENING: 500, // 500ms pause after reading before auto-listening
    AUTO_SEND_DELAY: 1000, // 1 second - delay before auto-sending voice response
  },
};

// Export convenience functions
export const getApiUrl = (endpoint) => {
  const endpoints = {
    query: config.API.QUERY_ENDPOINT,
    queryStream: config.API.QUERY_STREAM_ENDPOINT,
    queryClarify: config.API.QUERY_CLARIFY_ENDPOINT,
    reports: config.API.REPORTS_ENDPOINT,
    dashboard: config.API.DASHBOARD_ENDPOINT,
  };
  return endpoints[endpoint] || `${config.API.BASE_URL}/${endpoint.replace(/^\/+/, '')}`;
};

export default config;
