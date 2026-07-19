# EduFlow Frontend Design System

**Status:** Approved direction, implementation pending  
**Updated:** 2026-07-19  
**Product type:** AI-native teaching authoring workspace  
**Foundation:** shadcn/ui only; external libraries may provide decorative effects, never base controls

## 1. Design thesis

EduFlow should feel like a calm teaching studio with an observable reasoning engine. The interface uses one stable information architecture and one component tree across three switchable visual themes:

- `dawn` / 晨光：warm, scholarly and optimistic.
- `deep` / 深海：immersive, technical and focused.
- `canvas` / 画布：spatial, experimental and creation-oriented.

Themes change semantic tokens, surface materials and decorative effect parameters. They must not fork page markup, reset editor state or change interaction semantics.

The EduFlow book-and-play icon remains the primary brand signature in all themes. Its blue-to-violet gradient is not recolored by theme.

## 2. Canonical workbench

The teacher editor uses a stable four-region composition:

1. Global shell: collapsible left sidebar, breadcrumb/header and theme selector.
2. Teaching brief: natural-language prompt and structured constraints.
3. Reasoning plan: editable lesson steps with visible agent status.
4. Simulation preview: algorithm canvas, playback, state table and narration.

The desktop workbench is a three-column sequence: `brief -> plan -> preview`. The flow reads left-to-right, while the AI progress strip stays at the bottom of the content area. Do not nest decorative cards inside cards; use separators, section headers and grouped list rows for hierarchy.

Responsive behavior:

- `>= 1440px`: full sidebar and three-column workbench.
- `1024–1439px`: icon sidebar, compact brief, plan and preview remain visible.
- `768–1023px`: sidebar becomes off-canvas; brief and plan occupy a collapsible rail; preview is primary.
- `< 768px`: single-column task flow; editing settings open in a Sheet and simulation controls stay reachable without horizontal scrolling.

## 3. Typography and geometry

- UI family: `Inter Variable`, `Noto Sans SC`, `PingFang SC`, `Microsoft YaHei`, sans-serif.
- Use one UI family throughout the application. Display serif typography is reserved for future marketing pages, not the editor.
- Body: 14px/1.55 desktop, 15px/1.55 mobile.
- Labels and metadata: 12–13px; section title: 16–18px; workspace title: 20–24px.
- Numeric algorithm state uses tabular figures.
- Spacing scale: 4, 8, 12, 16, 24, 32, 48px.
- Radius scale: 8px controls, 12px grouped surfaces, 16px primary panels, fully rounded status pills only.
- Borders communicate structure; shadows communicate elevation. Never apply both heavily to every surface.

## 4. Theme tokens

All values are semantic CSS variables applied to `<html data-theme="...">`. These values are starting tokens and must be contrast-tested in implementation.

| Token | 晨光 `dawn` | 深海 `deep` | 画布 `canvas` |
|---|---|---|---|
| `--background` | `oklch(0.985 0.009 83)` | `oklch(0.135 0.025 255)` | `oklch(0.982 0.008 250)` |
| `--foreground` | `oklch(0.235 0.035 255)` | `oklch(0.955 0.010 250)` | `oklch(0.205 0.030 260)` |
| `--card` | `oklch(0.998 0.003 90)` | `oklch(0.175 0.028 255)` | `oklch(0.998 0.003 250)` |
| `--card-foreground` | `oklch(0.235 0.035 255)` | `oklch(0.955 0.010 250)` | `oklch(0.205 0.030 260)` |
| `--primary` | `oklch(0.575 0.205 274)` | `oklch(0.690 0.180 251)` | `oklch(0.570 0.220 265)` |
| `--primary-foreground` | `oklch(0.985 0.005 270)` | `oklch(0.125 0.025 255)` | `oklch(0.990 0.005 260)` |
| `--secondary` | `oklch(0.945 0.025 285)` | `oklch(0.225 0.035 255)` | `oklch(0.940 0.022 252)` |
| `--muted` | `oklch(0.955 0.014 255)` | `oklch(0.205 0.025 255)` | `oklch(0.950 0.012 255)` |
| `--muted-foreground` | `oklch(0.490 0.030 255)` | `oklch(0.720 0.025 250)` | `oklch(0.500 0.030 255)` |
| `--accent` | `oklch(0.920 0.055 278)` | `oklch(0.720 0.140 194)` | `oklch(0.925 0.050 263)` |
| `--accent-foreground` | `oklch(0.330 0.090 275)` | `oklch(0.135 0.025 255)` | `oklch(0.310 0.100 265)` |
| `--border` | `oklch(0.890 0.018 260)` | `oklch(0.300 0.035 250)` | `oklch(0.885 0.018 255)` |
| `--ring` | `oklch(0.620 0.200 274)` | `oklch(0.720 0.150 210)` | `oklch(0.620 0.205 265)` |
| `--success` | `oklch(0.625 0.110 145)` | `oklch(0.720 0.145 165)` | `oklch(0.625 0.110 145)` |
| `--warning` | `oklch(0.720 0.145 75)` | `oklch(0.780 0.135 80)` | `oklch(0.720 0.145 75)` |
| `--destructive` | `oklch(0.600 0.220 25)` | `oklch(0.690 0.190 25)` | `oklch(0.600 0.220 25)` |

Algorithm visualization adds semantic state tokens: `--graph-settled`, `--graph-current`, `--graph-unvisited`, `--graph-edge`, and `--graph-edge-active`. Status must never rely on color alone; pair color with labels, icons, line styles or node markers.

