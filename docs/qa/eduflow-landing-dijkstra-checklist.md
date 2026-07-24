# EduFlow landing and Dijkstra QA checklist

## Automated verification

| Check | Result | Evidence |
| --- | --- | --- |
| Demo accessibility and motion coverage | Pass | `npm test -- src/features/demo/DijkstraDemo.test.tsx src/features/demo/useDemoPlayback.test.tsx`: 2 files, 19 tests passed. |
| Frontend test suite | Pass | `npm test`: 18 files, 131 tests passed. |
| Root TypeScript command | Informational only | The root `tsconfig.json` has `files: []`; the application-specific command below is the authoritative check. |
| Application TypeScript check | Pass | `npx tsc --noEmit -p tsconfig.app.json` exits 0. |
| Lint | Pass with existing warnings | `npm run lint` exits 0; 13 pre-existing advisory warnings remain. |
| Production build | Pass | `npm run build` exits 0 and emits separate `DijkstraDemo` JavaScript/CSS chunks. Vite retains its non-blocking main-chunk size advisory. |
| Combined verification | Pass | `npm run verify` exits 0 after application typecheck, 131 tests, and the production build. |
| Public demo network audit | Pass | The public demo, explore, landing, and simulation-model imports contain no `/api/generate`, `/api/projects`, service-client import, or LLM-provider reference. |

### Production build repair

Commit `8f6894e` resolves the 23 application diagnostics with narrow type
repairs: unused code removal, `as const` value/type pairs for erasable syntax,
external DSL value narrowing, explicit API test result types, and a Node-only
stylesheet source contract outside the application TypeScript project. It does
not weaken compiler, lint, or test configuration.

## Browser QA

| Status | Route | Viewport / setting | Expected result | Actual result | Follow-up commit |
| --- | --- | --- | --- | --- | --- |
| Pass | `/` | 1440×900, Light | Paper-light landing, readable focus/status colors, complete static hero. | No horizontal overflow; hero ends at 786.03 px, Chapter 02 is visible, six graph nodes fit inside the compact graph, and previous/next controls are 44×44 px. Evidence: `implementation-home-light-1440x900-final.png`. | `c9abb9b` |
| Pass | `/` | 1440×900, Dark | Warm dark landing, readable focus/status colors, no layout shift. | Same geometry and interaction hierarchy as Light; warm dark colors retain readable status and focus treatment. Evidence: `implementation-home-dark-1440x900-final.png`. | `c9abb9b` |
| Pass | `/explore/dijkstra` | 1440×900, Light | Full Dijkstra controls and status table are usable. | Fresh route keeps `scrollY=0` and body focus; intro, graph, ledger, narration, timeline, and controls remain in usable order without horizontal overflow. Evidence: `implementation-explore-light-1440x900.png`. | `095ec84` |
| Pass | `/explore/dijkstra` | 1440×900, Dark | Full Dijkstra controls and status table are usable. | Dark theme preserves the full demo layout, labels, focus treatment, and status contrast without stealing initial focus. Evidence: `implementation-explore-dark-1440x900.png`. | `095ec84` |
| Pass | `/` | 768×1024, Light | Landing sections remain readable and appropriately stacked. | DOM geometry: `clientWidth=753`, `scrollWidth=753`; hero copy and demo remain inside the viewport and mobile navigation is active. | `c134e7b` |
| Pass | `/` | 768×1024, Dark | Landing sections remain readable and appropriately stacked. | Same no-overflow geometry as Light; theme change does not shift layout. | `c134e7b` |
| Pass | `/explore/dijkstra` | 768×1024, Light | Demo controls, graph, and data retain usable order. | DOM geometry: `clientWidth=753`, `scrollWidth=753`; demo width is 691 px and the parameter panel remains inside the viewport. | `c134e7b` |
| Pass | `/explore/dijkstra` | 768×1024, Dark | Demo controls, graph, and data retain usable order. | Same no-overflow geometry and content order as Light. | `c134e7b` |
| Pass | `/` | 390×844, Light | Text leads, product window follows, navigation remains usable. | Copy, actions, and demo stack without horizontal overflow; mobile navigation opens and Escape restores focus. Evidence: `implementation-home-light-390x844.png`. | `c134e7b` |
| Pass | `/` | 390×844, Dark | Text leads, product window follows, navigation remains usable. | Same responsive order and interaction behavior as Light. Evidence: `implementation-home-dark-390x844.png`. | `c134e7b` |
| Pass | `/explore/dijkstra` | 390×844, Light | Graph, controls, explanation, and timeline stack without requiring precise drag. | Fresh route remains at `scrollY=0`, body focus is preserved, and essential content stacks without horizontal overflow. Evidence: `implementation-explore-light-390x844.png`. | `095ec84` |
| Pass | `/explore/dijkstra` | 390×844, Dark | Graph, controls, explanation, and timeline stack without requiring precise drag. | Same responsive order, initial reading position, and status readability as Light. Evidence: `implementation-explore-dark-390x844.png`. | `095ec84` |
| Pass (automated) | `/explore/dijkstra` | Reduced-motion emulation | Five useful static checkpoints remain available without autoplay or no-op playback actions. | Real `MediaQueryList` change tests pass in both directions; five named checkpoints work; body Space remains available for page scrolling and React Flow Space-pan is disabled only in reduced motion. The selected browser cannot emulate this media feature, so no unsupported browser claim is made. | `c9abb9b` |
| Pass (automated) | `/explore/dijkstra` | Keyboard-only | Space toggles playback in normal motion; arrows and 44×44 px previous/next controls move frames; native controls retain their keys. | Automated keyboard coverage passes, including reduced-motion Space fallthrough and ArrowRight stepping. Browser Escape/focus restoration and fresh-route body focus pass. | `c9abb9b` |
| Pass | `/` and `/explore/dijkstra` | 200% browser zoom | Content reflows without clipped essential controls or unreadable overlap. | 720×450 CSS viewport produced no horizontal overflow or clipped essential controls on either route; mobile navigation activates as expected. | `c134e7b` |

