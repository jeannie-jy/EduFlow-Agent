/**
 * API 客户端 — 单元测试
 *
 * 测试 fetch 封装层：请求构建、错误处理、超时、上传。
 */

import { describe, expect, it, vi, afterEach } from "vitest";
import { api, ApiError, NetworkError, TimeoutError } from "@/services/api-client";

// ============================================================================
// 辅助函数
// ============================================================================

function mockFetchResponse(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  });
}

function mockFetchNetworkError(message: string) {
  return vi.fn().mockRejectedValue(new Error(message));
}

// ============================================================================
// ApiError
// ============================================================================

describe("ApiError", () => {
  it("constructs with status and body", () => {
    const err = new ApiError(404, {
      error: { code: "NOT_FOUND", message: "Project not found", details: { id: "1" } },
    });

    expect(err.name).toBe("ApiError");
    expect(err.status).toBe(404);
    expect(err.code).toBe("NOT_FOUND");
    expect(err.message).toBe("Project not found");
    expect(err.details).toEqual({ id: "1" });
  });

  it("is an instance of Error", () => {
    const err = new ApiError(500, {
      error: { code: "SERVER_ERROR", message: "Internal error" },
    });
    expect(err).toBeInstanceOf(Error);
  });
});

describe("NetworkError", () => {
  it("constructs with message", () => {
    const err = new NetworkError("网络请求失败");
    expect(err.name).toBe("NetworkError");
    expect(err.message).toBe("网络请求失败");
  });
});

describe("TimeoutError", () => {
  it("constructs with timeout duration", () => {
    const err = new TimeoutError(30000);
    expect(err.name).toBe("TimeoutError");
    expect(err.message).toContain("30000");
  });
});

// ============================================================================
// GET 请求
// ============================================================================

describe("api.get", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends GET request and returns parsed JSON", async () => {
    vi.stubGlobal("fetch", mockFetchResponse(200, { data: "test" }));

    const result = await api.get("/projects");
    expect(result).toEqual({ data: "test" });
  });

  it("appends query params to URL", async () => {
    const fetchMock = mockFetchResponse(200, { items: [] });
    vi.stubGlobal("fetch", fetchMock);

    await api.get("/projects", { page: "1", page_size: "10" });

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("page=1");
    expect(url).toContain("page_size=10");
  });

  it("throws ApiError on 404", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchResponse(404, {
        error: { code: "NOT_FOUND", message: "Resource not found" },
      }),
    );

    await expect(api.get("/projects/nonexistent")).rejects.toThrow(ApiError);
  });

  it("throws ApiError on 500", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchResponse(500, {
        error: { code: "SERVER_ERROR", message: "Internal server error" },
      }),
    );

    await expect(api.get("/projects")).rejects.toThrow(ApiError);
  });

  it("throws ApiError even when response is not valid JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        json: () => Promise.reject(new Error("Invalid JSON")),
        text: () => Promise.resolve("Bad Gateway"),
      }),
    );

    try {
      await api.get("/projects");
      expect.fail("Expected error to be thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).status).toBe(502);
    }
  });

  it("throws NetworkError on fetch failure", async () => {
    vi.stubGlobal("fetch", mockFetchNetworkError("Failed to fetch"));

    await expect(api.get("/projects")).rejects.toThrow(NetworkError);
  });
});

// ============================================================================
// POST 请求
// ============================================================================

describe("api.post", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends POST with JSON body", async () => {
    const fetchMock = mockFetchResponse(201, { id: "1", status: "draft" });
    vi.stubGlobal("fetch", fetchMock);

    const result = await api.post("/projects", {
      title: "测试项目",
      difficulty: "intermediate",
    });

    expect(result).toEqual({ id: "1", status: "draft" });

    const callArgs = fetchMock.mock.calls[0];
    const options = callArgs[1] as RequestInit;
    expect(options.method).toBe("POST");
    expect(options.body).toBe(JSON.stringify({ title: "测试项目", difficulty: "intermediate" }));
  });

  it("handles 201 created response", async () => {
    vi.stubGlobal("fetch", mockFetchResponse(201, { id: "uuid", created_at: "2024-01-01" }));

    const result = await api.post<{ id: string; created_at: string }>(
      "/projects",
      { title: "test" },
    );
    expect(result.id).toBe("uuid");
  });

  it("handles 204 no content", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 204,
        json: () => Promise.reject(new Error("No body")),
      }),
    );

    const result = await api.delete("/projects/123");
    expect(result).toBeUndefined();
  });
});

// ============================================================================
// PUT 请求
// ============================================================================

describe("api.put", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends PUT request with body", async () => {
    const fetchMock = mockFetchResponse(200, { updated_at: "2024-01-01" });
    vi.stubGlobal("fetch", fetchMock);

    await api.put("/projects/1/frames/f_001", { title: "新标题" });

    const options = fetchMock.mock.calls[0][1] as RequestInit;
    expect(options.method).toBe("PUT");
  });
});

// ============================================================================
// DELETE 请求
// ============================================================================

describe("api.delete", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends DELETE request", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: () => Promise.reject(new Error("No body")),
    });
    vi.stubGlobal("fetch", fetchMock);

    await api.delete("/projects/123");

    const options = fetchMock.mock.calls[0][1] as RequestInit;
    expect(options.method).toBe("DELETE");
  });
});

// ============================================================================
// 超时
// ============================================================================

describe("api timeout", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("throws TimeoutError when request exceeds timeout", async () => {
    // 创建一个会检查 AbortSignal 的 mock fetch
    const fetchMock = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      return new Promise<Response>((_resolve, reject) => {
        // 监听 abort 信号
        if (init?.signal) {
          if (init.signal.aborted) {
            const err = new DOMException("The operation was aborted", "AbortError");
            reject(err);
            return;
          }
          init.signal.addEventListener("abort", () => {
            const err = new DOMException("The operation was aborted", "AbortError");
            reject(err);
          });
        }
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const promise = api.get("/projects", undefined, 1);  // 1ms 超时

    await expect(promise).rejects.toThrow(TimeoutError);
  }, 10000);
});

// ============================================================================
// upload
// ============================================================================

describe("api.upload", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uploads file as FormData", async () => {
    const fetchMock = mockFetchResponse(201, {
      id: "uuid",
      filename: "test.pdf",
      size_bytes: 1024,
    });
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["test content"], "test.pdf", { type: "application/pdf" });
    const result = await api.upload<{
      id: string;
      filename: string;
      size_bytes: number;
    }>("/materials/upload", file);

    expect(result.filename).toBe("test.pdf");

    const options = fetchMock.mock.calls[0][1] as RequestInit;
    expect(options.body).toBeInstanceOf(FormData);
  });
});

// ============================================================================
// stream
// ============================================================================

describe("api.stream", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns raw response for SSE streaming", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body: new ReadableStream(),
      }),
    );

    const response = await api.stream("/projects/1/generate/stream", { action: "full" });

    expect(response.ok).toBe(true);
    expect(response.body).toBeInstanceOf(ReadableStream);
  });

  it("throws ApiError when stream fails", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchResponse(404, {
        error: { code: "NOT_FOUND", message: "Project not found" },
      }),
    );

    await expect(
      api.stream("/projects/nonexistent/generate/stream"),
    ).rejects.toThrow(ApiError);
  });
});
