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
    <div className="mx-auto max-w-4xl p-6">
      <Link
        to="/app"
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700"
      >
        <ArrowLeft size={17} />
        返回工作台
      </Link>

      <h1 className="text-2xl font-bold text-slate-900 mb-2">知识模板库</h1>
      <p className="text-sm text-slate-500 mb-6">浏览预设知识点模板，快速开始推演</p>

      {/* 搜索栏 */}
      <div className="mb-6 flex gap-2">
        <div className="relative flex-1">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input
            className="pl-10"
            placeholder="搜索知识点...（如：AVL树、Dijkstra、TCP）"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
        </div>
        <Button onClick={handleSearch} disabled={searching || !query.trim()} className="gap-2">
          <Search size={18} />
          {searching ? "搜索中..." : "搜索"}
        </Button>
      </div>

      {/* 学科筛选 */}
      {searchResults === null && (
        <div className="mb-6 flex gap-2">
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
        <div className="mb-6 flex items-center gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-600">
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
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 py-16 text-center">
          <BookOpen size={48} className="mx-auto mb-4 text-slate-300" />
          <p className="text-slate-500">{searchResults !== null ? "未找到匹配的知识点" : "暂无模板"}</p>
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

            return (
              <Link
                key={id}
                to={`/app/new?template=${encodeURIComponent(concept)}`}
                className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:shadow-md hover:border-indigo-200"
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-semibold text-slate-900">{concept}</h3>
                  <div className="flex items-center gap-1">
                    {similarity !== null && (
                      <Badge variant="secondary">
                        {Math.round(similarity * 100)}% 匹配
                      </Badge>
                    )}
                    <Badge variant="outline">{difficultyLabels[difficulty] ?? `L${difficulty}`}</Badge>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  {subject && <span>{subjectLabels[subject] ?? subject}</span>}
                  <Sparkles size={12} className="text-indigo-400" />
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