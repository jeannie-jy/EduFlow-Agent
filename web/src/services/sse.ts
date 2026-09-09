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

/** 模块生成开始事件 */
export interface SSEModuleStartEvent {
  phase: "module_start";
  module_id: string;
  display_name: string;
  message: string;
  pct: number;
}

/** 模块生成完成事件 */
export interface SSEModuleDoneEvent {
  phase: "module_done";
  module_id: string;
  display_name: string;
  output: unknown;
  issues?: unknown[] | null;
  pct: number;
}

/** 模块生成错误事件（非阻塞） */
export interface SSEModuleErrorEvent {
  phase: "module_error";
  module_id: string;
  display_name?: string;
  error: string;
  pct: number;
}

export type SSEConnectionState = "connecting" | "open" | "closed" | "error";

export interface SSEConnection {
  close(): void;
  readonly state: SSEConnectionState;
  readonly lastEventId: string | null;
}

export interface SSEOptions {
  onProgress?: (event: SSEProgressEvent) => void;
  onWaitingApproval?: (event: SSEWaitingApprovalEvent) => void;
  onDone?: (event: SSEDoneEvent) => void;
  onError?: (event: SSEErrorEvent) => void;
  onModuleStart?: (event: SSEModuleStartEvent) => void;
  onModuleDone?: (event: SSEModuleDoneEvent) => void;
  onModuleError?: (event: SSEModuleErrorEvent) => void;
  signal?: AbortSignal;
  /** 自动重连间隔（毫秒），默认 3000，设为 0 禁用 */
  reconnectMs?: number;
  /** 最大重连次数，默认 3 */
  maxReconnects?: number;
  /** 可选初始恢复游标；自动重连会继续使用最后收到的事件 ID。 */
  lastEventId?: string;
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
    onModuleStart,
    onModuleDone,
    onModuleError,
    signal,
    reconnectMs = 3000,
    maxReconnects = 3,
    lastEventId: initialLastEventId,
  } = options;

  let state: SSEConnectionState = "connecting";
  let reconnectCount = 0;
  let reader: ReadableStreamDefaultReader<Uint8Array> | null = null;
  let abortController: AbortController | null = null;
  let lastEventId: string | null = initialLastEventId ?? null;
  let terminalReceived = false;

  async function connect() {
    abortController = new AbortController();

    // 合并外部 signal
    if (signal) {
      signal.addEventListener("abort", () => abortController?.abort(), { once: true });
    }

    try {
      const headers: Record<string, string> = { Accept: "text/event-stream" };
      if (lastEventId) headers["Last-Event-ID"] = lastEventId;
      const res = await fetch(url, {
        credentials: "include",
        headers,
        signal: abortController.signal,
      });

      if (!res.ok) {
        throw new Error(`SSE 连接失败: HTTP ${res.status}`);
      }

      if (!res.body) {
        throw new Error("SSE 响应没有 body");
      }

      state = "open";
      reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          processBlock(block);
        }
      }
      buffer += decoder.decode().replace(/\r\n/g, "\n");
      if (buffer.trim()) processBlock(buffer);
      if (!terminalReceived && (state as SSEConnectionState) !== "closed") {
        throw new Error("SSE 流在终态事件前中断");
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
          void connect();
          return;
        }
      }

      // 重连次数耗尽或禁用重连 → 通知上层
      const errMsg = err instanceof Error ? err.message : "SSE 连接失败";
      console.error("SSE 连接失败（已放弃）:", errMsg);
      onError?.({ phase: "error", message: errMsg });
    }
  }

  function processBlock(block: string) {
    let eventName = "message";
    let eventId: string | null = null;
    const dataLines: string[] = [];
    for (const line of block.split("\n")) {
      if (!line || line.startsWith(":")) continue;
      const separator = line.indexOf(":");
      const field = separator < 0 ? line : line.slice(0, separator);
      let value = separator < 0 ? "" : line.slice(separator + 1);
      if (value.startsWith(" ")) value = value.slice(1);
      if (field === "event") eventName = value;
      else if (field === "id") eventId = value;
      else if (field === "data") dataLines.push(value);
    }
    if (!dataLines.length) return;
    if (eventId && lastEventId) {
      const incoming = Number(eventId);
      const previous = Number(lastEventId);
      if (
        eventId === lastEventId ||
        (Number.isSafeInteger(incoming) && Number.isSafeInteger(previous) && incoming <= previous)
      ) return;
    }
    try {
      const data = JSON.parse(dataLines.join("\n"));
      if (eventId) lastEventId = eventId;
      dispatch(eventName, data);
    } catch {
      // Ignore malformed application payloads while keeping the stream alive.
    }
  }

  function dispatch(eventName: string, data: Record<string, unknown>) {
    const phase = (data.phase as string) || eventName;
    if (terminalReceived) return;
    if (eventName === "done" || phase === "done") {
      terminalReceived = true;
      state = "closed";
      onDone?.(data as unknown as SSEDoneEvent);
    } else if (eventName === "error" || phase === "error") {
      terminalReceived = true;
      state = "closed";
      onError?.(data as unknown as SSEErrorEvent);
    } else if (eventName === "waiting_approval" || phase === "waiting_approval") {
      terminalReceived = true;
      state = "closed";
      onWaitingApproval?.(data as unknown as SSEWaitingApprovalEvent);
    } else if (phase === "module_start") {
      onModuleStart?.(data as unknown as SSEModuleStartEvent);
    } else if (phase === "module_done") {
      onModuleDone?.(data as unknown as SSEModuleDoneEvent);
    } else if (phase === "module_error") {
      onModuleError?.(data as unknown as SSEModuleErrorEvent);
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
    get lastEventId() {
      return lastEventId;
    },
  };
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
