# Left Panel Clarity, Brightness & Full-Bleed Sizing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix image clarity, brightness, contrast, and edge-to-edge full-bleed sizing inside the left visual panel of `LoginPage.jsx` without altering any part of the right-side form, inputs, buttons, colors, or page layout.

**Architecture & Key Deliverables:**
1. **Remove Black Sidebars / Full-Bleed Edge-to-Edge:**
   - Left image container has `relative overflow-hidden rounded-2xl` with zero inner padding around the `<img>`.
   - Use an `<img>` tag with `absolute inset-0 w-full h-full object-cover object-center` so the image fills 100% of the box with zero black letterboxing or pillarboxing.
2. **Remove Muddy Full-Panel Dark Scrim:**
   - Remove the heavy full-screen dark scrim (`bg-[#011425]/60 bg-gradient-to-t from-[#011425]/90 via-[#011425]/30 to-transparent`).
   - Replace with a light bottom-only vignette: `absolute inset-x-0 bottom-0 h-1/4 bg-gradient-to-t from-black/35 to-transparent pointer-events-none`.
   - The upper 75% of the sky, mist, and hills remains 100% clear, bright, and unobstructed.
3. **Boost Visual Sharpness & Contrast:**
   - Add optical enhancement filters: `brightness-[1.06] contrast-[1.08] saturate-[1.12] select-none transition-all duration-500`.
   - Add hardware acceleration and anti-blur styles: `style={{ imageRendering: 'auto', WebkitBackfaceVisibility: 'hidden', transform: 'translateZ(0)' }}`.
4. **Zero Right-Side Modifications:**
   - Strictly guard `AuthFormPanel.jsx`, the right column, colors, inputs, segmented controls, and container geometry.

---

## Global Constraints

- **Right-Side Invariance:** Zero changes to `AuthFormPanel.jsx`, the right form panel, colors, borders, or page layout.
- **Resource Constraints:** Keep engine memory strictly under 250 MB RAM using 4 KB chunk discards.
- **Git Safety Rule:** AI assistant is strictly prohibited from executing `git commit`, `git merge`, `git rebase`, or `git push`.

---

## Proposed Changes

### Component: `LoginPage.jsx` Left Panel
#### [MODIFY] `frontend/src/pages/LoginPage.jsx`
- Replace the left image container with:
```jsx
{/* Left Column: 10px Margin Inset Around Dynamic Background Image */}
<div className="lg:col-span-6 order-1 lg:order-1 p-[10px] flex flex-col justify-center">
  <div className="relative w-full h-full min-h-[460px] lg:min-h-[770px] overflow-hidden rounded-2xl">
    <img
      src={currentFrameData.src}
      alt={currentFrameData.phase}
      className="absolute inset-0 w-full h-full object-cover object-center brightness-[1.06] contrast-[1.08] saturate-[1.12] select-none transition-all duration-500"
      style={{
        imageRendering: 'auto',
        WebkitBackfaceVisibility: 'hidden',
        transform: 'translateZ(0)',
      }}
    />
    {/* Subtle bottom-only vignette (bottom 25%) preserving 75% clear sky and landscape */}
    <div className="absolute inset-x-0 bottom-0 h-1/4 bg-gradient-to-t from-black/35 to-transparent pointer-events-none" />
    <AuthVisualPanel />
  </div>
</div>
```

---

## Task Structure

### Task 1: Update `LoginPage.jsx`
- [x] Replace the CSS background container and full-panel dark scrim with the dedicated `<img>` tag and bottom 25% vignette.
- [x] Verify right-side form and overall layout are 100% untouched.

### Task 2: Build Verification
- [x] Run `cd frontend; npm run build` and ensure exit code 0.
- [x] Update `walkthrough.md`.
