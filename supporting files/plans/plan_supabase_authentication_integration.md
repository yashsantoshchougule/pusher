# Plan: Supabase Authentication Integration

> **Target:** Wire Supabase authentication into the Pusher frontend and backend while maintaining strict security separation between client-safe keys and backend secret keys.

---

## 1. Security Architecture & Key Separation

| Scope | Allowed Environment Variables | Usage | Exposed to Browser? |
| :--- | :--- | :--- | :--- |
| **Frontend (Vite / React)** | `VITE_SUPABASE_URL`<br>`VITE_SUPABASE_ANON_KEY` | Initializing `@supabase/supabase-js`, handling user sign-in/up & OAuth redirects. | **Yes** (Client-safe public anon token) |
| **Backend (FastAPI / Server)** | `SUPABASE_URL`<br>`SUPABASE_SECRET_KEY`<br>`SUPABASE_JWKS_URL` | Validating user JWT tokens on protected test endpoints, managing database policies. | **NO** (Strictly server-side; excluded from frontend bundles) |

---

## 2. Integration Components

### Component A: Supabase Client Library
- Install `@supabase/supabase-js` in `frontend/`.
- Create `frontend/src/lib/supabaseClient.js`:
  ```javascript
  import { createClient } from '@supabase/supabase-js';

  const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
  const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

  export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
    auth: {
      autoRefreshToken: true,
      persistSession: true,
      detectSessionInUrl: true,
    },
  });
  ```

### Component B: Authentication Methods in `LoginPage.jsx` & `AuthFormPanel.jsx`
1. **Sign Up (`isSignUp === true`)**:
   - Call `supabase.auth.signUp({ email, password, options: { data: { first_name, last_name } } })`.
   - Display success notification: "Confirmation email sent" or "Account created".
2. **Log In (`isSignUp === false`)**:
   - Call `supabase.auth.signInWithPassword({ email, password })`.
   - On success: updates global auth state and redirects to website/dashboard console.
   - On error: displays crisp error message in the army-olive toast banner.
3. **OAuth SSO (Google, Apple, GitHub)**:
   - Call `supabase.auth.signInWithOAuth({ provider: 'google' | 'apple' | 'github' })`.

### Component C: Global Session Management (`App.jsx`)
- Check current user via `supabase.auth.getSession()` on load.
- Listen for live auth events (`SIGNED_IN`, `SIGNED_OUT`, `TOKEN_REFRESHED`) via `supabase.auth.onAuthStateChange()`.
- Display active user profile in the navigation header when logged in.

---

## 3. Implementation Steps
- [ ] **Step 1:** Install `@supabase/supabase-js` in `frontend/`.
- [ ] **Step 2:** Create `frontend/src/lib/supabaseClient.js`.
- [ ] **Step 3:** Wire `signUp`, `signInWithPassword`, and `signInWithOAuth` into `AuthFormPanel.jsx` and `LoginPage.jsx`.
- [ ] **Step 4:** Add session state listener to `App.jsx`.
- [ ] **Step 5:** Run Vite build verification (`npm run build`) and test connection.
