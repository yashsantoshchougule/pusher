# Implementation Plan: Pixel-Accurate Pusher Starter Page Implementation & Visual Loop

## 1. Overview & Goal
The objective is to implement the exact visual and structural design of the **Pusher Starter Page** in `frontend/src/pages/StarterPage.jsx`, wire it as the root (`/`) component in `frontend/src/App.jsx`, and conduct a visual verification loop via the browser subagent to match the reference mockup (`media_1794810385841_efd7d983.jpg`).

---

## 2. Key Architecture & Visual Elements

### A. Full-Screen Diagonal Silk Waves
- **Base Canvas**: `#011425`
- **Diagonal Silk Ribbons**: A smooth SVG / CSS layer featuring sweeping curved luminous ribbons running diagonally across the viewport from top-right down toward the left and bottom-right, styled with `#1F4959` (25% opacity) and `#5C7C89` (15% opacity), layered with Gaussian blur (`blur-3xl`) to create the soft, ethereal silk effect shown in the reference image.

### B. Fixed/Sticky Top Navbar (`h-16`)
- **Left**: Rounded square icon (`bg-[#1F4959] border border-[#5C7C89]/60`) with bold white `P`, brand text `PUSHER` in high-contrast bold white, and `#242424` badge `v1.0` with a subtle `#5C7C89` border.
- **Center**: 4 nav links (`Features`, `Live Demo`, `Safety Guardrails`, `WAF Guide`) in `#5C7C89` (`hover:text-white transition-colors`).
- **Right**: `Log in` text link + solid light-slate rounded-full pill button `Sign up` (`bg-[#C5D8E0] text-[#011425] font-semibold px-4 py-1.5`).

### C. Centered Hero Section
- **Top Pill Badge**: `⚡ Developer-First Load Testing • 250 MB RAM Engine` inside `bg-[#112230]/90 border border-[#5C7C89]/40 rounded-full px-4 py-1.5 text-xs text-white`.
- **Two-Tone Headline**:
  - Line 1 in crisp white (`#FFFFFF`): `Developer-first load testing`
  - Line 2 in muted slate blue-gray (`#5C7C89`): `for power users`
- **Subtitle**: In `#8CA3B0` with `max-w-2xl mx-auto text-sm md:text-base`.
- **Dual Rounded-Full CTA Buttons**:
  - Left: `Start Load Testing →` (`bg-gradient-to-b from-[#3B6478] to-[#1F4959] border border-[#5C7C89] text-white rounded-full px-6 py-2.5 text-sm font-semibold shadow-lg`)
  - Right: `Login / Sign Up` (`bg-[#0B1822]/90 border border-[#5C7C89]/60 text-white rounded-full px-6 py-2.5 text-sm font-semibold`)
- **Trust Bar**: 6-item horizontal row (`100% Free | Open Source | No Credit Card | 99.9% Uptime | Instant Reports | Enterprise Ready`) with Lucide icons in `#5C7C89` and divider bars.

### D. Glassmorphic Browser Window Mockup (`max-w-5xl mx-auto`)
- **Outer Shell**: `bg-[#16222A]/90 border border-[#5C7C89]/50 rounded-2xl p-4 shadow-2xl backdrop-blur-xl`.
- **Top Window Bar**:
  - Mac window controls: Red (`#FF5F56`), Yellow (`#FFBD2E`), Green (`#27C93F`).
  - URL Pill: `bg-[#0D161C] border border-[#5C7C89]/30 rounded-lg px-3.5 py-1.5` with lock icon + `https://pusher.local/report`.
  - Right buttons: `View Demo →` (`bg-[#1F4959] text-white`) and `▶ Auto Loop` (`bg-[#0D161C] border border-[#5C7C89]/40 text-[#5C7C89]`).
- **Row 1 — 3 Metric Cards (`grid grid-cols-1 md:grid-cols-3 gap-4 mt-4`)**:
  - **Card 1 (`Max Safe Capacity`)**: Shield icon + label, `420 VUs` in bold white, `↑ 12% 100% Confidence`, and right-side SVG multi-peak area wave sparkline (`#5C7C89` stroke, `#1F4959` area gradient).
  - **Card 2 (`Real-time Credit`)**: TrendingUp icon + label, `+250%` in bold white, `Run: #543 (420) • Run: #544 (420)`, and right-side SVG ascending wave sparkline.
  - **Card 3 (`Truncated Error Log`)**: Terminal `>_` icon + label, dark monospace inset box (`bg-[#1E2226] rounded-lg px-3 py-2 font-mono text-xs text-white`) reading `512-byte cap: 0 total exceptions`, and bottom link `View full log →`.
- **Row 2 — Full-Width Advisor Banner**:
  - Outlined warm yellow lightbulb, `Plain-English Advisor Recommendations:`, full advisor diagnosis text, and `Read More →` rounded button.

---

## 3. Execution Plan

1. **Create `frontend/src/pages/StarterPage.jsx`**:
   Write the complete, non-truncated, pixel-accurate implementation with all styles, Tailwind classes, SVG definitions, and Lucide icons.
2. **Update `frontend/src/App.jsx`**:
   Wire `frontend/src/pages/StarterPage.jsx` as the root component.
3. **Verify Build**:
   Execute `npm run build` in `frontend` to guarantee 0 syntax or JSX compile errors.
4. **Visual Verification with Browser Subagent**:
   Start the dev server (`npm run dev`), launch the `browser` subagent to navigate to `http://localhost:5173/`, capture screenshots, and compare them against the target image (`media_1794810385841_efd7d983.jpg`).
5. **Iterate & Refine**:
   Fine-tune any layout details (glow intensity, SVG wave paths, padding, font weights) until exact parity is achieved.
