/**
 * 教学计划确认页 — SSE 流式生成进度 + 教学计划展示。
 *
 * 对接: POST /api/projects/{id}/generate + SSE stream
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Sparkles,
  RefreshCw,
  Play,
  Pencil,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  startGeneration,
  streamGeneration,
  getProject,
  type ProjectDetailResponse,
  type SSEProgressEvent,
  ApiError,
  NetworkError,
} from "@/services";

// ============================================================================
// 类型
// ============================================================================

type Phase = "idle" | "connecting" | "planning" | "generating" | "validating" | "done" | "error";

// ============================================================================
// 组件
// ============================================================================

export function PlanConfirm() {
  const { projectId } = useParams<{ projectId: string }>();
  const [phase, setPhase] = useState<Phase>("idle");
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [teachingPlan, setTeachingPlan] = useState<Record<string, unknown> | null>(null);
  const [qualityReport, setQualityReport] = useState<Record<string, unknown> | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [project, setProject] = useState<ProjectDetailResponse | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const startedRef = useRef(false);

  // 加载项目信息
  useEffect(() => {
    if (!projectId) return;
    getProject(projectId).then(setProject).catch(() => {});
  }, [projectId]);

  // 启动生成
  const handleStart = useCallback(async () => {
    if (!projectId || startedRef.current) return;
    startedRef.current = true;
    setPhase("connecting");
    setErrorMsg(null);

    try {
      // 1. 调用启动生成接口
      await startGeneration(projectId, "full");

      // 2. 建立 SSE 连接
      abortRef.current = new AbortController();
      streamGeneration(projectId, {
        signal: abortRef.current.signal,
        onProgress: (event: SSEProgressEvent) => {
          setProgress(event.pct);
          setMessage(event.message);
          if (event.phase === "planning") {
            setPhase("planning");
            if (event.teaching_plan) {
              setTeachingPlan(event.teaching_plan as Record<string, unknown>);
            }
          } else if (event.phase === "generating" || event.phase === "knowledge" || event.phase === "coder") {
            setPhase("generating");
          } else if (event.phase === "validating" || event.phase === "quality") {
            setPhase("validating");
          }
        },
        onDone: (event) => {
          setPhase("done");
          setProgress(100);
          setMessage("生成完成");
          if (event.quality_report) {
            setQualityReport(event.quality_report as Record<string, unknown>);
          }
          // 刷新项目详情
          if (projectId) {
            getProject(projectId).then(setProject).catch(() => {});
          }
        },
        onError: (event) => {
          setPhase("error");
          setErrorMsg(event.message || "生成过程中发生错误");
        },
      });
    } catch (err) {
      setPhase("error");
      if (err instanceof ApiError) {
        setErrorMsg(err.message);
      } else if (err instanceof NetworkError) {
        setErrorMsg("无法连接到服务器，请检查后端是否已启动");
      } else {
        setErrorMsg("生成启动失败");
      }
    }
  }, [projectId]);

  // 取消生成
  const handleCancel = () => {
    abortRef.current?.abort();
    setPhase("idle");
    startedRef.current = false;
  };

  // 组件卸载时取消
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  return (
    <div className="mx-auto max-w-3xl p-6">
      {/* 面包屑 */}
      <Link
        to="/app"
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700"
      >
        <ArrowLeft size={17} />
        返回工作台
      </Link>

      <h1 className="text-2xl font-bold text-slate-900 mb-2">教学计划确认</h1>
      <p className="text-sm text-slate-500 mb-8">
        {project?.title ?? "加载中..."}
      </p>

      {/* 未开始 */}
      {phase === "idle" && (
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center">
          <Sparkles size={48} className="mx-auto mb-4 text-indigo-400" />
          <h2 className="text-lg font-semibold text-slate-900 mb-2">准备生成教学计划</h2>
          <p className="text-sm text-slate-500 mb-6">
            AI 将分析你的知识点，制定教学目标、大纲和推演策略
          </p>
          <Button onClick={handleStart} className="gap-2">
            <Sparkles size={18} />
            开始生成
          </Button>
        </div>
      )}

      {/* 生成中 */}
      {(phase === "connecting" || phase === "planning" || phase === "generating" || phase === "validating") && (
        <div className="space-y-6">
          <div className="rounded-xl border border-indigo-200 bg-white p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="flex size-10 items-center justify-center rounded-full bg-indigo-50">
                <svg className="size-5 text-indigo-500 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              </div>
              <div>
                <p className="font-medium text-slate-900">
                  {phase === "connecting" && "正在连接..."}
                  {phase === "planning" && "正在制定教学计划"}
                  {phase === "generating" && "正在生成推演帧"}
                  {phase === "validating" && "正在校验质量"}
                </p>
                <p className="text-sm text-slate-500">{message}</p>
              </div>
            </div>
            <Progress value={progress} className="h-2" />
            <p className="mt-2 text-right text-xs text-slate-400">{progress}%</p>
          </div>

          {/* 教学计划预览 */}
          {teachingPlan && (
            <div className="rounded-xl border border-slate-200 bg-white p-6">
              <h3 className="font-semibold text-slate-900 mb-4">教学计划</h3>
              <pre className="max-h-64 overflow-auto rounded-lg bg-slate-50 p-4 text-xs text-slate-700">
                {JSON.stringify(teachingPlan, null, 2)}
              </pre>
            </div>
          )}

          <div className="text-center">
            <Button variant="outline" size="sm" onClick={handleCancel} className="gap-2">
              <XCircle size={16} />
              取消生成
            </Button>
          </div>
        </div>
      )}

      {/* 生成完成 */}
      {phase === "done" && (
        <div className="space-y-6">
          <div className="rounded-xl border border-green-200 bg-green-50 p-6 text-center">
            <CheckCircle2 size={48} className="mx-auto mb-4 text-green-500" />
            <h2 className="text-lg font-semibold text-green-800 mb-2">生成完成</h2>
            <p className="text-sm text-green-600 mb-6">
              教学计划和推演帧已生成完毕，可以进入播放器查看
            </p>
            <div className="flex items-center justify-center gap-3">
              <Link to={`/app/project/${projectId}/play`}>
                <Button className="gap-2">
                  <Play size={18} />
                  进入播放器
                </Button>
              </Link>
              <Link to={`/app/project/${projectId}/edit`}>
                <Button variant="outline" className="gap-2">
                  <Pencil size={18} />
                  进入编辑器
                </Button>
              </Link>
            </div>
          </div>

          {/* 质量报告 */}
          {qualityReport && (
            <div className="rounded-xl border border-slate-200 bg-white p-6">
              <h3 className="font-semibold text-slate-900 mb-4">质量报告</h3>
              <pre className="max-h-64 overflow-auto rounded-lg bg-slate-50 p-4 text-xs text-slate-700">
                {JSON.stringify(qualityReport, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* 错误 */}
      {phase === "error" && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
          <AlertTriangle size={48} className="mx-auto mb-4 text-red-400" />
          <h2 className="text-lg font-semibold text-red-800 mb-2">生成失败</h2>
          <p className="text-sm text-red-600 mb-6">{errorMsg}</p>
          <div className="flex items-center justify-center gap-3">
            <Button
              variant="outline"
              onClick={() => { setPhase("idle"); startedRef.current = false; }}
              className="gap-2"
            >
              <RefreshCw size={16} />
              重试
            </Button>
            <Link to="/app">
              <Button variant="ghost">返回工作台</Button>
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}