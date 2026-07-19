# EduFlow Public And Auth Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a responsive, indigo-led EduFlow landing page plus functional login and registration experiences with a layered animated-book hero derived from the supplied visual reference.

**Architecture:** A single React 18 application owns the public routes and shares brand, navigation, book-scene, and authentication-shell components. CSS variables define the indigo visual system; CSS keyframes and a small pointer-parallax hook provide motion without a general animation dependency. Authentication remains a deterministic front-end simulation behind typed validation functions so a real API can replace the submit adapter later.

**Tech Stack:** React 18, TypeScript, Vite, React Router, Vitest, Testing Library, CSS modules/global CSS, Lucide React, Noto Sans SC Variable, Manrope Variable

## Global Constraints

- Only `web/`, this plan, the approved design specification, and project-root `design-qa.md` may change.
- Routes are exactly `/`, `/login`, `/register`, and `/app`, plus a public not-found screen.
- The public palette is led by `#3F51E8`, `#2635B8`, `#6475FF`, and `#7DDCFF`; `#7557F6` appears only at gradient edges and highlights.
- The book hero and brand imagery must use real raster assets, not CSS drawings, inline SVG, emoji, glyphs, or placeholders.
- CSS continuous animation is limited to the layered book scene and ambient knowledge flow.
- `prefers-reduced-motion: reduce` disables loops, reveal motion, and pointer parallax.
- Authentication is mock-only and must not modify backend, database, session, or API code.
- Target responsive widths are 375, 768, 1024, 1440, and 1680 pixels.
- Every behavior task follows red-green-refactor and ends with focused verification.

---

## File Structure

```text
web/
├── public/brand/eduflow-book-hero.png
├── public/brand/eduflow-mark.png
├── src/
│   ├── app/App.tsx
│   ├── app/App.test.tsx
│   ├── app/router.tsx
│   ├── components/auth/AuthShell.tsx
│   ├── components/brand/EduFlowBrand.tsx
│   ├── components/effects/BookHeroScene.tsx
│   ├── components/effects/usePointerParallax.ts
│   ├── components/layout/PublicHeader.tsx
│   ├── features/auth/auth.ts
│   ├── features/auth/auth.test.ts
│   ├── features/auth/LoginForm.tsx
│   ├── features/auth/RegisterForm.tsx
│   ├── pages/AppEntryPlaceholder.tsx
│   ├── pages/LandingPage.tsx
│   ├── pages/LoginPage.tsx
│   ├── pages/NotFoundPage.tsx
│   ├── pages/RegisterPage.tsx
│   ├── styles/global.css
│   ├── test/setup.ts
│   └── main.tsx
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

### Task 1: Create The Tested React Foundation

**Files:**
- Create: `web/package.json`
- Create: `web/index.html`
- Create: `web/tsconfig.json`
- Create: `web/vite.config.ts`
- Create: `web/src/main.tsx`
- Create: `web/src/app/App.tsx`
- Create: `web/src/app/App.test.tsx`
- Create: `web/src/test/setup.ts`

**Interfaces:**
- Consumes: Node 20+ and the repository `web/` directory.
- Produces: `App(): JSX.Element`, `npm run test`, `npm run typecheck`, `npm run build`, and `npm run dev`.

- [ ] **Step 1: Bootstrap the Product Design React starter into `web/` and install dependencies**

Run the provided Product Design bootstrap script with `web/` as the destination, then install `react@18.3.1`, `react-dom@18.3.1`, `react-router-dom`, `lucide-react`, `@fontsource-variable/manrope`, `@fontsource-variable/noto-sans-sc`, `vitest`, `jsdom`, and Testing Library packages. Preserve the starter's Vite dev script and add `test`, `typecheck`, and `verify` scripts.

- [ ] **Step 2: Write the first failing application test**

```tsx
import { render, screen } from "@testing-library/react";
import { App } from "./App";

