/**
 * SSE 连接管理器 — 单元测试
 *
 * 测试 SSE 事件解析、状态管理、重连、取消。
 */

import { describe, expect, it, vi, afterEach } from "vitest";

// ============================================================================
// 辅助：创建可控制的 SSE 模拟流
// ============================================================================

function createSSEStream(...events: string[]) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const event of events) {
        controller.enqueue(encoder.encode(event));
      }
      controller.close();
    },
  });

  return vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    body: stream,
  });
}

function sseEvent(event: string, data: Record<string, unknown>): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

// ============================================================================
// connectSSE
// ============================================================================

describe("connectSSE", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("receives progress events", async () => {
    const progressData = {
      phase: "planner",
      message: "正在执行 planner...",
      pct: 10,
    };

    const stream = createSSEStream(
      sseEvent("progress", progressData),
      sseEvent("done", { phase: "done", pct: 100 }),
    );
    vi.stubGlobal("fetch", stream);

    const { connectSSE } = await import("@/services/sse");

    const onProgress = vi.fn();
    const onDone = vi.fn();

    const conn = connectSSE("http://localhost:8000/api/projects/1/generate/stream", {
      onProgress,
      onDone,
      reconnectMs: 0,  // 禁用重连
    });

    // 等待流消费完成
    await vi.waitFor(() => expect(onProgress).toHaveBeenCalled(), { timeout: 2000 });

    expect(onProgress).toHaveBeenCalledWith(
      expect.objectContaining({ phase: "planner", pct: 10 }),
    );
    expect(onDone).toHaveBeenCalled();

    conn.close();
  });

  it("receives done event", async () => {
    const doneData = {
      phase: "done",
      pct: 100,
      quality_report: { overall_score: 0.85 },
    };

    const stream = createSSEStream(sseEvent("done", doneData));
    vi.stubGlobal("fetch", stream);

    const { connectSSE } = await import("@/services/sse");

    const onDone = vi.fn();
    const conn = connectSSE("http://localhost:8000/api/projects/1/generate/stream", {
      onDone,
      reconnectMs: 0,
    });

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled(), { timeout: 2000 });
    expect(onDone).toHaveBeenCalledWith(
      expect.objectContaining({ phase: "done", pct: 100 }),
    );

    conn.close();
  });

  it("receives error event", async () => {
    const errorData = {
      phase: "error",
      message: "生成流程内部错误",
      error_code: "GENERATION_FAILED",
    };

    const stream = createSSEStream(sseEvent("error", errorData));
    vi.stubGlobal("fetch", stream);

    const { connectSSE } = await import("@/services/sse");

    const onError = vi.fn();
    const conn = connectSSE("http://localhost:8000/api/projects/1/generate/stream", {
      onError,
      reconnectMs: 0,
    });

    await vi.waitFor(() => expect(onError).toHaveBeenCalled(), { timeout: 2000 });
    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ phase: "error", error_code: "GENERATION_FAILED" }),
    );

    conn.close();
  });

  it("handles multiple events in sequence", async () => {
    const events = [
      sseEvent("progress", { phase: "planner", message: "planning", pct: 10 }),
      sseEvent("progress", { phase: "knowledge", message: "knowledge", pct: 25 }),
      sseEvent("progress", { phase: "coder", message: "generating", pct: 50 }),
      sseEvent("progress", { phase: "quality", message: "validating", pct: 90 }),
      sseEvent("done", { phase: "done", pct: 100 }),
    ];

    const stream = createSSEStream(...events);
    vi.stubGlobal("fetch", stream);

    const { connectSSE } = await import("@/services/sse");

    const onProgress = vi.fn();
    const onDone = vi.fn();
    const conn = connectSSE("http://localhost:8000/api/projects/1/generate/stream", {
      onProgress,
      onDone,
      reconnectMs: 0,
    });

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled(), { timeout: 2000 });

    // 应收到 4 个进度事件 + 1 个 done 事件
    expect(onProgress).toHaveBeenCalledTimes(4);
    expect(onDone).toHaveBeenCalledTimes(1);

    conn.close();
  });

  it("exposes connection state", async () => {
    const stream = createSSEStream(
      sseEvent("done", { phase: "done", pct: 100 }),
    );
    vi.stubGlobal("fetch", stream);

    const { connectSSE } = await import("@/services/sse");

    const onDone = vi.fn();
    const conn = connectSSE("http://localhost:8000/api/projects/1/generate/stream", {
      onDone,
      reconnectMs: 0,
    });

    expect(conn.state).toBe("connecting");

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled(), { timeout: 2000 });

    conn.close();
    expect(conn.state).toBe("closed");
  });

  it("calls close to abort connection", async () => {
    // 创建一个永不关闭的流
    const stream = new ReadableStream({
      start(_controller) {
        // 不 push 任何数据，也不关闭
      },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body: stream,
      }),
    );

    const { connectSSE } = await import("@/services/sse");

    const conn = connectSSE("http://localhost:8000/api/projects/1/generate/stream", {
      reconnectMs: 0,
    });

    // 立即关闭
    conn.close();
    expect(conn.state).toBe("closed");
  });

  it("ignores invalid JSON in data lines", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        // 有效事件
        controller.enqueue(encoder.encode(
          sseEvent("progress", { phase: "test", pct: 50 }),
        ));
        // 无效 JSON
        controller.enqueue(encoder.encode("data: not valid json\n\n"));
        // 有效事件
        controller.enqueue(encoder.encode(
          sseEvent("done", { phase: "done", pct: 100 }),
        ));
        controller.close();
      },
    });

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: stream,
    }));

    const { connectSSE } = await import("@/services/sse");
    const onProgress = vi.fn();
    const onDone = vi.fn();

    const conn = connectSSE("http://localhost:8000/api/projects/1/generate/stream", {
      onProgress,
      onDone,
      reconnectMs: 0,
    });

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled(), { timeout: 2000 });

    // 无效 JSON 行不应导致崩溃
    expect(onProgress).toHaveBeenCalled();
    expect(onDone).toHaveBeenCalled();

    conn.close();
  });
});