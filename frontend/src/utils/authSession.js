/**
 * Auth Session Storage & Utilities for PUSHER Platform
 * Manages localStorage session persistence for pusher_auth_session:
 * {
 *   access_token: string,
 *   user: {
 *     user_id: string,
 *     email: string,
 *     full_name: string
 *   }
 * }
 */

export const AUTH_SESSION_KEY = 'pusher_auth_session';

export function getAuthSession() {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(AUTH_SESSION_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (err) {
    console.error('Failed to parse auth session from localStorage:', err);
    return null;
  }
}

export function setAuthSession(session) {
  if (typeof window === 'undefined') return;
  if (!session) {
    localStorage.removeItem(AUTH_SESSION_KEY);
  } else {
    localStorage.setItem(AUTH_SESSION_KEY, JSON.stringify(session));
  }
}

export function clearAuthSession() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(AUTH_SESSION_KEY);
}

export function isAuthenticated() {
  const session = getAuthSession();
  return Boolean(session && (session.access_token || session.user?.user_id || session.user?.email));
}
