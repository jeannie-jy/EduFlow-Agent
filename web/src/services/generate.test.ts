/**
 * 生成服务 — 单元测试
 *
 * 测试 startGeneration, streamGeneration, regenerate 的请求构造。
 */

import { describe, expect, it, vi, afterEach } from "vitest";

describe("generate service", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
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
      locked_frame_ids: ["f_001"],
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
});