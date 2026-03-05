'use client';

/**
 * SECURITY WARNING: Mock Authentication Hook
 *
 * This is a DEVELOPMENT-ONLY mock authentication implementation.
 *
 * KNOWN SECURITY ISSUES (DO NOT USE IN PRODUCTION):
 *
 * 1. XSS VULNERABILITY: Session data is stored in localStorage which is
 *    accessible to any JavaScript running on the page. If an XSS attack
 *    occurs, attackers can steal user sessions.
 *
 * 2. NO SERVER-SIDE VALIDATION: There is no backend authentication.
 *    Any client can impersonate any user by modifying localStorage.
 *
 * 3. NO CSRF PROTECTION: Cross-site request forgery is not prevented.
 *
 * PRODUCTION REQUIREMENTS:
 * - Implement proper JWT authentication with httpOnly cookies
 * - Add server-side session validation
 * - Use secure, httpOnly, sameSite cookies for token storage
 * - Implement CSRF tokens for state-changing requests
 * - Add rate limiting and brute force protection
 *
 * See: https://owasp.org/www-community/attacks/xss/
 */

import { useEffect, useState, useCallback } from 'react';

export interface User {
  id: string;
  email: string;
}

const MOCK_SESSION_KEY = 'mock_session_user';
const ACCESS_TOKEN_KEY = 'access_token';

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // SECURITY: localStorage is vulnerable to XSS - use httpOnly cookies in production
    const storedUser = localStorage.getItem(MOCK_SESSION_KEY);
    if (storedUser) {
      try {
        setUser(JSON.parse(storedUser));
      } catch (e) {
        console.error('Failed to parse session', e);
        localStorage.removeItem(MOCK_SESSION_KEY);
      }
    }
    setLoading(false);
  }, []);

  const signIn = useCallback(async (email: string, accessToken?: string) => {
    setLoading(true);
    // SECURITY: In production, this should call a secure backend endpoint
    // that returns an httpOnly cookie, not store credentials in localStorage
    await new Promise(resolve => setTimeout(resolve, 500));

    const mockUser: User = {
      id: 'mock-user-id-' + Math.random().toString(36).substring(7),
      email,
    };

    // SECURITY WARNING: localStorage is accessible to XSS attacks
    localStorage.setItem(MOCK_SESSION_KEY, JSON.stringify(mockUser));
    if (accessToken) {
      localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    }
    setUser(mockUser);
    setLoading(false);
  }, []);

  const signOut = useCallback(async () => {
    setLoading(true);
    // SECURITY: In production, this should invalidate the session server-side
    await new Promise(resolve => setTimeout(resolve, 300));

    localStorage.removeItem(MOCK_SESSION_KEY);
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    setUser(null);
    setLoading(false);
  }, []);

  return {
    user,
    loading,
    isAuthenticated: !!user,
    signIn,
    signOut,
  };
}
