/**
 * 生成服务 — 单元测试
 *
 * 测试 startGeneration, streamGeneration, regenerate 的请求构造。
 */

import { describe, expect, it, vi, afterEach } from "vitest";

describe("generate service", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.sessionStorage.clear();
  });

  it("startGeneration sends POST with action=full", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 202,
      json: () => Promise.resolve({
        stream_url: "/api/projects/1/generate/stream",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const { startGeneration } = await import("@/services/generate");
    const result = await startGeneration("abc-123", "full");

    expect(result.stream_url).toContain("generate/stream");

    const options = fetchMock.mock.calls[0][1] as RequestInit;
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body as string)).toEqual({ action: "full" });
  });

  it("startGeneration defaults to 'full' action", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 202,
      json: () => Promise.resolve({ stream_url: "/api/projects/1/generate/stream" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const { startGeneration } = await import("@/services/generate");
    await startGeneration("abc-123");

    const options = fetchMock.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(options.body as string);
    expect(body.action).toBe("full");
  });

  it("regenerate sends POST with scope", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 202,
      json: () => Promise.resolve({ stream_url: "/api/projects/1/generate/stream" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const { regenerate } = await import("@/services/generate");
    await regenerate("abc-123", {
      type: "frame_range",
      frame_ids: ["f_005", "f_006"],
    });

    const options = fetchMock.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(options.body as string);
    expect(body.scope.type).toBe("frame_range");
    expect(body.scope.frame_ids).toEqual(["f_005", "f_006"]);
  });

  it("streamGeneration constructs SSE connection URL", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(
          'event: done\ndata: {"phase":"done","pct":100}\n\n',
        ));
        controller.close();
      },
    });

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: stream,
    });
    vi.stubGlobal("fetch", fetchMock);

    const { streamGeneration } = await import("@/services/generate");

    const onDone = vi.fn();
    const conn = streamGeneration("abc-123", {
      onDone,
      reconnectMs: 0,
    });

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled(), { timeout: 2000 });

    // 验证 URL 包含 project ID
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("abc-123");
    expect(url).toContain("generate/stream");

    conn.close();
  });

  it("regenerates a module batch through the exact persisted stream URL", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(
          'event: done\ndata: {"phase":"done","pct":100}\n\n',
        ));
        controller.close();
      },
    });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 202,
        json: () => Promise.resolve({
          stream_url: "/api/projects/p1/generate/modules/stream?stream_id=persisted-id",
        }),
      })
      .mockResolvedValueOnce({ ok: true, status: 200, body: stream });
    vi.stubGlobal("fetch", fetchMock);
    const { regenerateModules } = await import("@/services/generate");
    const onDone = vi.fn();

    const connection = await regenerateModules("p1", ["quiz", "mindmap"], {
      onDone,
      reconnectMs: 0,
    });
    await vi.waitFor(() => expect(onDone).toHaveBeenCalled());

    expect(JSON.parse(fetchMock.mock.calls[0][1].body as string)).toEqual({
      modules: ["quiz", "mindmap"],
    });
    expect(fetchMock.mock.calls[1][0]).toBe(
      "http://localhost:8000/api/projects/p1/generate/modules/stream?stream_id=persisted-id",
    );
    connection.close();
  });

  it("requests a trace-based cost estimate before module retry", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({
        available: false,
        requested_module_count: 2,
        estimated_cost_usd: null,
        sample_count: 0,
        method: "unavailable",
        hard_limit_cost_usd: 10,
        hard_limit_tokens: 100000,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const { estimateModuleCost } = await import("@/services/generate");

    const result = await estimateModuleCost("p1", ["quiz", "mindmap"]);

    expect(result.available).toBe(false);
    expect(fetchMock.mock.calls[0][0]).toContain(
      "/projects/p1/generate/modules/cost-estimate",
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1].body as string)).toEqual({
      modules: ["quiz", "mindmap"],
    });
  });

  it("resumes a page-refresh stream with its persisted event cursor", async () => {
    const encoder = new TextEncoder();
    const interrupted = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(
          'id: 7\nevent: progress\ndata: {"phase":"coder","pct":60,"message":"coding","event_id":7}\n\n',
        ));
        controller.close();
      },
    });
    const completed = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(
          'id: 8\nevent: done\ndata: {"phase":"done","pct":100,"event_id":8}\n\n',
        ));
        controller.close();
      },
    });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, status: 200, body: interrupted })
      .mockResolvedValueOnce({ ok: true, status: 200, body: completed });
    vi.stubGlobal("fetch", fetchMock);
    const { resumeProjectStream, streamFromUrl } = await import("@/services/generate");
    const onInterrupted = vi.fn();

    streamFromUrl("/api/projects/p1/generate/stream?stream_id=s1", {
      reconnectMs: 0,
      onError: onInterrupted,
    });
    await vi.waitFor(() => expect(onInterrupted).toHaveBeenCalled());

    const saved = window.sessionStorage.getItem("eduflow:active-stream:p1");
    expect(saved).toContain('"lastEventId":"7"');
    const onDone = vi.fn();
    resumeProjectStream("p1", { reconnectMs: 0, onDone });
    await vi.waitFor(() => expect(onDone).toHaveBeenCalled());

    const headers = fetchMock.mock.calls[1][1].headers as Record<string, string>;
    expect(headers["Last-Event-ID"]).toBe("7");
    expect(window.sessionStorage.getItem("eduflow:active-stream:p1")).toBeNull();
  });

  it("discovers a server-ledger stream when local session state is missing", async () => {
    const encoder = new TextEncoder();
    const completed = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(
          'id: 5\nevent: done\ndata: {"phase":"done","pct":100,"event_id":5}\n\n',
        ));
        controller.close();
      },
    });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          stream_url: "/api/projects/p1/generate/stream?stream_id=s1",
          last_event_id: 4,
        }),
      })
      .mockResolvedValueOnce({ ok: true, status: 200, body: completed });
    vi.stubGlobal("fetch", fetchMock);
    const { discoverProjectStream } = await import("@/services/generate");
    const onDone = vi.fn();

    const connection = await discoverProjectStream("p1", { reconnectMs: 0, onDone });
    await vi.waitFor(() => expect(onDone).toHaveBeenCalled());

    expect(fetchMock.mock.calls[0][0]).toContain("generate/active-stream");
    const headers = fetchMock.mock.calls[1][1].headers as Record<string, string>;
    expect(headers["Last-Event-ID"]).toBe("4");
    connection?.close();
  });
});
