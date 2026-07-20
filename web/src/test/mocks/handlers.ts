/**
 * MSW 测试服务器 — 用于组件测试中的 API mock。
 */

import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

// ============================================================================
// Handlers
// ============================================================================

export const handlers = [
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

  http.delete("http://localhost:8000/api/projects/:id", () => {
    return new HttpResponse(null, { status: 204 });
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