## Review follow-up — accessibility safeguards

| Check | Result | Evidence |
| --- | --- | --- |
| Native reduced-motion change while autoplaying | Pass | A real `MediaQueryList` `change` test confirms playback immediately returns to the poster and a pending timer cannot advance a frame. |
| Native reduced-motion change from true to false | Pass | A real `MediaQueryList` `change` test confirms explicit playback becomes available without remounting. When `matchMedia` exists, its subscribed value is authoritative; Motion is only a fallback when it does not. |
| Keyboard frame boundaries | Pass | ArrowLeft at the first frame leaves the poster state intact; ArrowRight at the final autoplay frame leaves the completed state intact. |
| Modified/repeated Space | Pass | Shift+Space and repeated Space are ignored; unmodified Space still starts playback. |
| Reduced-motion Space | Pass | Body Space is not prevented and does not call a hidden no-op; ArrowLeft/ArrowRight and five static checkpoints remain available. |
| Offscreen autoplay | Pass | `IntersectionObserver` pauses autoplay when the demo leaves the viewport and keeps one observer across frame ticks; mode transitions re-observe cleanly. |
| Auth-aware landing | Pass | Signed-out actions remain unchanged; signed-in desktop/mobile header actions use `打开工作台`, and the Hero uses `继续上次项目`. |
| Lazy public demo | Pass | Landing and explore both expose honest Suspense loading status and the production build emits separate demo chunks. |

## Browser QA iteration — first viewport chapter cue

| Status | Route | Viewport / setting | Expected result | Actual result | Follow-up commit |
| --- | --- | --- | --- | --- | --- |
| Pass | `/` | 1440×900, Light | The `#product` chapter label and heading visibly peek into the first viewport; target section top is approximately 840 px or less, while the compact graph, ledger, narration, controls, and timeline remain present. | Before the revision, `#product` began at 900.67 px. Final post-review measurement is 786.03 px, with both 44×44 px frame controls and all compact-demo regions still present. Evidence: `implementation-home-light-1440x900-final.png`. | `c9abb9b` |

## Browser QA iteration — compact graph first render

| Status | Route | Viewport / setting | Expected result | Actual result | Follow-up commit |
| --- | --- | --- | --- | --- | --- |
| Pass | `/` | 1440×900, Light, fresh route at page top | Compact graph nodes and edges fit inside the graph panel without user action, while the Chapter 02 cue remains visible at the bottom of the first viewport. | Final graph panel is y=430.06..650.77 and all six nodes are y=444.06..637.06. The viewport transform is `matrix(0.623788, 0, 0, 0.623788, 231.318, -12.3258)`. The earlier offset only occurred when reloading mid-page during HMR; the normal fresh-route state passes. | `c134e7b` |
