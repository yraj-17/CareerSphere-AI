const TOKEN_KEY = 'careersphere_auth_token';
const USER_KEY = 'careersphere_user';

export const getStoredToken = () => {
  if (typeof window === 'undefined') return null;
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch (error) {
    console.error('Error accessing token from storage:', error);
    return null;
  }
};

export const setStoredToken = (token) => {
  if (typeof window === 'undefined') return;
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch (error) {
    console.error('Error saving token to storage:', error);
  }
};

export const getStoredUser = () => {
  if (typeof window === 'undefined') return null;
  try {
    const userStr = localStorage.getItem(USER_KEY);
    return userStr ? JSON.parse(userStr) : null;
  } catch (error) {
    console.error('Error accessing user from storage:', error);
    return null;
  }
};

export const setStoredUser = (user) => {
  if (typeof window === 'undefined') return;
  try {
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(USER_KEY);
    }
  } catch (error) {
    console.error('Error saving user to storage:', error);
  }
};

export const clearStoredAuth = () => {
  if (typeof window === 'undefined') return;
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch (error) {
    console.error('Error clearing auth storage:', error);
  }
};
