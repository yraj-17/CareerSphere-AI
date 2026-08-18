'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  loginUser,
  registerUser,
  getCurrentUser,
  logoutUser,
  extractErrorMessage,
} from '@/services/api';
import {
  getStoredToken,
  setStoredToken,
  getStoredUser,
  setStoredUser,
  clearStoredAuth,
} from '@/lib/auth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  // Initialize and verify authentication state on client mount
  const checkAuth = useCallback(async () => {
    const savedToken = getStoredToken();
    const savedUser = getStoredUser();

    if (!savedToken) {
      setUser(null);
      setToken(null);
      setIsLoading(false);
      return;
    }

    setToken(savedToken);
    if (savedUser) {
      setUser(savedUser);
    }

    try {
      // Validate token with backend
      const userData = await getCurrentUser();
      setUser(userData);
      setStoredUser(userData);
    } catch (error) {
      console.warn('Session verification failed, clearing auth state:', error);
      clearStoredAuth();
      setUser(null);
      setToken(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  /**
   * Log in user with identifier and password
   */
  const login = async (identifier, password) => {
    try {
      const response = await loginUser({ identifier, password });
      const { access_token, user: userData } = response;

      setStoredToken(access_token);
      setStoredUser(userData);
      setToken(access_token);
      setUser(userData);

      return { success: true, user: userData };
    } catch (error) {
      const errorMsg = extractErrorMessage(error);
      return { success: false, error: errorMsg };
    }
  };

  /**
   * Register a new user
   */
  const signup = async (userData) => {
    try {
      const newUser = await registerUser(userData);
      return { success: true, user: newUser };
    } catch (error) {
      const errorMsg = extractErrorMessage(error);
      return { success: false, error: errorMsg };
    }
  };

  /**
   * Log out user
   */
  const logout = async () => {
    try {
      await logoutUser();
    } finally {
      clearStoredAuth();
      setUser(null);
      setToken(null);
      router.push('/login');
    }
  };

  const value = {
    user,
    token,
    isAuthenticated: !!user && !!token,
    isLoading,
    login,
    signup,
    logout,
    checkAuth,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
