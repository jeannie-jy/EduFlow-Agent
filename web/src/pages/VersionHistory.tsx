/**
 * 版本历史 — 版本列表 + 对比 + 恢复。
 *
 * 对接: GET /api/projects/{id}/versions, POST /versions/{vid}/restore
 */

import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Label } from "@/components/ui/label";
import {
  ArrowLeft,
  RefreshCw,
  RotateCcw,
  AlertCircle,
  CheckCircle2,
  GitCompare,
  X,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  listVersions,
  getVersion,
  restoreVersion,
  type VersionItem,
  NetworkError,
} from "@/services";

export function VersionHistory() {
  const { projectId } = useParams<{ projectId: string }>();
  const [versions, setVersions] = useState<VersionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [restoring, setRestoring] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  // Diff 状态
  const [diffMode, setDiffMode] = useState(false);
  const [leftVersion, setLeftVersion] = useState<VersionItem | null>(null);
  const [rightVersion, setRightVersion] = useState<VersionItem | null>(null);
  const [diffData, setDiffData] = useState<{
    leftFrames: number;
    rightFrames: number;
    diff: string[];
  } | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);

  const fetchVersions = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError("");
    try {
      const res = await listVersions(projectId);
      setVersions(res.versions);
    } catch (err) {
      if (err instanceof NetworkError) setError("无法连接到服务器");
      else setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { fetchVersions(); }, [fetchVersions]);

  const handleRestore = async (versionId: string, version: number) => {
    if (!projectId) return;
    setRestoring(versionId);
    try {
      await restoreVersion(projectId, versionId);
      setMsg(`已恢复到版本 ${version}`);
      setTimeout(() => setMsg(""), 2000);
      fetchVersions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "恢复失败");
    } finally {
      setRestoring(null);
    }
  };

  const handleCompare = async () => {
    if (!projectId || !leftVersion || !rightVersion) return;
    setDiffLoading(true);
    setDiffData(null);
    try {
      const [left, right] = await Promise.all([
        getVersion(projectId, leftVersion.id),
        getVersion(projectId, rightVersion.id),
      ]);

      const leftDSL = (left as { dsl?: Record<string, unknown> }).dsl ?? {};
      const rightDSL = (right as { dsl?: Record<string, unknown> }).dsl ?? {};

      const leftFrames = ((leftDSL as Record<string, unknown>).frames as unknown[])?.length ?? 0;
      const rightFrames = ((rightDSL as Record<string, unknown>).frames as unknown[])?.length ?? 0;

      const diffLines: string[] = [];

      if (leftFrames !== rightFrames) {
        diffLines.push(`帧数量: ${leftFrames} → ${rightFrames} (${rightFrames > leftFrames ? "+" : ""}${rightFrames - leftFrames})`);
      }

      const leftParams = ((leftDSL as Record<string, unknown>).parameters as unknown[]) ?? [];
      const rightParams = ((rightDSL as Record<string, unknown>).parameters as unknown[]) ?? [];
      if (leftParams.length !== rightParams.length) {
        diffLines.push(`参数数量: ${leftParams.length} → ${rightParams.length}`);
      } else {
        for (const lp of leftParams) {
          const rp = rightParams.find(
            (r) => (r as Record<string, unknown>).key === (lp as Record<string, unknown>).key,
          );
          if (!rp) {
            diffLines.push(`参数 "${(lp as Record<string, unknown>).key}" 仅存在于左侧`);
          }
        }
      }

      const leftQuality = (leftDSL as Record<string, unknown>).quality_report as Record<string, unknown> | undefined;
      const rightQuality = (rightDSL as Record<string, unknown>).quality_report as Record<string, unknown> | undefined;
      if (leftQuality && rightQuality) {
        const lScore = leftQuality.overall_score as number ?? 0;
        const rScore = rightQuality.overall_score as number ?? 0;
        if (Math.abs(lScore - rScore) > 0.01) {
          diffLines.push(`质量评分: ${(lScore * 100).toFixed(0)}% → ${(rScore * 100).toFixed(0)}%`);
        }
      } else if (leftQuality && !rightQuality) {
        diffLines.push("质量报告: 仅在左侧存在");
      } else if (!leftQuality && rightQuality) {
        diffLines.push("质量报告: 仅在右侧存在");
      }

      if (diffLines.length === 0) {
        diffLines.push("两个版本无显著差异");
      }

      setDiffData({ leftFrames, rightFrames, diff: diffLines });
    } catch (err) {
      setError(err instanceof Error ? err.message : "对比失败");
    } finally {
      setDiffLoading(false);
    }
  };

  const toggleDiffMode = () => {
    setDiffMode(!diffMode);
    setDiffData(null);
    setLeftVersion(null);
    setRightVersion(null);
  };

  return (
    <div className="mx-auto max-w-2xl p-6">
      <Link
        to="/app"
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700"
      >
        <ArrowLeft size={17} />
        返回工作台
      </Link>

      <h1 className="text-2xl font-bold text-slate-900 mb-2">版本历史</h1>
      <p className="text-sm text-slate-500 mb-4">查看和恢复项目的历史版本</p>

      {/* 对比模式按钮 */}
      <div className="mb-6">
        <Button
          variant={diffMode ? "default" : "outline"}
          size="sm"
          onClick={toggleDiffMode}
          className="gap-1.5"
        >
          {diffMode ? <><X size={16} /> 退出对比</> : <><GitCompare size={16} /> 版本对比</>}
        </Button>
      </div>

      {/* 对比面板 */}
      {diffMode && (
        <div className="mb-6 rounded-xl border border-indigo-200 bg-indigo-50/50 p-4">
          <div className="flex items-center gap-4 mb-3">
            <div className="flex-1">
              <Label className="text-xs">左侧版本</Label>
              <select
                className="mt-1 h-9 w-full rounded-lg border bg-white px-3 text-sm"
                value={leftVersion?.id ?? ""}
                onChange={(e) => {
                  const v = versions.find((ver) => ver.id === e.target.value);
                  setLeftVersion(v ?? null);
                }}
              >
                <option value="">选择版本...</option>
                {versions.map((v) => (
                  <option key={v.id} value={v.id}>v{v.version} — {v.change_summary || "无描述"}</option>
                ))}
              </select>
            </div>
            <span className="text-slate-400 mt-5">vs</span>
            <div className="flex-1">
              <Label className="text-xs">右侧版本</Label>
              <select
                className="mt-1 h-9 w-full rounded-lg border bg-white px-3 text-sm"
                value={rightVersion?.id ?? ""}
                onChange={(e) => {
                  const v = versions.find((ver) => ver.id === e.target.value);
                  setRightVersion(v ?? null);
                }}
              >
                <option value="">选择版本...</option>
                {versions.map((v) => (
                  <option key={v.id} value={v.id}>v{v.version} — {v.change_summary || "无描述"}</option>
                ))}
              </select>
            </div>
          </div>
          <Button
            size="sm"
            disabled={!leftVersion || !rightVersion || diffLoading}
            onClick={handleCompare}
            className="gap-1.5"
          >
            {diffLoading ? <RefreshCw size={14} className="animate-spin" /> : <GitCompare size={14} />}
            开始对比
          </Button>

          {/* 对比结果 */}
          {diffData && (
            <div className="mt-4 rounded-lg border bg-white p-3">
              <div className="grid grid-cols-3 gap-4 mb-3 text-center">
                <div>
                  <p className="text-xs text-slate-400">左侧帧数</p>
                  <p className="text-lg font-bold">{diffData.leftFrames}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-400">右侧帧数</p>
                  <p className="text-lg font-bold">{diffData.rightFrames}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-400">差异</p>
                  <p className="text-lg font-bold">{Math.abs(diffData.rightFrames - diffData.leftFrames)}</p>
                </div>
              </div>
              <ul className="space-y-1">
                {diffData.diff.map((line, idx) => (
                  <li key={idx} className="text-sm text-slate-600 flex items-center gap-1.5">
                    <span className="text-[10px] text-slate-400">•</span>
                    {line}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {msg && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-green-50 p-3 text-sm text-green-700">
          <CheckCircle2 size={16} /> {msg}
        </div>
      )}

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-600">
          <AlertCircle size={16} /> {error}
          <Button variant="ghost" size="sm" onClick={fetchVersions} className="ml-auto gap-1">
            <RefreshCw size={14} /> 重试
          </Button>
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      ) : versions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 py-16 text-center">
          <p className="text-slate-500">暂无历史版本</p>
          <p className="text-xs text-slate-400 mt-1">在编辑器中保存后会生成版本记录</p>
        </div>
      ) : (
        <div className="space-y-3">
          {versions.map((v) => (
            <div
              key={v.id}
              className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4"
            >
              <div>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">v{v.version}</Badge>
                  <span className="text-sm font-medium text-slate-700">
                    {v.change_summary || "无描述"}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-1">
                  {v.created_at ? new Date(v.created_at).toLocaleString("zh-CN") : ""}
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                disabled={restoring === v.id}
                onClick={() => handleRestore(v.id, v.version)}
                className="gap-1"
              >
                <RotateCcw size={16} />
                {restoring === v.id ? "恢复中..." : "恢复"}
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}