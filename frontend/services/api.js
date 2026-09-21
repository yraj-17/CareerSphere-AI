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
const AI_CHAT_TIMEOUT_MS = 240000;
/**
 * Career Matching may involve Qwen explanation generation which can be slow.
 * Allow generous overhead beyond the backend Qwen timeout.
 */
const CAREER_MATCHING_TIMEOUT_MS = 480000;
const AI_PROFILE_OPTIMIZATION_TIMEOUT_MS = 240000;
const GRAMMAR_TIMEOUT_MS = 30000;
/** Skill gap AI (Qwen) backend timeout is 360s; allow extra HTTP overhead. */
const AI_SKILL_ANALYSIS_TIMEOUT_MS = 420000;


/**
 * Send a career-related prompt to the FastAPI AI chat endpoint (one-shot, no history).
 * JWT is attached by the shared request interceptor when present.
 */
export const chatWithAI = async (prompt, think = false, useProfile = false) => {
  const response = await apiClient.post(
    '/api/ai/chat',
    { prompt, think, use_profile: useProfile },
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
export const createConversation = async (content, useProfile = false) => {
  const response = await apiClient.post(
    '/api/ai/conversations',
    { content, use_profile: useProfile },
    { timeout: AI_CHAT_TIMEOUT_MS }
  );
  return response.data;
};

export const sendConversationMessage = async (conversationId, content, useProfile = false) => {
  const response = await apiClient.post(
    `/api/ai/conversations/${conversationId}/messages`,
    { content, use_profile: useProfile },
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

export const optimizeMyProfile = async () => {
  const response = await apiClient.post(
    '/api/ai/profile/optimize',
    {},
    { timeout: AI_PROFILE_OPTIMIZATION_TIMEOUT_MS }
  );
  return response.data;
};

export const uploadMedia = async (file, purpose = 'general') => {
  const formData = new FormData();
  formData.append('purpose', purpose);
  formData.append('file', file);
  const response = await apiClient.post('/api/media/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  });
  return response.data;
};

export const getMyProfile = async () => {
  const response = await apiClient.get('/api/profile/me');
  return response.data;
};

export const updateMyProfile = async (payload) => {
  const response = await apiClient.patch('/api/profile/me', payload);
  return response.data;
};

export const addSkill = async (payload) => {
  const response = await apiClient.post('/api/profile/me/skills', payload);
  return response.data;
};

export const deleteSkill = async (skillId) => {
  await apiClient.delete(`/api/profile/me/skills/${skillId}`);
};

export const addEducation = async (payload) => {
  const response = await apiClient.post('/api/profile/me/education', payload);
  return response.data;
};

export const updateEducation = async (id, payload) => {
  const response = await apiClient.put(`/api/profile/me/education/${id}`, payload);
  return response.data;
};

export const deleteEducation = async (id) => {
  await apiClient.delete(`/api/profile/me/education/${id}`);
};

export const addExperience = async (payload) => {
  const response = await apiClient.post('/api/profile/me/experience', payload);
  return response.data;
};

export const updateExperience = async (id, payload) => {
  const response = await apiClient.put(`/api/profile/me/experience/${id}`, payload);
  return response.data;
};

export const deleteExperience = async (id) => {
  await apiClient.delete(`/api/profile/me/experience/${id}`);
};

export const addProject = async (payload) => {
  const response = await apiClient.post('/api/profile/me/projects', payload);
  return response.data;
};

export const updateProject = async (id, payload) => {
  const response = await apiClient.put(`/api/profile/me/projects/${id}`, payload);
  return response.data;
};

export const deleteProject = async (id) => {
  await apiClient.delete(`/api/profile/me/projects/${id}`);
};

export const addCertification = async (payload) => {
  const response = await apiClient.post('/api/profile/me/certifications', payload);
  return response.data;
};

export const updateCertification = async (id, payload) => {
  const response = await apiClient.put(`/api/profile/me/certifications/${id}`, payload);
  return response.data;
};

export const deleteCertification = async (id) => {
  await apiClient.delete(`/api/profile/me/certifications/${id}`);
};

export const updateCareerPreferences = async (payload) => {
  const response = await apiClient.patch('/api/profile/me/preferences', payload);
  return response.data;
};

/**
 * Fetch the authenticated user's skill analysis.
 *
 * When includeAI is true (default), the backend also calls Qwen to produce
 * AI-powered priority gaps, learning order, and roadmap.  This can take up to
 * ~360s on a local Ollama instance, so a longer client timeout is required.
 *
 * The backend derives the user from the JWT — do NOT send user_id or profile data.
 */
export const getSkillAnalysis = async (includeAI = true) => {
  const response = await apiClient.get('/api/skill-analysis/me', {
    params: { include_ai: includeAI },
    timeout: AI_SKILL_ANALYSIS_TIMEOUT_MS,
  });
  return response.data;
};

/**
 * Fetch the authenticated user's personalised career matches.
 *
 * When includeAI is true (default), the backend runs Gemini reranking and
 * Qwen explanation generation — both can be slow.  A generous client timeout
 * is set so the request is not aborted mid-pipeline.
 *
 * The backend derives the current user from the JWT — do NOT send user_id,
 * profile_id, or any profile data from the frontend.
 *
 * @param {boolean} includeAI - Include Gemini reranking and Qwen AI explanations.
 * @returns {Promise<import('./api').CareerMatchingAPIResponse>}
 */
export const getCareerMatching = async (includeAI = true) => {
  const response = await apiClient.get('/api/career-matching/me', {
    params: { include_ai: includeAI },
    timeout: CAREER_MATCHING_TIMEOUT_MS,
  });
  return response.data;
};

export default apiClient;

// ─────────────────────────────────────────────────────────────────────────────
// Networking — Phase 5.3 / 5.4
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Discover other users (people search).
 *
 * @param {{ q?: string, limit?: number, offset?: number }} params
 * @returns {Promise<{ total: number, limit: number, offset: number, users: Array }>}
 */
export const getNetworkingUsers = async ({ q = '', limit = 20, offset = 0 } = {}) => {
  const params = { limit, offset };
  if (q && q.trim()) params.q = q.trim();
  const response = await apiClient.get('/api/networking/users', { params });
  return response.data;
};

/**
 * Check the connection status between the authenticated user and another user.
 *
 * @param {string} userId  — target user's ID
 * @returns {Promise<{ status: string, connection_id?: string, requester_id?: string, receiver_id?: string }>}
 */
export const getNetworkingUserConnection = async (userId) => {
  const response = await apiClient.get(`/api/networking/users/${userId}/connection`);
  return response.data;
};

/**
 * Send a connection request to another user.
 * The authenticated user is automatically the requester (derived from JWT).
 *
 * @param {string} userId  — target user's ID
 * @returns {Promise<{ id: string, requester_id: string, receiver_id: string, status: string }>}
 */
export const sendConnectionRequest = async (userId) => {
  const response = await apiClient.post(`/api/networking/connections/${userId}`);
  return response.data;
};

/**
 * Get the authenticated user's accepted connections.
 *
 * @returns {Promise<Array>}
 */
export const getMyConnections = async () => {
  const response = await apiClient.get('/api/networking/connections');
  return response.data;
};

/**
 * Get incoming pending connection requests for the authenticated user.
 *
 * @returns {Promise<Array>}
 */
export const getIncomingRequests = async () => {
  const response = await apiClient.get('/api/networking/requests/incoming');
  return response.data;
};

/**
 * Get outgoing pending connection requests sent by the authenticated user.
 *
 * @returns {Promise<Array>}
 */
export const getOutgoingRequests = async () => {
  const response = await apiClient.get('/api/networking/requests/outgoing');
  return response.data;
};

/**
 * Accept a pending connection request.
 *
 * @param {string} connectionId
 * @returns {Promise<Object>}
 */
export const acceptConnectionRequest = async (connectionId) => {
  const response = await apiClient.post(`/api/networking/requests/${connectionId}/accept`);
  return response.data;
};

/**
 * Reject a pending connection request.
 *
 * @param {string} connectionId
 * @returns {Promise<Object>}
 */
export const rejectConnectionRequest = async (connectionId) => {
  const response = await apiClient.post(`/api/networking/requests/${connectionId}/reject`);
  return response.data;
};

/**
 * Cancel an outgoing pending connection request.
 *
 * @param {string} connectionId
 * @returns {Promise<Object>}
 */
export const cancelConnectionRequest = async (connectionId) => {
  const response = await apiClient.post(`/api/networking/requests/${connectionId}/cancel`);
  return response.data;
};

/**
 * Remove an accepted connection (either party may call this).
 *
 * @param {string} connectionId
 * @returns {Promise<void>}
 */
export const removeConnection = async (connectionId) => {
  await apiClient.delete(`/api/networking/connections/${connectionId}`);
};

// ─────────────────────────────────────────────────────────────────────────────
// My Network — Phase 5.5 (enriched endpoints with user details)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Get accepted connections enriched with the other user's public profile details.
 * Used by the My Network page to avoid per-user secondary fetches.
 *
 * @returns {Promise<Array<EnrichedConnectionResponse>>}
 */
export const getMyNetworkConnections = async () => {
  const response = await apiClient.get('/api/networking/my-network/connections');
  return response.data;
};

/**
 * Get incoming pending requests enriched with the requester's public profile.
 *
 * @returns {Promise<Array<EnrichedConnectionResponse>>}
 */
export const getMyNetworkIncoming = async () => {
  const response = await apiClient.get('/api/networking/my-network/requests/incoming');
  return response.data;
};

/**
 * Get outgoing pending requests enriched with the receiver's public profile.
 *
 * @returns {Promise<Array<EnrichedConnectionResponse>>}
 */
export const getMyNetworkOutgoing = async () => {
  const response = await apiClient.get('/api/networking/my-network/requests/outgoing');
  return response.data;
};
