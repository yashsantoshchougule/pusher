# Login Card 2.06:1 Aspect Ratio & 70% Proportional Viewport Scaling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the wide `2.0625:1` aspect ratio (`1320px × 640px` base canvas) for the PUSHER login/signup card and enable responsive 70% viewport scaling across PC, laptop, and tablet screens without clipping or overflow.

**Architecture:** Update `LoginPage.jsx` to canonical dimensions of `1320px × 640px` with 50/50 columns (`660px` left photo with `p-4 rounded-2xl`, `660px` right form). Update `AuthFormPanel.jsx` with `px-14 py-8`, `h-11` (44px) inputs, and vertically balanced spacing. Replace `computeScale` with viewport width/height fill formula (`0.70` on desktop/laptop, `0.88` on tablet).

**Tech Stack:** React 18, Vite, Tailwind CSS, Playwright (Chromium headless)

## Global Constraints
- Canonical card dimensions: `1320px × 640px` (`2.0625 : 1` ratio)
- Permanent 50/50 split (`grid-template-columns: 1fr 1fr`), columns `660px` each
- Left photo: `p-4`, `rounded-2xl overflow-hidden`, `w-full h-full object-cover`
- Right form: `px-14 py-8 flex flex-col justify-center`, `h-11` (44px) input fields
- Dynamic scale: `Math.min((vw * widthFill) / CARD_W, (vh * heightFill) / CARD_H)` with `widthFill = vw < 1024 ? 0.88 : 0.70; heightFill = 0.76;`
- Zero automatic `git commit` or `git push`

---

### Task 1: Update `AuthFormPanel.jsx` Layout & Input Dimensions
**Files:**
- Modify: `frontend/src/components/auth/AuthFormPanel.jsx`

- [ ] **Step 1: Set outer container padding to `px-14 py-8`**
- [ ] **Step 2: Upgrade input field heights to `h-11` (`44px`) with `rounded-xl px-4`**
- [ ] **Step 3: Update CTA and Social buttons to comfortable heights (`h-11` / `py-2.5`)**
- [ ] **Step 4: Verify spacing between sections in both Sign Up and Log In modes**

---

### Task 2: Update `LoginPage.jsx` Card Dimensions & Viewport Scaling
**Files:**
- Modify: `frontend/src/pages/LoginPage.jsx`

- [ ] **Step 1: Update `CARD_W = 1320`, `CARD_H = 640`**
- [ ] **Step 2: Update `computeScale` to use `vw * widthFill` / `vh * heightFill`**
- [ ] **Step 3: Update container styles (`width: 1320px`, `height: 640px`, `borderRadius: 24px`, columns `660px`)**
- [ ] **Step 4: Update left column padding to `p-4` with `rounded-2xl`**

---

### Task 3: Comprehensive Playwright Multi-Viewport Verification
**Files:**
- Create: `scratch/verify_scale_206.py`

- [ ] **Step 1: Test Desktop PC (`1920 × 1080`): verify rendered width is ~1344px (70% fill), height ~651.6px, aspect ratio 2.0625**
- [ ] **Step 2: Test Laptop (`1366 × 768`): verify rendered width is ~956.2px (70% fill), height ~463.6px, aspect ratio 2.0625**
- [ ] **Step 3: Test Landscape Tablet (`1024 × 768`): verify rendered dimensions and aspect ratio 2.0625**
- [ ] **Step 4: Test Portrait Tablet (`768 × 1024`): verify 88% fill without horizontal cutoff or vertical stacking**
- [ ] **Step 5: Verify tab toggle (Log In vs Sign Up) in all viewports with zero overflow**
- [ ] **Step 6: Capture screenshot evidence for each viewport and mode**
- [ ] **Step 7: Run backend pytest and frontend build**
