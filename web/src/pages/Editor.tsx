/**
 * 推演编辑器 — 帧列表编辑 + 属性面板 + 局部重生成。
 *
 * 对接: GET/PUT frames, POST regenerate, POST versions
 */

import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowLeft,
  Save,
  Lock,
  Unlock,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  History,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  listFrames,
  updateFrame,
  lockFrame,
  regenerate,
  saveVersion,
  getProject,
  type FrameData,
  type ProjectDetailResponse,
  NetworkError,
} from "@/services";

export function Editor() {
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<ProjectDetailResponse | null>(null);
  const [frames, setFrames] = useState<FrameData[]>([]);
  const [selected, setSelected] = useState<FrameData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [error, setError] = useState("");

  const fetchFrames = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const [projectData, framesData] = await Promise.all([
        getProject(projectId),
        listFrames(projectId),
      ]);
      setProject(projectData);
      setFrames(framesData.frames);
      if (framesData.frames.length > 0 && !selected) {
        setSelected(framesData.frames[0]);
      }
    } catch (err) {
      if (err instanceof NetworkError) setError("无法连接到服务器");
      else setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [projectId, selected]);

  useEffect(() => { fetchFrames(); }, [projectId]);

  const handleSave = async () => {
    if (!projectId || !selected) return;
    setSaving(true);
    setSaveMsg("");
    try {
      await updateFrame(projectId, selected.frame_id, {
        title: selected.title,
        narration: selected.narration,
        visual_objects: selected.visual_objects,
        state_snapshot: selected.state_snapshot,
        animations: selected.animations,
      });
      setSaveMsg("保存成功");
      setTimeout(() => setSaveMsg(""), 2000);
    } catch (err) {
      setSaveMsg(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleLock = async (frameId: string, locked: boolean) => {
    if (!projectId) return;
    try {
      await lockFrame(projectId, frameId, locked);
      setFrames((prev) =>
        prev.map((f) => (f.frame_id === frameId ? { ...f, is_locked: locked } : f)),
      );
      if (selected?.frame_id === frameId) {
        setSelected((prev) => (prev ? { ...prev, is_locked: locked } : null));
      }
    } catch (err) {
      console.error("锁定失败:", err);
    }
  };

  const handleRegenerate = async () => {
    if (!projectId) return;
    try {
      await regenerate(projectId, { type: "from_frame" });
      await fetchFrames();
    } catch (err) {
      console.error("重生成失败:", err);
    }
  };

  const handleSaveVersion = async () => {
    if (!projectId) return;
    try {
      await saveVersion(projectId, "手动保存");
      setSaveMsg("版本已保存");
      setTimeout(() => setSaveMsg(""), 2000);
    } catch (err) {
      setSaveMsg(err instanceof Error ? err.message : "版本保存失败");
    }
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="w-full max-w-2xl space-y-4">
          <Skeleton className="h-8 w-1/3" />
          <Skeleton className="h-64 w-full rounded-xl" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6">
        <AlertCircle size={48} className="text-red-300 mb-4" />
        <p className="text-red-600 mb-4">{error}</p>
        <Button variant="outline" onClick={fetchFrames} className="gap-2">
          <RefreshCw size={16} /> 重试
        </Button>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* 顶部工具栏 */}
      <header className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-3">
          <Link to="/app" className="text-slate-500 hover:text-slate-700">
            <ArrowLeft size={18} />
          </Link>
          <h1 className="font-semibold text-slate-900">
            {project?.title ?? "推演编辑器"}
          </h1>
          <Badge variant="secondary">{frames.length} 帧</Badge>
        </div>
        <div className="flex items-center gap-2">
          {saveMsg && (
            <span className="text-xs text-green-600 flex items-center gap-1">
              <CheckCircle2 size={14} /> {saveMsg}
            </span>
          )}
          <Button variant="outline" size="sm" onClick={handleSaveVersion} className="gap-1">
            <History size={16} /> 保存版本
          </Button>
          <Button variant="outline" size="sm" onClick={handleRegenerate} className="gap-1">
            <RefreshCw size={16} /> 重生成
          </Button>
          <Button size="sm" onClick={handleSave} disabled={saving} className="gap-1">
            <Save size={16} /> {saving ? "保存中..." : "保存"}
          </Button>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        {/* 左侧帧列表 */}
        <aside className="w-64 border-r overflow-y-auto bg-slate-50">
          <div className="p-3">
            <p className="text-xs font-semibold text-slate-400 uppercase mb-2">帧列表</p>
            {frames.map((frame) => (
              <button
                key={frame.frame_id}
                onClick={() => setSelected(frame)}
                className={`w-full rounded-lg px-3 py-2 text-left text-sm transition-colors mb-1 ${
                  selected?.frame_id === frame.frame_id
                    ? "bg-indigo-50 text-indigo-700 font-medium"
                    : "hover:bg-slate-100 text-slate-700"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="truncate">{frame.frame_id}: {frame.title || "未命名"}</span>
                  {frame.is_locked && <Lock size={12} className="text-amber-500 shrink-0" />}
                </div>
              </button>
            ))}
          </div>
        </aside>

        {/* 右侧属性面板 */}
        <main className="flex-1 overflow-y-auto p-6">
          {selected ? (
            <div className="mx-auto max-w-2xl space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-slate-900">
                  {selected.frame_id} — {selected.title || "未命名帧"}
                </h2>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleLock(selected.frame_id, !selected.is_locked)}
                  className="gap-1"
                >
                  {selected.is_locked ? (
                    <><Unlock size={16} /> 解锁</>
                  ) : (
                    <><Lock size={16} /> 锁定</>
                  )}
                </Button>
              </div>

              <div className="space-y-2">
                <Label htmlFor="frame-title">标题</Label>
                <Input
                  id="frame-title"
                  value={selected.title}
                  onChange={(e) => setSelected({ ...selected, title: e.target.value })}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="frame-narration">讲解文本</Label>
                <Textarea
                  id="frame-narration"
                  rows={4}
                  value={selected.narration}
                  onChange={(e) => setSelected({ ...selected, narration: e.target.value })}
                />
              </div>

              <div className="space-y-2">
                <Label>视觉对象 (JSON)</Label>
                <Textarea
                  rows={8}
                  className="font-mono text-xs"
                  value={JSON.stringify(selected.visual_objects, null, 2)}
                  onChange={(e) => {
                    try {
                      const parsed = JSON.parse(e.target.value);
                      setSelected({ ...selected, visual_objects: parsed });
                    } catch { /* 编辑中 */ }
                  }}
                />
              </div>

              <div className="space-y-2">
                <Label>状态快照 (JSON)</Label>
                <Textarea
                  rows={8}
                  className="font-mono text-xs"
                  value={JSON.stringify(selected.state_snapshot, null, 2)}
                  onChange={(e) => {
                    try {
                      const parsed = JSON.parse(e.target.value);
                      setSelected({ ...selected, state_snapshot: parsed });
                    } catch { /* 编辑中 */ }
                  }}
                />
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center text-slate-400">
              <p>选择左侧帧开始编辑</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}