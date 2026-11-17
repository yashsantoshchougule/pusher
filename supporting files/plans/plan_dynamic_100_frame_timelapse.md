# Dynamic 100-Frame Real-Time Clock Timelapse Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update ONLY the left visual panel in `src/pages/LoginPage.jsx` to dynamically display the exact background image from the 100-frame sequence (`ezgif-frame-001.jpg` through `ezgif-frame-100.jpg`) based on the user's real-time local clock (`new Date()`). The right-side login/signup form and page layout remain completely untouched.

**Architecture:**
1. **Asset Staging:** Copy all 100 images from `frontend/public/timelapse/timelapse/` into `frontend/public/frames/` so Vite serves them at `/frames/ezgif-frame-001.jpg` through `/frames/ezgif-frame-100.jpg`.
2. **Clock-to-Frame Engine:** Embed `getTimeBasedFrameData(date = new Date())` in `LoginPage.jsx` with the exact 4-phase mapping:
   - Morning (`05:00`–`11:59`, 420 mins): Frames `1`–`25`
   - Afternoon (`12:00`–`16:59`, 300 mins): Frames `26`–`48`
   - Evening (`17:00`–`19:59`, 180 mins): Frames `49`–`76`
   - Night (`20:00`–`04:59`, 540 mins, wrapping midnight): Frames `77`–`100`
3. **Reactive State & Auto-Tick:** In `LoginPage.jsx`, maintain `currentFrameData` state with a 60-second `setInterval` in `useEffect` so the frame updates automatically as time advances.
4. **Visual Layer Binding:** Bind `currentFrameData.src` to the left panel container's `backgroundImage: "url('" + currentFrameData.src + "')"`, preserving the 10px inset margin, `rounded-[22px]`, gradient scrim overlay (`#011425`), and `AuthVisualPanel`.
5. **Strict Scope Enforcement:** Zero edits or styling modifications to `AuthFormPanel.jsx`, the right panel, or the card geometry.

**Architecture Diagram:**

```mermaid
graph TD
    A["System Clock: new Date()"] --> B["getTimeBasedFrameData()"]
    B --> C{"Time of Day Window"}
    C -->|05:00 - 11:59 (420m)| D["Morning: Frames 1 - 25"]
    C -->|12:00 - 16:59 (300m)| E["Afternoon: Frames 26 - 48"]
    C -->|17:00 - 19:59 (180m)| F["Evening: Frames 49 - 76"]
    C -->|20:00 - 04:59 (540m)| G["Night: Frames 77 - 100"]
    D --> H["Padded Path: /frames/ezgif-frame-XXX.jpg"]
    E --> H
    F --> H
    G --> H
    H --> I["LoginPage.jsx Left Panel<br/>backgroundImage: url('/frames/ezgif-frame-XXX.jpg')"]
    I --> J["Dark Gradient Scrim Overlay (#011425)"]
```

---

## Global Constraints

- **Scope Isolation:** Modify ONLY the left visual panel in `LoginPage.jsx`. Absolutely zero modifications or restyling of `AuthFormPanel.jsx`, the right-side form, or the page container.
- **Resource Constraints:** Keep engine memory strictly under 250 MB RAM using 4 KB chunk discards.
- **Git Safety Rule:** AI assistant is strictly prohibited from executing `git commit`, `git merge`, `git rebase`, or `git push`.
- **Review Gate:** Zero code modifications will be executed until the user explicitly reviews and approves this plan.

---

## Proposed Changes

### Component 1: Static Frames Asset Directory (`frontend/public/frames/`)
#### [NEW] `frontend/public/frames/ezgif-frame-001.jpg` through `ezgif-frame-100.jpg`
- Create `frontend/public/frames/` directory.
- Copy all 100 frames from `frontend/public/timelapse/timelapse/` into `frontend/public/frames/`.
- Verify all 100 files exist and match sizes.

---

### Component 2: `LoginPage.jsx` Left Panel Dynamic Binding
#### [MODIFY] `frontend/src/pages/LoginPage.jsx`
- Add `getTimeBasedFrameData` function.
- Add `currentFrameData` state initialized via `getTimeBasedFrameData()`.
- Add `useEffect` with a 60-second timer to re-evaluate the frame as time passes and clear interval on unmount.
- Bind `currentFrameData.src` to the left panel `div`:
```jsx
style={{ backgroundImage: `url('${currentFrameData.src}')` }}
```
- Keep all existing classes, 10px margin, `rounded-[22px]`, scrim overlay, and `AuthVisualPanel`.

---

## Task Structure

### Task 1: Asset Directory Setup
- [x] Create `frontend/public/frames` directory.
- [x] Copy all 100 frame files (`ezgif-frame-001.jpg` – `ezgif-frame-100.jpg`) from `frontend/public/timelapse/timelapse/` to `frontend/public/frames/`.
- [x] Verify file count equals 100.

### Task 2: Update `LoginPage.jsx`
- [x] Add `getTimeBasedFrameData(date = new Date())` helper.
- [x] Initialize `const [currentFrameData, setCurrentFrameData] = useState(() => getTimeBasedFrameData());`.
- [x] Add `useEffect` to tick every 60,000ms.
- [x] Update inline style on the left panel container to load `currentFrameData.src`.
- [x] Verify right panel and form remain 100% untouched.

### Task 3: Build Verification & Testing
- [x] Run automated tests verifying frame mapping math for edge cases (`05:00`, `11:59`, `12:00`, `16:59`, `17:00`, `19:59`, `20:00`, `00:00`, `04:59`).
- [x] Run `cd frontend; npm run build` and ensure exit code 0.
- [x] Update `walkthrough.md`.
