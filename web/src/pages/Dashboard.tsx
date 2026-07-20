/**
 * 工作台（Dashboard）— 项目列表 + 新建入口。
 *
 * 对接: GET /api/projects
 */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  Plus,
  FolderOpen,
  RefreshCw,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import {
  listProjects,
  type ProjectListItem,
  ApiError,
  NetworkError,
} from "@/services";

// ============================================================================
// 状态映射
// ============================================================================

const statusLabels: Record<string, string> = {
  draft: "草稿",
  planning: "规划中",
  generating: "生成中",
  reviewing: "校验中",
  done: "已完成",
  failed: "失败",
};

const statusVariants: Record<string, "default" | "secondary" | "outline"> = {
  draft: "secondary",
  planning: "secondary",
  generating: "default",
  reviewing: "default",
  done: "outline",
  failed: "secondary",
};

// ============================================================================
// 组件
// ============================================================================

export function Dashboard() {
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pageSize = 20;

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { page: number; page_size: number; status?: string } = {
        page,
        page_size: pageSize,
      };
      if (statusFilter) params.status = statusFilter;
      const res = await listProjects(params);
      setProjects(res.items);
      setTotal(res.total);
    } catch (err) {
      if (err instanceof NetworkError) {
        setError("无法连接到服务器，请检查网络或后端是否已启动");
      } else if (err instanceof ApiError) {
        setError(`服务器错误: ${err.message}`);
      } else {
        setError("加载项目列表失败，请稍后重试");
      }
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">我的推演</h1>
          <p className="text-sm text-slate-500 mt-1">管理和创建你的教学推演项目</p>
        </div>
        <Link to="/app/new">
          <Button className="gap-2">
            <Plus size={18} />
            新建推演
          </Button>
        </Link>
      </div>

      {/* 状态筛选 */}
      <div className="flex gap-2">
        <Button
          variant={statusFilter === "" ? "default" : "outline"}
          size="sm"
          onClick={() => { setPage(1); setStatusFilter(""); }}
        >
          全部
        </Button>
        {Object.entries(statusLabels).map(([key, label]) => (
          <Button
            key={key}
            variant={statusFilter === key ? "default" : "outline"}
            size="sm"
            onClick={() => { setPage(1); setStatusFilter(key); }}
          >
            {label}
          </Button>
        ))}
      </div>

      {/* 内容区 */}
      {loading ? (
        <LoadingSkeleton />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchProjects} />
      ) : projects.length === 0 ? (
        <EmptyState statusFilter={statusFilter} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => (
              <ProjectCard key={project.id} project={project} />
            ))}
          </div>

          {/* 分页 */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-slate-500">
                共 {total} 个项目，第 {page}/{totalPages} 页
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  <ChevronLeft size={16} />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  <ChevronRight size={16} />
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ============================================================================
// 项目卡片
// ============================================================================

function ProjectCard({ project }: { project: ProjectListItem }) {
  return (
    <Link
      to={`/app/project/${project.id}/play`}
      className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-all hover:shadow-md hover:border-indigo-200"
    >
      <div className="flex items-start justify-between mb-3">
        <h3 className="font-semibold text-slate-900 truncate flex-1 mr-2">
          {project.title}
        </h3>
        <Badge variant={statusVariants[project.status] ?? "secondary"}>
          {statusLabels[project.status] ?? project.status}
        </Badge>
      </div>
      <div className="flex items-center gap-4 text-xs text-slate-400">
        {project.topic && <span>{project.topic}</span>}
        <span>{project.difficulty === "intermediate" ? "中级" : project.difficulty}</span>
        <span>{project.frame_count} 帧</span>
      </div>
      <div className="mt-3 text-xs text-slate-400">
        {project.updated_at ? new Date(project.updated_at).toLocaleDateString("zh-CN") : ""}
      </div>
    </Link>
  );
}

// ============================================================================
// 加载骨架屏
// ============================================================================

function LoadingSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="rounded-xl border border-slate-200 bg-white p-5">
          <Skeleton className="h-5 w-3/4 mb-3" />
          <Skeleton className="h-3 w-1/2 mb-2" />
          <Skeleton className="h-3 w-1/4" />
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// 空状态
// ============================================================================

function EmptyState({ statusFilter }: { statusFilter: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50 py-20">
      <FolderOpen size={48} className="text-slate-300 mb-4" />
      <p className="text-slate-500 mb-2">
        {statusFilter ? `没有 "${statusLabels[statusFilter] ?? statusFilter}" 状态的项目` : "还没有推演项目"}
      </p>
      <p className="text-sm text-slate-400 mb-4">创建一个推演，开始你的交互式教学体验</p>
      <Link to="/app/new">
        <Button variant="outline" className="gap-2">
          <Plus size={16} />
          创建第一个推演
        </Button>
      </Link>
    </div>
  );
}

// ============================================================================
// 错误状态
// ============================================================================

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-red-200 bg-red-50 py-20">
      <AlertCircle size={48} className="text-red-300 mb-4" />
      <p className="text-red-600 mb-2">{message}</p>
      <Button variant="outline" size="sm" onClick={onRetry} className="gap-2">
        <RefreshCw size={16} />
        重试
      </Button>
    </div>
  );
}