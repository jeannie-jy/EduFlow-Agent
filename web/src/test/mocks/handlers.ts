/**
 * MSW 测试服务器 — 用于组件测试中的 API mock。
 */

import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

// ============================================================================
// Handlers
// ============================================================================

export const handlers = [
  // ── Auth session bootstrap ───────────────────────────────
  http.get("http://localhost:8000/api/auth/me", () => {
    const cached = localStorage.getItem("eduflow-auth");
    if (!cached) {
      return HttpResponse.json(
        { error: { code: "UNAUTHORIZED", message: "Authentication required" } },
        { status: 401 },
      );
    }
    const state = JSON.parse(cached) as { id?: string; nickname: string; email: string; role?: string };
    return HttpResponse.json({
      id: state.id ?? "test-user",
      nickname: state.nickname,
      email: state.email,
      role: state.role ?? "teacher",
      email_verified: true,
    });
  }),

  // ── Projects ──────────────────────────────────────────────
  http.get("http://localhost:8000/api/projects", () => {
    return HttpResponse.json({
      items: [
        {
          id: "proj-001",
          title: "Dijkstra 最短路径",
          status: "done",
          topic: "图算法",
          difficulty: "intermediate",
          frame_count: 14,
          updated_at: "2024-01-15T10:00:00Z",
        },
        {
          id: "proj-002",
          title: "冒泡排序可视化",
          status: "draft",
          topic: "排序算法",
          difficulty: "beginner",
          frame_count: 0,
          updated_at: "2024-01-14T08:00:00Z",
        },
      ],
      total: 2,
      page: 1,
      page_size: 20,
    });
  }),

  http.get("http://localhost:8000/api/projects/:id", ({ params }) => {
    return HttpResponse.json({
      id: params.id,
      title: "Dijkstra 最短路径",
      status: "done",
      audience: "undergraduate_cs",
      difficulty: "intermediate",
      teaching_plan: {
        objectives: ["理解最短路径", "掌握 Dijkstra 算法"],
        outline: [{ step: 1, title: "概述", key_points: ["图", "距离"], estimated_frames: 3 }],
      },
      knowledge_graph: null,
      dsl: { frames: [] },
      quality_report: null,
      frame_count: 14,
      created_at: "2024-01-15T10:00:00Z",
      updated_at: "2024-01-15T10:00:00Z",
    });
  }),

  http.post("http://localhost:8000/api/projects", async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json(
      {
        id: "new-proj-001",
        title: body.title,
        status: "draft",
        created_at: new Date().toISOString(),
      },
      { status: 201 },
    );
  }),

  // ── Module generation metadata ─────────────────────────
  // ProjectWorkspace loads this list even for the client-side `_new`
  // placeholder. Keep the browser tests independent from any local API
  // process by returning the same public catalog as the production fallback.
  http.get("http://localhost:8000/api/projects/:id/generate/modules", () => {
    return HttpResponse.json({
      modules: [
        { module_id: "mindmap", display_name: "思维导图", description: "知识概念导图", icon: "mindmap", category: "visual", priority: 1, estimated_seconds: 15 },
        { module_id: "cards", display_name: "知识卡片", description: "概念知识卡片", icon: "cards", category: "visual", priority: 2, estimated_seconds: 20 },
        { module_id: "interactive_demo", display_name: "交互推演", description: "知识互动体验", icon: "play", category: "interactive", priority: 3, estimated_seconds: 40 },
        { module_id: "quiz", display_name: "小练习", description: "自动生成练习题", icon: "quiz", category: "interactive", priority: 4, estimated_seconds: 25 },
        { module_id: "comparison", display_name: "对比分析", description: "按当前主题生成多维度对比", icon: "comparison", category: "visual", priority: 5, estimated_seconds: 30 },
        { module_id: "video", display_name: "教学视频", description: "生成教学视频", icon: "video", category: "export", priority: 6, estimated_seconds: 120 },
        { module_id: "misconception", display_name: "常见误区", description: "识别并澄清常见误解", icon: "misconception", category: "visual", priority: 7, estimated_seconds: 30 },
        { module_id: "pathway", display_name: "学习路径", description: "生成循序渐进的学习路径", icon: "pathway", category: "visual", priority: 8, estimated_seconds: 30 },
        { module_id: "sandbox", display_name: "代码沙箱", description: "提供可运行的代码实验", icon: "sandbox", category: "interactive", priority: 9, estimated_seconds: 45 },
      ],
    });
  }),

  http.delete("http://localhost:8000/api/projects/:id", () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // ── Materials ─────────────────────────────────────────────
  http.get("http://localhost:8000/api/materials", () => {
    return HttpResponse.json({ items: [] });
  }),

  // ── Generate ──────────────────────────────────────────────
  http.post("http://localhost:8000/api/projects/:id/generate", () => {
    return HttpResponse.json(
      {
        stream_url: "/api/projects/test/generate/stream",
        message: "Generation started",
      },
      { status: 202 },
    );
  }),

  // ── Knowledge ─────────────────────────────────────────────
  http.post("http://localhost:8000/api/knowledge/search", () => {
    return HttpResponse.json({
      items: [
        {
          id: "k1",
          title: "Dijkstra 算法",
          subject: "algorithms",
          difficulty: "intermediate",
          concepts: ["最短路径", "贪心", "松弛"],
          preview: "Dijkstra 算法用于计算图中单源最短路径...",
        },
      ],
      total: 1,
    });
  }),
];

// ============================================================================
// Server
// ============================================================================

export const server = setupServer(...handlers);
