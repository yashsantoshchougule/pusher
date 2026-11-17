# Implementation Plan: Frontend 5-Color Design System & Token Integration

This plan formalizes the exact 5-color palette provided in the brand visual specification across Pusher's web dashboard, landing pages, interactive telemetry charts, and UI components.

---

## 1. Color Palette Tokens & Exact Hex Values

Extracted directly from the official palette specification:

| Token Name | Hex Code | RGB | Semantic Role & UI Application |
| :--- | :--- | :--- | :--- |
| **Crisp White** | `#FFFFFF` | `rgb(255, 255, 255)` | Primary headings (`h1`, `h2`), high-contrast body text, metric counters, active primary button text. |
| **Dark Charcoal** | `#242424` | `rgb(36, 36, 36)` | Bento card backgrounds, secondary containers, video player frames, elevated toolbars. |
| **Slate Blue-Gray** | `#5C7C89` | `rgb(92, 124, 137)` | Subtitles, muted labels, container borders (`border-[#5C7C89]/40`), chart gridlines, disabled states. |
| **Ocean / Deep Teal** | `#1F4959` | `rgb(31, 73, 89)` | Primary Action buttons (CTA), active navigation pills, live chart strokes/fills, glowing indicators. |
| **Deep Midnight** | `#011425` | `rgb(1, 20, 37)` | Deep canvas background, terminal/telemetry console backgrounds, recessed input tracks. |

---

## 2. Component Design Token Mappings

### A. Navigation & Top App Bar
* **Background**: `#011425` with 90% opacity (`backdrop-blur-md`).
* **Border**: `#5C7C89` with 30% opacity (`border-[#5C7C89]/30`).
* **Logo Badge**: `#1F4959` with crisp white text (`#FFFFFF`) and `#5C7C89` subtle border.
* **Navigation Links**: Default `#5C7C89`, hover transition to `#FFFFFF`.

### B. Hero & Starter Page Bento Cards
* **Main Canvas**: `#011425`.
* **Elevated Cards**: `#242424` with 2px borders in `#5C7C89`/60.
* **Primary Buttons**: `#1F4959` background with `#FFFFFF` text and hover brightness transition.
* **Secondary Buttons**: `#242424` background with `#5C7C89` border and `#FFFFFF` text.

### C. Live Telemetry & Speed Dashboard (Live Charts)
* **Chart Background Canvas**: `#242424`.
* **Telemetry Graph Axis & Ticks**: `#5C7C89`.
* **Requests Per Second (RPS) Line**: `#1F4959` stroke with translucent gradient fill (`#1F4959` to `#011425`).
* **Latency Percentile Lines**:
  * `p50`: `#5C7C89`
  * `p90`: `#1F4959`
  * `p99`: High-contrast highlight `#FFFFFF` (or critical warning accent for 5xx).

### D. Verification Wizard & Pusher Guard Download Modal
* **Modal Overlay**: `#011425` with 85% opacity.
* **Modal Dialog Box**: `#242424` with `#5C7C89` border.
* **Code Preview Blocks**: `#011425` recessed box with `#5C7C89` syntax accenting and `#FFFFFF` token strings.
* **Download Button**: `#1F4959` CTA.

---

## 3. Tailwind CSS & Design Token Implementation

To ensure all developers and UI components share the exact same names without hardcoding raw hex strings, define the theme extensions:

```javascript
// frontend/tailwind.config.js
module.exports = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        pusher: {
          canvas: '#011425',      // Deep Midnight Canvas
          surface: '#242424',     // Dark Charcoal Cards
          slate: '#5C7C89',       // Slate Blue-Gray Borders & Secondary Text
          teal: '#1F4959',        // Ocean / Deep Teal Accent & Primary CTA
          white: '#FFFFFF',       // Crisp White Primary Text
        }
      }
    }
  },
  plugins: []
};
```

---

## 4. Verification & Consistency

1. **`StarterPage.jsx`**: Validated that all 5 tokens are integrated into the existing starter page component.
2. **`architecture_and_standards.md`**: Update Section 3 with the official 5-color design system specification.
3. **Index Update**: Register this plan in `supporting files/plans/README.md`.
