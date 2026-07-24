# EduFlow landing and Dijkstra QA checklist

## Automated verification

| Check | Result | Evidence |
| --- | --- | --- |
| Demo accessibility and motion coverage | Pass | `npm test -- src/features/demo/DijkstraDemo.test.tsx src/features/demo/useDemoPlayback.test.tsx`: 2 files, 15 tests passed. |
| Frontend test suite | Pass | `npm test`: 17 files, 118 tests passed. |
| TypeScript no-emit check | Pass | `npm run typecheck` exited 0. |
| Lint | Pass with existing warnings | `npm run lint` exited 0; it reported 17 existing warnings outside the Task 9 files. |
| Production build | Blocked by existing errors | `npm run build` exits 1 with 23 TypeScript errors outside this task's scope. See the build blocker list below. |
| Combined verification | Blocked by production build | `npm run verify` completed typecheck and 118 tests, then exited 1 at the same build errors. |
| Public demo network audit | Pass | The public demo, explore, landing, and simulation-model imports contain no `/api/generate`, `/api/projects`, service-client import, or LLM-provider reference. |

### Build blockers (not changed by Task 9)

- `FeedbackPanel.tsx`: unused `Badge` import.
- `FileUploader.tsx`: three functional updater values are incompatible with the declared setter type.
- `simulation-model.ts`: three `enum` declarations conflict with `erasableSyntaxOnly`.
- `SimulationPreview.tsx`: unused `needsInteraction` plus a non-iterable union destructure.
- `visual-objects/ArrayObject.tsx`: invalid `color` access and two invalid React keys.
- `visual-objects/LinkedListObject.tsx`: `unknown` rendered as a React node.
- `visual-objects/MemoryBlockObject.tsx`: unreachable nullish fallback and an invalid React node.
- `visual-objects/TableObject.tsx`: unused `useMemo` import.
- `LandingPage.test.tsx`: Node test globals/modules are excluded from the build type context.
- `ProjectWorkspace.tsx`: two `unknown` values rendered as React nodes.
- `api-client.test.ts`: two results are inferred as `unknown`.

## Browser QA — main-agent verification pending

Every row below is intentionally pending. No visual or browser-interaction result is implied by automated checks.

| Status | Route | Viewport / setting | Expected result | Actual result | Follow-up commit |
| --- | --- | --- | --- | --- | --- |
| Pending | `/` | 1440×900, Light | Paper-light landing, readable focus/status colors, complete static hero. | Not performed; reserved for main-agent browser QA. | — |
| Pending | `/` | 1440×900, Dark | Warm dark landing, readable focus/status colors, no layout shift. | Not performed; reserved for main-agent browser QA. | — |
| Pending | `/explore/dijkstra` | 1440×900, Light | Full Dijkstra controls and status table are usable. | Not performed; reserved for main-agent browser QA. | — |
| Pending | `/explore/dijkstra` | 1440×900, Dark | Full Dijkstra controls and status table are usable. | Not performed; reserved for main-agent browser QA. | — |
| Pending | `/` | 768×1024, Light | Landing sections remain readable and appropriately stacked. | Not performed; reserved for main-agent browser QA. | — |
| Pending | `/` | 768×1024, Dark | Landing sections remain readable and appropriately stacked. | Not performed; reserved for main-agent browser QA. | — |
| Pending | `/explore/dijkstra` | 768×1024, Light | Demo controls, graph, and data retain usable order. | Not performed; reserved for main-agent browser QA. | — |
| Pending | `/explore/dijkstra` | 768×1024, Dark | Demo controls, graph, and data retain usable order. | Not performed; reserved for main-agent browser QA. | — |
| Pending | `/` | 390×844, Light | Text leads, product window follows, navigation remains usable. | Not performed; reserved for main-agent browser QA. | — |
| Pending | `/` | 390×844, Dark | Text leads, product window follows, navigation remains usable. | Not performed; reserved for main-agent browser QA. | — |
| Pending | `/explore/dijkstra` | 390×844, Light | Graph, controls, explanation, and timeline stack without requiring precise drag. | Not performed; reserved for main-agent browser QA. | — |
| Pending | `/explore/dijkstra` | 390×844, Dark | Graph, controls, explanation, and timeline stack without requiring precise drag. | Not performed; reserved for main-agent browser QA. | — |
| Pending | `/explore/dijkstra` | Reduced-motion emulation | Explicit activation leaves static steps available and does not autoplay. | Not performed; automated coverage passes; browser verification pending. | — |
| Pending | `/explore/dijkstra` | Keyboard-only | Space toggles playback when focus is not editable; arrows move frames; controls retain native key behavior. | Not performed; automated coverage passes; browser verification pending. | — |
| Pending | `/` and `/explore/dijkstra` | 200% browser zoom | Content reflows without clipped essential controls or unreadable overlap. | Not performed; reserved for main-agent browser QA. | — |
