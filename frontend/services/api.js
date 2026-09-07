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
    if (error.code === 'ECONNABORTED' || error.message?.includes('Network Error')) {
      return 'Unable to connect to the server. Please try again later.';
    }
    return error.message || 'Unable to connect to the server. Please try again later.';
  }

  const data = error.response.data;
  if (!data) return 'An unexpected error occurred. Please try again.';

  if (typeof data.detail === 'string') {
    return data.detail;
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

export default apiClient;
