/**
 * 知识模板库 — 浏览预设知识点模板，按学科/难度筛选。
 *
 * 对接: GET /api/knowledge/templates, POST /api/knowledge/search
 */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Search,
  ArrowLeft,
  Sparkles,
  BookOpen,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import {
  listTemplates,
  searchKnowledge,
  type TemplateItem,
  type SearchResultItem,
  NetworkError,
} from "@/services";

const subjectLabels: Record<string, string> = {
  algorithm: "算法",
  data_structure: "数据结构",
  operating_system: "操作系统",
  network: "网络",
  database: "数据库",
};

const difficultyLabels: Record<number, string> = {
  1: "入门",
  2: "初级",
  3: "中级",
  4: "高级",
  5: "专家",
};

export function TemplateBrowser() {
  const [templates, setTemplates] = useState<TemplateItem[]>([]);
  const [searchResults, setSearchResults] = useState<SearchResultItem[] | null>(null);
  const [query, setQuery] = useState("");
  const [subjectFilter, setSubjectFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await listTemplates(
        subjectFilter ? { subject: subjectFilter } : undefined,
      );
      setTemplates(res.templates);
      setSearchResults(null);
    } catch (err) {
      if (err instanceof NetworkError) setError("无法连接到服务器");
      else setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [subjectFilter]);

  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setError("");
    try {
      const res = await searchKnowledge(query.trim(), 10);
      setSearchResults(res.results);
    } catch (err) {
      if (err instanceof NetworkError) setError("无法连接到服务器");
      else setError(err instanceof Error ? err.message : "搜索失败");
    } finally {
      setSearching(false);
    }
  };

  const display = searchResults ?? templates;

  return (
    <div className="mx-auto max-w-5xl p-4 sm:p-6">
      <Link
        to="/app"
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
      >
        <ArrowLeft size={17} />
        返回工作台
      </Link>

      <h1 className="mb-2 text-2xl font-bold text-[var(--foreground)]">知识模板库</h1>
      <p className="mb-6 text-sm text-[var(--muted-foreground)]">浏览预设知识点模板，快速开始推演</p>

      {/* 搜索栏 */}
      <div className="mb-6 flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]" />
          <Input
            className="pl-10"
            placeholder="搜索知识点...（如：AVL树、Dijkstra、TCP）"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
        </div>
        <Button onClick={handleSearch} disabled={searching || !query.trim()} className="gap-2 sm:min-w-24">
          <Search size={18} />
          {searching ? "搜索中..." : "搜索"}
        </Button>
      </div>

      {/* 学科筛选 */}
      {searchResults === null && (
        <div className="mb-6 flex flex-wrap gap-2" aria-label="按学科筛选模板">
          <Button
            variant={subjectFilter === "" ? "default" : "outline"}
            size="sm"
            onClick={() => setSubjectFilter("")}
          >
            全部
          </Button>
          {Object.entries(subjectLabels).map(([key, label]) => (
            <Button
              key={key}
              variant={subjectFilter === key ? "default" : "outline"}
              size="sm"
              onClick={() => setSubjectFilter(key)}
            >
              {label}
            </Button>
          ))}
        </div>
      )}

      {error && (
        <div className="mb-6 flex items-center gap-2 rounded-lg border border-[color-mix(in_oklch,var(--error)_30%,var(--border))] bg-[color-mix(in_oklch,var(--error)_8%,var(--card))] p-3 text-sm text-[var(--error)]">
          <AlertCircle size={16} /> {error}
          <Button variant="ghost" size="sm" onClick={searchResults ? handleSearch : fetchTemplates} className="ml-auto gap-1">
            <RefreshCw size={14} /> 重试
          </Button>
        </div>
      )}

      {/* 结果列表 */}
      {loading || searching ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
      ) : display.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--secondary)]/45 py-16 text-center">
          <BookOpen size={48} className="mx-auto mb-4 text-[var(--muted-foreground)] opacity-55" />
          <p className="text-[var(--muted-foreground)]">{searchResults !== null ? "未找到匹配的知识点" : "暂无模板"}</p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {display.map((item) => {
            const isSearch = searchResults !== null;
            const concept = item.concept;
            const id = item.id;
            const subject = "subject" in item ? (item.subject ?? "") : "";
            const difficulty = "difficulty" in item ? item.difficulty : 3;
            const similarity = isSearch && "similarity" in (item as SearchResultItem)
              ? (item as SearchResultItem).similarity : null;

            const templateParams = new URLSearchParams();
            templateParams.set("template", concept);
            if (subject) templateParams.set("subject", subject);
            if (difficulty) templateParams.set("difficulty", String(difficulty));

            return (
              <Link
                key={id}
                to={`/app/project/_new?${templateParams.toString()}`}
                className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm transition-[border-color,box-shadow,transform] hover:-translate-y-0.5 hover:border-[color-mix(in_oklch,var(--interactive)_45%,var(--border))] hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--interactive)]"
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-semibold text-[var(--foreground)]">{concept}</h3>
                  <div className="flex items-center gap-1">
                    {similarity !== null && (
                      <Badge variant="secondary">
                        {Math.round(similarity * 100)}% 匹配
                      </Badge>
                    )}
                    <Badge variant="outline">{difficultyLabels[difficulty] ?? `L${difficulty}`}</Badge>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
                  {subject && <span>{subjectLabels[subject] ?? subject}</span>}
                  <Sparkles size={12} className="text-[var(--interactive)]" />
                  <span>点击开始推演</span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
