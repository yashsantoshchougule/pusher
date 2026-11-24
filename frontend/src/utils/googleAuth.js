/**
 * Google Identity Services (GIS) & OAuth Client Utility
 * Integrates Google OAuth 2.0 with Client ID:
 * 999210457582-han5qlmibone69dtrdpq587krna09g9e.apps.googleusercontent.com
 */

export const GOOGLE_CLIENT_ID =
  import.meta.env.VITE_GOOGLE_CLIENT_ID ||
  '999210457582-han5qlmibone69dtrdpq587krna09g9e.apps.googleusercontent.com';

/**
 * Safely decodes a JWT payload (such as Google GIS ID Token Credential)
 */
export function parseJwt(token) {
  if (!token || typeof token !== 'string') return null;
  try {
    const parts = token.split('.');
    if (parts.length < 2) return null;
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (err) {
    console.warn('Failed to parse JWT:', err);
    return null;
  }
}

/**
 * Initiates Google OAuth Sign-In
 * Supports both Google GIS ID Token & OAuth 2.0 Access Token flows
 */
export function initiateGoogleSignIn({ onSuccess, onError, onPrompt }) {
  if (typeof window === 'undefined') return;

  const clientId = GOOGLE_CLIENT_ID;

  // Check if Google Identity Services script is loaded
  if (!window.google || !window.google.accounts) {
    if (onError) {
      onError({
        code: 'SDK_NOT_LOADED',
        message: 'Google Sign-In SDK is loading or blocked by browser extensions.',
      });
    }
    return;
  }

  try {
    // 1. Initialize Google Credential One Tap / ID Token listener
    window.google.accounts.id.initialize({
      client_id: clientId,
      auto_select: false,
      callback: (response) => {
        if (response && response.credential) {
          const profile = parseJwt(response.credential);
          if (profile && onSuccess) {
            onSuccess({
              provider: 'google',
              id: profile.sub,
              email: profile.email,
              fullName: profile.name || [profile.given_name, profile.family_name].filter(Boolean).join(' '),
              avatarUrl: profile.picture || '',
              token: response.credential,
              type: 'id_token',
            });
          }
        }
      },
    });

    // 2. Try standard OAuth 2.0 popup via initTokenClient
    if (window.google.accounts.oauth2) {
      const tokenClient = window.google.accounts.oauth2.initTokenClient({
        client_id: clientId,
        scope: 'openid email profile',
        callback: async (tokenResponse) => {
          if (tokenResponse.error) {
            if (onError) onError(tokenResponse);
            return;
          }

          if (tokenResponse.access_token) {
            try {
              const res = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
                headers: { Authorization: `Bearer ${tokenResponse.access_token}` },
              });
              if (res.ok) {
                const userinfo = await res.json();
                if (onSuccess) {
                  onSuccess({
                    provider: 'google',
                    id: userinfo.sub,
                    email: userinfo.email,
                    fullName: userinfo.name || `${userinfo.given_name || ''} ${userinfo.family_name || ''}`.trim(),
                    avatarUrl: userinfo.picture || '',
                    token: tokenResponse.access_token,
                    type: 'access_token',
                  });
                }
                return;
              }
            } catch (fetchErr) {
              console.warn('Failed fetching Google userinfo:', fetchErr);
            }

            // Fallback if userinfo fetch fails
            if (onSuccess) {
              onSuccess({
                provider: 'google',
                id: 'google_' + Date.now(),
                email: 'operator@gmail.com',
                fullName: 'Google Operator',
                avatarUrl: '',
                token: tokenResponse.access_token,
                type: 'access_token',
              });
            }
          }
        },
        error_callback: (error) => {
          if (onError) onError(error);
        },
      });

      tokenClient.requestAccessToken({ prompt: 'select_account' });
      return;
    }

    // Fallback: prompt One Tap / account chooser
    window.google.accounts.id.prompt((notification) => {
      if (onPrompt) onPrompt(notification);
      if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
        if (onError) {
          onError({
            code: 'PROMPT_SUPPRESSED',
            reason: notification.getNotDisplayedReason?.() || 'Suppressed',
          });
        }
      }
    });
  } catch (err) {
    if (onError) onError(err);
  }
}
