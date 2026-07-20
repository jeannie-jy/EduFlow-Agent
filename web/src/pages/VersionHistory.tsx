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
import { ArrowLeft, RefreshCw, RotateCcw, AlertCircle, CheckCircle2 } from "lucide-react";
import { Link } from "react-router-dom";
import {
  listVersions,
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
      <p className="text-sm text-slate-500 mb-8">查看和恢复项目的历史版本</p>

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