Theme material rules:

- 晨光: warm paper surfaces, mineral blue/violet accents, restrained sage status color, soft directional shadows.
- 深海: graphite layers, spectral blue/cyan active states, restrained violet highlights, luminous borders only on active regions.
- 画布: pearl-gray field, crisp ink borders, ultramarine structure and restrained coral/cyan signals, almost no drop shadow.

## 5. Theme switching

- Use a shadcn `DropdownMenuRadioGroup` in the workspace header with 晨光、深海、画布 choices and a visible current-theme label.
- Store the selected id in `localStorage` under `eduflow-theme`.
- Apply `data-theme` before React hydration through a small inline startup script to avoid a color flash.
- With no saved choice, map a dark system preference to `deep` and a light preference to `canvas`.
- Announce a changed theme through an unobtrusive live region; do not reload or reset editor data.
- Theme changes use a 180ms color/border transition. Large background effects cross-fade only when reduced motion is not requested.

## 6. shadcn component map

Use the `base-nova` preset with CSS variables. Base UI supports React 17–19, so the existing React 18 foundation remains valid.

| Region | shadcn primitives |
|---|---|
| App shell | `SidebarProvider`, `Sidebar`, `SidebarInset`, `SidebarTrigger`, `Breadcrumb`, `DropdownMenu`, `Avatar` |
| Teaching brief | `FieldGroup`, `Field`, `InputGroup`, `InputGroupTextarea`, `Button`, `ToggleGroup`, `Select`, `Slider`, `Switch`, `Collapsible` |
| Reasoning plan | `Item`, `Badge`, `Separator`, `Progress`, `ScrollArea`, `Collapsible`, `ButtonGroup` |
| Simulation | `ResizablePanelGroup`, `Tabs`, `Table`, `Slider`, `Tooltip`, `Popover`, `ButtonGroup`, `Sheet` |
| AI state | `Alert`, `Progress`, `Spinner`, `Collapsible`, `Sonner` |
| Loading/empty/error | `Skeleton`, `Empty`, `Alert`, `Spinner`, `Sonner` |

Rules:

- Shadcn owns every control, form field, navigation item, panel, dialog, table, toast, loading state and empty state.
- Prefer built-in variants and semantic tokens. Add `className` for layout, responsive behavior or local composition, not to reimplement component states.
- Use `Field` and `FieldGroup` for forms, `ToggleGroup` for mutually exclusive visual choices and `InputGroup` for prompt affordances.
- Overlays require accessible titles. All icon-only actions require tooltips and accessible names.
- Use Lucide as the single interface icon library; never use emoji as controls.

## 7. Effect layer

External components live in `src/components/effects/`. Each file records source URL, license, dependencies and local changes. Effects decorate or connect shadcn components; they never replace them.

Approved pool, capped at 6–10 reusable components for the whole site:

| Effect | Source | Purpose |
|---|---|---|
| `WorkspaceGrid` | Magic UI Animated Grid Pattern | Theme-aware ambient canvas; static fallback |
| `KnowledgeBeam` | Magic UI Animated Beam | Brief-to-plan-to-preview relationship; active generation only |
| `GenerationBorder` | Magic UI Border Beam / Shine Border | Active AI progress strip only |
| `DeepSpotlight` | Aceternity Spotlight | Deep-theme focal lighting |
| `ReasoningTrace` | Aceternity Tracing Beam | Active plan progression |
| `NarrationReveal` | Aceternity Text Generate Effect | One-shot explanation reveal |
| `MicroLoader` | Uiverse, MIT | Small decorative agent-processing indicator; not a replacement for shadcn Spinner |

No screen may show more than two continuously prominent animations at once. Hover and focus micro-interactions do not count. Theme-specific backgrounds are mutually exclusive and loaded lazily.

## 8. Motion

- Fast feedback: 120ms; standard transition: 180–220ms; panel transition: 280–320ms.
- Standard easing: `cubic-bezier(0.22, 1, 0.36, 1)`.
- Animate opacity and transform first. Avoid layout-shifting scale effects and decorative parallax inside the editor.
- Generation may loop only while work is active. Finished and paused states become static.
- Under `prefers-reduced-motion: reduce`, remove background drift, beam travel, typewriter effects and nonessential transforms; retain instant state changes and progress text.

## 9. Accessibility and interaction

- Meet WCAG AA contrast: 4.5:1 for normal text and 3:1 for large text and non-text UI boundaries.
- Every interactive element is keyboard reachable and has a visible `:focus-visible` ring.
- Sidebar, editor rail and simulation preserve a predictable tab order matching visual order.
- Provide a skip link to the active workspace.
- AI progress uses `aria-live="polite"`; errors use concise text and recovery actions.
- Minimum touch target is 44x44px on touch layouts.
- Do not hide required actions behind hover alone.

## 10. Implementation checks

- [ ] One component tree renders all three themes.
- [ ] Theme persists and applies before hydration without flashing.
- [ ] Theme switching preserves editor, playback and agent state.
- [ ] All foundational UI comes from shadcn `base-nova`.
- [ ] Effect components document provenance and have static fallbacks.
- [ ] No more than two prominent looping animations appear per screen.
- [ ] Reduced-motion mode is complete.
- [ ] Keyboard, focus, live-region and contrast checks pass in all three themes.
- [ ] Layout is verified at 375, 768, 1024 and 1440px.
- [ ] No horizontal overflow or fixed-navigation content occlusion.
