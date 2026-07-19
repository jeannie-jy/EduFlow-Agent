# Task 6 Report: Routes and frontend-only states

## Red / green evidence

- **RED:** `npm test -- src/app/router.test.tsx` failed as expected because `@/app/router` did not exist. The new test declared all eight required memory-router cases.
- **GREEN:** after implementing the router, `npm test -- src/app/router.test.tsx && npm run typecheck` passed: 8 route cases passed and TypeScript reported no errors.

## Files

- Created `web/src/app/router.tsx`
- Created `web/src/app/router.test.tsx`
- Created `web/src/pages/RouteEmptyState.tsx`
- Modified `web/src/app/App.tsx`
- Modified `web/src/components/workbench/WorkbenchPage.tsx`
- Modified `web/src/components/layout/AppShell.test.tsx`

## Route semantics

| Path | Rendered heading | State |
| --- | --- | --- |
| `/` | 教学工作台 | WorkbenchPage |
| `/new` | 新建推演 | Frontend-only empty state |
| `/project/demo/plan` | 教学计划确认 | Frontend-only empty state |
| `/project/demo/edit` | 教师编辑器 | Frontend-only empty state |
| `/project/demo/play` | 交互式播放器 | Frontend-only empty state |
| `/project/demo/export` | 导出中心 | Frontend-only empty state |
| `/templates` | 知识点模板库 | Frontend-only empty state |
| unmatched paths | 页面未找到 | 404 with a link to `/` |

All unfinished business states use the exact copy: `该能力将在对应功能分支中实现；当前页面不连接后端服务。` No API, authentication, settings, loading, or extra routes were added.

Routes share one nested `ShellRoute` and use `Outlet`, so the theme provider and `AppShell` stay mounted while only the route content changes. Existing workbench effect imports and lazy loading were not changed.

## Verification

- `npm test -- src/app/router.test.tsx && npm run typecheck` — pass (8 route tests)
- `npm test` — pass (6 files, 27 tests)
- `npm run typecheck` — pass
- `npm run build` — pass
- `git diff --check` — pass

## Commit

Pending at report creation.

## Self-review

- Confirmed all eight required headings via a memory router.
- Confirmed unfinished states use Shadcn `Empty` primitives and the mandated honest copy.
- Confirmed the 404 has a real client-side return action to `/`.
- Confirmed app routing is initialized once at module scope and the shared shell wraps the outlet.

## Concerns

- Production build succeeds but reports the existing Vite warning that the main bundle is larger than 500 kB after minification. This task did not change the existing deferred effect boundary or add a new large dependency.
