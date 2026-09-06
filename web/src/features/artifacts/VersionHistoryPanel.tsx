import { useEffect, useState } from "react";
import { GitCompare, History, LoaderCircle, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  diffVersion,
  listVersions,
  restoreVersion,
  type VersionDiffResponse,
  type VersionItem,
} from "@/services/versions";

export function VersionHistoryPanel({
  projectId,
  onRestored,
}: {
  projectId: string;
  onRestored?: () => void | Promise<void>;
}) {
  const [versions, setVersions] = useState<VersionItem[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<VersionItem>();
  const [diff, setDiff] = useState<VersionDiffResponse>();
  const [confirmRestore, setConfirmRestore] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!expanded) return;
    setLoading(true);
    listVersions(projectId)
      .then((result) => setVersions(result.versions))
      .catch((error) => setMessage(error instanceof Error ? error.message : "版本加载失败"))
      .finally(() => setLoading(false));
  }, [expanded, projectId]);

  const compare = async (version: VersionItem) => {
    setSelected(version);
    setConfirmRestore(false);
    setLoading(true);
    setMessage("");
    try {
      setDiff(await diffVersion(projectId, version.id));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "版本对比失败");
    } finally {
      setLoading(false);
    }
  };

  const restore = async () => {
    if (!selected) return;
    if (!confirmRestore) {
      setConfirmRestore(true);
      return;
    }
    setLoading(true);
    try {
      await restoreVersion(projectId, selected.id);
      setMessage(`已恢复到版本 ${selected.version}，恢复前状态已自动存档`);
      setConfirmRestore(false);
      setDiff(undefined);
      await onRestored?.();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "版本恢复失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="border-t border-[var(--border)] p-2 text-xs">
      <Button className="w-full justify-start" variant="ghost" size="sm" onClick={() => setExpanded((value) => !value)}>
        <History />版本历史
      </Button>
      {expanded && (
        <div className="mt-2 space-y-2">
          {loading && <p className="flex items-center gap-2 px-2 text-[var(--muted-foreground)]"><LoaderCircle className="animate-spin" size={13} />加载中</p>}
          {!loading && versions.length === 0 && <p className="px-2 text-[var(--muted-foreground)]">暂无已保存版本</p>}
          {versions.map((version) => (
            <button
              key={version.id}
              type="button"
              className={`w-full rounded-md border px-2 py-2 text-left ${selected?.id === version.id ? "border-[var(--interactive)] bg-[var(--interactive)]/5" : "border-[var(--border)]"}`}
              onClick={() => void compare(version)}
            >
              <span className="flex items-center justify-between gap-2 font-semibold">
                版本 {version.version}
                {version.is_current && <span className="rounded-full bg-[var(--interactive)]/10 px-1.5 py-0.5 text-[9px] text-[var(--interactive)]">当前</span>}
              </span>
              <span className="mt-0.5 block truncate text-[10px] text-[var(--muted-foreground)]">{version.change_summary}</span>
            </button>
          ))}
          {diff && selected && (
            <div className="rounded-md bg-[var(--secondary)] p-2" role="region" aria-label="版本差异预览">
              <p className="flex items-center gap-1 font-semibold"><GitCompare size={12} />版本 {selected.version} → 当前</p>
              <p className="mt-1 leading-5 text-[var(--muted-foreground)]">
                帧 +{diff.summary.frames_added} / -{diff.summary.frames_removed} / 改 {diff.summary.frames_modified}<br />
                参数变更 {diff.summary.parameters_changed} · 元数据变更 {diff.summary.metadata_fields_changed}
                {diff.summary.frame_order_changed ? " · 顺序已变化" : ""}
              </p>
              <Button className="mt-2 w-full" variant={confirmRestore ? "destructive" : "outline"} size="sm" disabled={loading} onClick={() => void restore()}>
                <RotateCcw />{confirmRestore ? `确认恢复版本 ${selected.version}` : "恢复此版本"}
              </Button>
            </div>
          )}
          {message && <p className="px-2 text-[10px] text-[var(--muted-foreground)]" role="status">{message}</p>}
        </div>
      )}
    </section>
  );
}
