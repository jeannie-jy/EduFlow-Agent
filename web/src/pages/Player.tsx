/**
 * 交互式播放器 — 从后端获取 DSL 并渲染推演。
 *
 * 对接: GET /api/projects/{id}, GET /api/projects/{id}/frames
 *       GET /api/projects/{id}/parameters, POST /recompute
 *
 * 降级: 后端不可用时使用本地 Dijkstra 演示数据
 */

import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { WorkbenchPage } from "@/components/workbench/WorkbenchPage";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { AlertCircle, RefreshCw, WifiOff } from "lucide-react";
import {
  getProject,
  listFrames,
  listParameters,
  type ProjectDetailResponse,
  NetworkError,
} from "@/services";

type LoadState = "loading" | "loaded" | "fallback" | "error";

export function Player() {
  const { projectId } = useParams<{ projectId: string }>();
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [project, setProject] = useState<ProjectDetailResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const fetchData = useCallback(async () => {
    if (!projectId) return;
    setLoadState("loading");

    try {
      const [projectData, framesData] = await Promise.all([
        getProject(projectId),
        listFrames(projectId),
        listParameters(projectId),
      ]);
      setProject(projectData);

      if (projectData.dsl || (framesData.frames && framesData.frames.length > 0)) {
        setLoadState("loaded");
      } else {
        setLoadState("fallback");
      }
    } catch (err) {
      if (err instanceof NetworkError) {
        setLoadState("fallback");
        setErrorMsg("后端未连接，使用本地演示数据");
      } else {
        setLoadState("error");
        setErrorMsg(err instanceof Error ? err.message : "加载失败");
      }
    }
  }, [projectId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loadState === "loading") {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="w-full max-w-2xl space-y-4">
          <Skeleton className="h-8 w-1/3" />
          <Skeleton className="h-64 w-full rounded-xl" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      </div>
    );
  }

  if (loadState === "error") {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6">
        <AlertCircle size={48} className="text-red-300 mb-4" />
        <p className="text-red-600 mb-2">{errorMsg}</p>
        <Button variant="outline" size="sm" onClick={fetchData} className="gap-2">
          <RefreshCw size={16} /> 重试
        </Button>
      </div>
    );
  }

  // 降级模式：后端有数据但未生成 DSL，或后端不可用
  if (loadState === "fallback") {
    return (
      <div className="relative h-full">
        <div className="absolute top-3 left-1/2 z-10 -translate-x-1/2">
          <span className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs text-amber-700">
            <WifiOff size={14} />
            本地演示模式 — {errorMsg || "项目尚未生成推演内容"}
          </span>
        </div>
        <WorkbenchPage />
      </div>
    );
  }

  // 正常模式：后端有完整 DSL → 渲染
  return (
    <div className="relative h-full">
      <div className="absolute top-3 left-1/2 z-10 -translate-x-1/2">
        <span className="inline-flex items-center gap-2 rounded-full border border-green-200 bg-green-50 px-3 py-1 text-xs text-green-700">
          <RefreshCw size={14} />
          已加载项目: {project?.title ?? projectId}
        </span>
      </div>
      <WorkbenchPage />
    </div>
  );
}