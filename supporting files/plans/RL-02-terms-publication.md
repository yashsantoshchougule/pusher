# RL-02 follow-up — Approve and publish the Terms

Must Fix. Item 1 in the current two-task request and the Terms follow-up to [RL-02](RL-02-account-recovery-and-terms.md). The source is the PDF supplied by the owner at `C:/yash/aa.pdf`. Record verification evidence in this local plan.

## Task prompt

Publish the project owner's approved Terms through the existing `/terms` page. Use the exact wording from the supplied PDF once the owner approves it, or use an approved replacement. Update the sign-up checkbox to refer to the approved Terms and retain the unchecked default. Verify that email, Google, and GitHub sign-up continue to require the checkbox and that existing users can sign in normally.

The owner approved the four sections exactly as written in `C:/yash/aa.pdf` in this chat on 24 November 2026. Use the reviewed PDF identified by the SHA-256 below. Remove the draft notice and show the signup wording “I agree to the Terms & Conditions”.

## Baseline and implementation

On 24 November 2026, visual review of both PDF pages found that page 1 shows the same four sections as `frontend/src/pages/TermsPage.jsx` and still identifies the wording as a draft. Page 2 is blank. The PDF SHA-256 is `c439a42359d102b5b04b917470fe8da26eb17a5171915640442a8d83a4f7a5b1`. The page and signup checkbox identify the text as a review draft. `frontend/src/App.jsx` already routes `/terms`, and the email and OAuth buttons use the same consent state in `frontend/src/components/auth/AuthFormPanel.jsx`.

1. Verify the owner's explicit decision for the exact text before removing the draft notices. If the wording changed after the decision, reconcile the difference with the owner.
2. Copy the approved text into `TermsPage.jsx`, remove the review banner, and update the visible and accessible consent wording in `AuthFormPanel.jsx`. Keep the link, checkbox behavior, form wiring, and app routing. Update the draft sentence in `README.md` to describe the released page.
3. Update `supporting files/testing/unit/test_account_recovery.mjs` where the view checks expect the draft banner. Assert that the approved headings and the agreed text are rendered. Before publication, verify that checking and clearing the consent checkbox enables and disables all three signup actions and that the email submit handler rejects an unchecked submission. Retain the login and password recovery checks.
4. Run the focused tests and a production build. Verify `/terms` directly and through the signup link in a local browser. Use synthetic provider behavior. Record the approved wording reference, check results, and status in this file before starting task 2.

```powershell
node --test 'supporting files/testing/unit/test_account_recovery.mjs' 'supporting files/testing/unit/test_sign_in.mjs'
npm run build --prefix frontend
```

Acceptance requires the exact approved copy at `/terms`, the approved wording in the consent control, and passing local verification. Any rollback restores the prior Terms page and checkbox copy together. Local implementation is the handoff to the next task, which covers owner publication and verification from the exact published commit.

## Local verification before approval

The focused Node command above passed 16 tests with zero failures and zero skips. Added a component regression that checks and clears consent, verifies all three signup buttons follow the change, and confirms the email submit handler rejects unchecked submissions. Existing checks cover the draft page, signup link, and ordinary login. All 88 Node unit tests passed, and the production build passed with the existing bundle-size warning. These checks ran against the draft. Final-wording tests and release verification remain pending.

## Result after approval

Verified in the local checkout on 24 November 2026. The `/terms` page displays the owner-approved PDF wording without the draft banner. Signup now says “I agree to the Terms & Conditions” and starts unchecked. The exact-copy regression checks all four headings and paragraphs.

- The focused Node command above passed 17 tests. All 89 Node unit tests and 10 clock checks passed. The production build passed with the existing bundle-size warning.
- With a loopback-only simulated signed-out session, the browser showed all three signup buttons disabled before consent, enabled after checking, and disabled again after clearing. The signup link opened `/terms`, and reloading that route showed all four sections.
- Local acceptance passed. Publication of the reviewed Git commit and verification from a clean checkout are tracked in [RL-03](RL-03-release-candidate.md).
