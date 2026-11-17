# Dashboard Sage, Olive & Cream Palette Migration Plan

## 🎯 Goal
Migrate `frontend/src/pages/DashboardPage.jsx` from the dark navy/slate theme (`#011425`, `#16222A`, `#1F4959`) to the unified **Earthy Sage, Olive, and Cream** design system matching `LoginPage.jsx` and user-uploaded reference `media_1794899003927_f39c17d3.jpg`.

---

## 🎨 Token Architecture & Luminance Mapping

| Layer / Element | New Hex Token | Role / Aesthetics |
| :--- | :--- | :--- |
| **Canvas Viewport** | `#EBEBD8` | Full-height page background (Warm Cream) |
| **Sidebar Navigation** | `#9BA685` | Left sidebar container (Soft Sage Green) with `#455230`/20 border |
| **Cards & Panels** | `#9BA685` | 4 KPI cards, Quick Traffic Launcher, pusher_guard.py card, Recent Runs container |
| **Inner Controls / Insets** | `#F7F6E4` / `#EBEBD8` | Dropdown, table rows, domain cards, slider tracks, inactive mode cards |
| **Focal CTAs & Active Pills** | `#455230` / `#4B5437` | `+ New Load Test`, `Start Controlled Test`, active navigation item, active traffic mode |
| **Primary Typography** | `#374220` | Headings, KPI values, labels, and table typography |
| **Inverted Typography** | `#EBEBD8` / `#EFFADA` | Text on active buttons, active tabs, and badges |
| **Borders & Dividers** | `#637545`/25 | Subtle borders ensuring clear definition |

---

## 📋 Implementation Checklist

- [ ] **1. Left Sidebar Navigation**: Styled with `#9BA685` background, `#455230` active items, and `#EBEBD8` guardrails widget.
- [ ] **2. Top Header Bar**: Mission Control title in `#374220`, `#EBEBD8` engine status pill, and `#455230` primary button.
- [ ] **3. 4 KPI Summary Cards**: Styled with `#9BA685` surfaces, `#263016` metric values, and `#EBEBD8` badges.
- [ ] **4. Interactive Quick Traffic Launcher & pusher_guard.py**: Styled with `#9BA685` card, `#455230` selected mode, and `#EBEBD8` input controls.
- [ ] **5. Recent Load Test Runs Table**: Styled with `#9BA685` container, `#374220` data rows, and high-contrast status pills.
- [ ] **6. Verification**: Production build, unit tests, and live browser verification.