it("renders the EduFlow public experience", () => {
  render(<App />);
  expect(screen.getByRole("link", { name: /EduFlow/ })).toBeInTheDocument();
});
```

- [ ] **Step 3: Run the test and confirm RED**

Run: `npm test -- src/app/App.test.tsx`  
Expected: FAIL because `App` does not yet render the EduFlow public experience.

- [ ] **Step 4: Add the minimal app shell and test setup**

`App` returns a semantic shell containing an `EduFlow` home link. Configure Vitest with jsdom and `@testing-library/jest-dom/vitest`.

- [ ] **Step 5: Run the focused test and confirm GREEN**

Run: `npm test -- src/app/App.test.tsx`  
Expected: one passing test and no console warnings.

### Task 2: Add Typed Authentication Validation

**Files:**
- Create: `web/src/features/auth/auth.ts`
- Create: `web/src/features/auth/auth.test.ts`

**Interfaces:**
- Produces: `validateLogin(values: LoginValues): LoginErrors`, `validateRegistration(values: RegistrationValues): RegistrationErrors`, and `simulateAuth(): Promise<{ ok: true }>`.

- [ ] **Step 1: Write failing tests for login validation**

```ts
expect(validateLogin({ email: "", password: "" })).toEqual({
  email: "请输入邮箱地址",
  password: "请输入密码",
});
expect(validateLogin({ email: "invalid", password: "password1" }).email)
  .toBe("请输入有效的邮箱地址");
```

- [ ] **Step 2: Run and confirm RED**

Run: `npm test -- src/features/auth/auth.test.ts`  
Expected: FAIL because the validation module does not exist.

- [ ] **Step 3: Implement login validation and registration tests**

Add registration tests for required nickname/email/password, an 8-character letter-plus-number password, matching confirmation, and accepted terms. Then implement the smallest pure validation functions that return field-keyed Chinese messages.

- [ ] **Step 4: Run and confirm GREEN**

Run: `npm test -- src/features/auth/auth.test.ts`  
Expected: all validation tests pass.

### Task 3: Generate And Place The Indigo Brand Assets

**Files:**
- Create: `web/public/brand/eduflow-book-hero.png`
- Create: `web/public/brand/eduflow-mark.png`

**Interfaces:**
- Consumes: the supplied reference screenshot and exact palette from Global Constraints.
- Produces: optimized raster assets with no embedded words or watermarks.

- [ ] **Step 1: Generate the book hero**

Use the reference as art-direction input to produce a polished 3D open book with a translucent indigo play-and-knowledge structure emerging from the spine, soft ice-blue light, minimal violet edge reflections, and enough clean space around the silhouette for layered animation.

- [ ] **Step 2: Generate or crop the matching EduFlow mark**

Create a compact open-book and play-node brand mark in the same indigo material language. Keep it free of text so `EduFlow` remains accessible HTML.

- [ ] **Step 3: Inspect both assets**

Open both raster files at original detail. Reject embedded text, cropping, muddy transparency edges, incorrect violet dominance, or mismatched material rendering.

### Task 4: Build Routes, Landing Narrative, And Shared Motion

**Files:**
- Create: `web/src/app/router.tsx`
- Create: `web/src/components/brand/EduFlowBrand.tsx`
- Create: `web/src/components/layout/PublicHeader.tsx`
- Create: `web/src/components/effects/BookHeroScene.tsx`
- Create: `web/src/components/effects/usePointerParallax.ts`
- Create: `web/src/pages/LandingPage.tsx`
- Create: `web/src/pages/AppEntryPlaceholder.tsx`
- Create: `web/src/pages/NotFoundPage.tsx`
- Modify: `web/src/app/App.tsx`
- Modify: `web/src/styles/global.css`
- Test: `web/src/app/App.test.tsx`

**Interfaces:**
- Produces: browser routes, `EduFlowBrand`, `PublicHeader`, and `BookHeroScene({ compact?: boolean })`.

- [ ] **Step 1: Add failing route and landing interaction tests**

Test that the landing page exposes the heading “让知识动起来。让理解自然发生。”, that “免费开始” navigates to `/register`, that “登录” navigates to `/login`, and that “查看如何工作” targets `#how-it-works`.

- [ ] **Step 2: Run and confirm RED**

