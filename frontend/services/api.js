import axios from 'axios';
import { getStoredToken, clearStoredAuth } from '@/lib/auth';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000,
});

// Request interceptor: Attach JWT token to every request if available
apiClient.interceptors.request.use(
  (config) => {
    const token = getStoredToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: Handle global unauthorized / network errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // If token expired or invalid, clear local auth
      if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
        clearStoredAuth();
      }
    }
    return Promise.reject(error);
  }
);

/**
 * Format API errors into user-friendly messages
 */
export const extractErrorMessage = (error) => {
  if (!error.response) {
    if (error.code === 'ECONNABORTED') {
      return 'The request timed out. Please try again.';
    }
    if (error.message?.includes('Network Error')) {
      return 'Unable to connect to the server. Please try again later.';
    }
    return error.message || 'Unable to connect to the server. Please try again later.';
  }

  const data = error.response.data;
  if (!data) return 'An unexpected error occurred. Please try again.';

    if (typeof data.detail === 'string') {
    return data.detail;
  }

  if (data.detail && typeof data.detail === 'object' && !Array.isArray(data.detail)) {
    return data.detail.message || data.detail.detail || 'An unexpected error occurred. Please try again.';
  }

  if (Array.isArray(data.detail)) {
    // Pydantic validation errors
    return data.detail.map((err) => err.msg || err.message).join('. ');
  }

  return data.message || 'An unexpected error occurred. Please try again.';
};

/**
 * Health check endpoint
 */
export const getHealth = async () => {
  const response = await apiClient.get('/api/health');
  return response.data;
};

/**
 * Check if username is available
 */
export const checkUsername = async (username) => {
  const response = await apiClient.get('/api/auth/check-username', {
    params: { username },
  });
  return response.data;
};

/**
 * Check if email is available and valid
 */
export const checkEmail = async (email) => {
  const response = await apiClient.get('/api/auth/check-email', {
    params: { email },
  });
  return response.data;
};

/**
 * Send a 6-digit OTP to the given email address
 */
export const sendOtp = async (email) => {
  const response = await apiClient.post('/api/auth/send-otp', { email });
  return response.data;
};

/**
 * Verify the OTP for the given email address
 * Returns { verification_token } on success
 */
export const verifyOtp = async (email, otp) => {
  const response = await apiClient.post('/api/auth/verify-otp', { email, otp });
  return response.data;
};


/**
 * Register a new user
 */
export const registerUser = async (userData) => {
  const response = await apiClient.post('/api/auth/register', userData);
  return response.data;
};

/**
 * Log in with username/email and password
 */
export const loginUser = async (credentials) => {
  const response = await apiClient.post('/api/auth/login', credentials);
  return response.data;
};

/**
 * Fetch current authenticated user profile
 */
export const getCurrentUser = async () => {
  const response = await apiClient.get('/api/auth/me');
  return response.data;
};

/**
 * Log out user
 */
export const logoutUser = async () => {
  try {
    await apiClient.post('/api/auth/logout');
  } catch (error) {
    // Ignore server error on logout
  } finally {
    clearStoredAuth();
  }
};

/** Local CPU inference can exceed the default 10s client timeout. */
const AI_CHAT_TIMEOUT_MS = 180000;
const GRAMMAR_TIMEOUT_MS = 30000;

/**
 * Send a career-related prompt to the FastAPI AI chat endpoint (one-shot, no history).
 * JWT is attached by the shared request interceptor when present.
 */
export const chatWithAI = async (prompt, think = false) => {
  const response = await apiClient.post(
    '/api/ai/chat',
    { prompt, think },
    { timeout: AI_CHAT_TIMEOUT_MS }
  );
  return response.data;
};

export const getConversations = async () => {
  const response = await apiClient.get('/api/ai/conversations');
  return response.data;
};

export const getConversation = async (conversationId) => {
  const response = await apiClient.get(`/api/ai/conversations/${conversationId}`);
  return response.data;
};

/**
 * Create a conversation on the first user message and return the assistant reply.
 */
export const createConversation = async (content) => {
  const response = await apiClient.post(
    '/api/ai/conversations',
    { content },
    { timeout: AI_CHAT_TIMEOUT_MS }
  );
  return response.data;
};

export const sendConversationMessage = async (conversationId, content) => {
  const response = await apiClient.post(
    `/api/ai/conversations/${conversationId}/messages`,
    { content },
    { timeout: AI_CHAT_TIMEOUT_MS }
  );
  return response.data;
};

export const retryConversationMessage = async (conversationId) => {
  const response = await apiClient.post(
    `/api/ai/conversations/${conversationId}/retry`,
    {},
    { timeout: AI_CHAT_TIMEOUT_MS }
  );
  return response.data;
};

export const deleteConversation = async (conversationId) => {
  await apiClient.delete(`/api/ai/conversations/${conversationId}`);
};

export const checkGrammar = async (text) => {
  const response = await apiClient.post(
    '/api/ai/grammar-check',
    { text },
    { timeout: GRAMMAR_TIMEOUT_MS }
  );
  return response.data;
};

export default apiClient;
