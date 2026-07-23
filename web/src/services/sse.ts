/**
 * SSE（Server-Sent Events）连接管理器。
 *
 * 基于 fetch + ReadableStream 实现，支持：
 * - 进度回调（progress / done / error 事件）
 * - 自动重连
 * - 取消（AbortSignal）
 * - 连接状态追踪
 */

// ============================================================================
// 类型
// ============================================================================

export interface SSEProgressEvent {
  phase: string;
  message: string;
  pct: number;
  teaching_plan?: unknown;
  /** 等待审批时，后端会推送此事件 */
  [key: string]: unknown;
}

/** 等待审批事件（Human-in-the-Loop） */
export interface SSEWaitingApprovalEvent {
  phase: "waiting_approval";
  message: string;
  pct: number;
  teaching_plan: unknown;
}

export interface SSEDoneEvent {
  phase: "done";
  pct: number;
  quality_report?: unknown;
  [key: string]: unknown;
}

export interface SSEErrorEvent {
  phase: "error";
  message: string;
  details?: unknown;
}

export type SSEConnectionState = "connecting" | "open" | "closed" | "error";

export interface SSEConnection {
  close(): void;
  readonly state: SSEConnectionState;
}

export interface SSEOptions {
  onProgress?: (event: SSEProgressEvent) => void;
  onWaitingApproval?: (event: SSEWaitingApprovalEvent) => void;
  onDone?: (event: SSEDoneEvent) => void;
  onError?: (event: SSEErrorEvent) => void;
  signal?: AbortSignal;
  /** 自动重连间隔（毫秒），默认 3000，设为 0 禁用 */
  reconnectMs?: number;
  /** 最大重连次数，默认 3 */
  maxReconnects?: number;
}

// ============================================================================
// 连接
// ============================================================================

export function connectSSE(url: string, options: SSEOptions = {}): SSEConnection {
  const {
    onProgress,
    onWaitingApproval,
    onDone,
    onError,
    signal,
    reconnectMs = 3000,
    maxReconnects = 3,
  } = options;

  let state: SSEConnectionState = "connecting";
  let reconnectCount = 0;
  let reader: ReadableStreamDefaultReader<Uint8Array> | null = null;
  let abortController: AbortController | null = null;

  async function connect() {
    abortController = new AbortController();

    // 合并外部 signal
    if (signal) {
      signal.addEventListener("abort", () => abortController?.abort(), { once: true });
    }

    try {
      const res = await fetch(url, {
        headers: { Accept: "text/event-stream" },
        signal: abortController.signal,
      });

      if (!res.ok) {
        throw new Error(`SSE 连接失败: HTTP ${res.status}`);
      }

      if (!res.body) {
        throw new Error("SSE 响应没有 body");
      }

      state = "open";
      reconnectCount = 0;
      reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              dispatch(data);
            } catch {
              // 忽略解析失败的行
            }
          }
        }
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        state = "closed";
        return;
      }

      state = "error";

      // 自动重连
      if (reconnectMs > 0 && reconnectCount < maxReconnects) {
        reconnectCount++;
        console.log(`SSE 重连中... (${reconnectCount}/${maxReconnects})`);
        await delay(reconnectMs);
        if ((state as SSEConnectionState) !== "closed") {
          state = "connecting";
          connect();
          return;
        }
      }

      // 重连次数耗尽或禁用重连 → 通知上层
      const errMsg = err instanceof Error ? err.message : "SSE 连接失败";
      console.error("SSE 连接失败（已放弃）:", errMsg);
      onError?.({ phase: "error", message: errMsg });
    }
  }

  function dispatch(data: Record<string, unknown>) {
    const phase = data.phase as string;
    if (phase === "done") {
      onDone?.(data as unknown as SSEDoneEvent);
    } else if (phase === "error") {
      onError?.(data as unknown as SSEErrorEvent);
    } else if (phase === "waiting_approval") {
      onWaitingApproval?.(data as unknown as SSEWaitingApprovalEvent);
    } else {
      onProgress?.(data as SSEProgressEvent);
    }
  }

  function close() {
    state = "closed";
    abortController?.abort();
    reader?.cancel().catch(() => {});
  }

  // 启动连接
  connect();

  return {
    close,
    get state() {
      return state;
    },
  };
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}