Run: `npm test -- src/app/App.test.tsx`  
Expected: FAIL because the router and landing controls are missing.

- [ ] **Step 3: Implement the route tree and public content**

Build the header, hero, three floating capability notes, three capability cards, three-step workflow, final conversion section, `/app` placeholder, and a not-found page. Use real buttons and links; do not add pricing, testimonials, or unavailable third-party actions.

- [ ] **Step 4: Implement purposeful motion**

Layer the hero raster with small foreground page overlays derived from the same asset crop, ambient knowledge-flow images, staggered card drift, and an 8px maximum pointer parallax. Under reduced motion, set every animation and transform to the static final state.

- [ ] **Step 5: Run route tests and confirm GREEN**

Run: `npm test -- src/app/App.test.tsx`  
Expected: all public route tests pass.

### Task 5: Build Functional Login And Registration Pages

**Files:**
- Create: `web/src/components/auth/AuthShell.tsx`
- Create: `web/src/features/auth/LoginForm.tsx`
- Create: `web/src/features/auth/RegisterForm.tsx`
- Create: `web/src/pages/LoginPage.tsx`
- Create: `web/src/pages/RegisterPage.tsx`
- Modify: `web/src/app/App.test.tsx`
- Modify: `web/src/styles/global.css`

**Interfaces:**
- Consumes: validation functions, `simulateAuth`, router navigation, and `BookHeroScene({ compact: true })`.
- Produces: accessible login and registration flows that navigate to `/app` after simulated success.

- [ ] **Step 1: Add failing form behavior tests**

Test visible labels, invalid-email feedback, password visibility toggle, mismatched registration passwords, unaccepted terms, login/register cross-links, submit loading text, and successful navigation to `/app`.

- [ ] **Step 2: Run and confirm RED**

Run: `npm test -- src/app/App.test.tsx`  
Expected: FAIL because auth pages and form states do not exist.

- [ ] **Step 3: Implement semantic forms and shared auth shell**

Use labeled inputs with `autoComplete`, `aria-invalid`, `aria-describedby`, stable inline error regions, a password visibility button, disabled duplicate submission, and an `aria-live` submission status. Preserve entered values after validation failures.

- [ ] **Step 4: Run and confirm GREEN**

Run: `npm test -- src/app/App.test.tsx`  
Expected: all landing and authentication behavior tests pass without act warnings.

### Task 6: Verify, Render, Compare, And Polish

**Files:**
- Modify: frontend files only when fixing observed issues.
- Create: `design-qa.md`
- Create: local screenshots under `web/.artifacts/`.

**Interfaces:**
- Consumes: the supplied reference image, local implementation, and the Product Design QA rubric.
- Produces: a browser-tested build and `design-qa.md` with `final result: passed`.

- [ ] **Step 1: Run full automated verification**

Run: `npm run verify`  
Expected: typecheck, all tests, and production build exit with code 0.

- [ ] **Step 2: Start the local app and open it in the in-app browser**

Inspect `/`, `/login`, `/register`, and `/app`; test the primary actions, mobile navigation, keyboard focus, password toggles, form validation, successful submission, console errors, and reduced-motion presentation.

- [ ] **Step 3: Capture matched screenshots**

Capture the landing page at 1680×945 to match the reference ratio, then capture 375×844 landing and authentication screens. Save the exact implementation screenshots under `web/.artifacts/`.

- [ ] **Step 4: Run visual comparison and fix P0–P2 findings**

Combine the original reference and matched implementation screenshot into one comparison input. Evaluate typography, spacing, palette, image quality, copy, responsiveness, and interaction affordances. Fix every P0, P1, and P2 issue, recapture, and compare again.

- [ ] **Step 5: Write the blocking QA report**

Create `design-qa.md` containing the source path, screenshot paths, viewports, states, primary interactions tested, console check, full-view evidence, focused-region evidence, iteration history, residual P3 notes, and exact line `final result: passed` only after no P0–P2 findings remain.

- [ ] **Step 6: Re-run fresh verification**

Run: `npm run verify`  
Expected: all commands pass after visual fixes.

