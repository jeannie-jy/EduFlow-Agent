/**
 * 新建推演页 — 主题输入 + 约束配置 + 文件上传。
 *
 * 对接: POST /api/projects
 */

import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ArrowLeft, Sparkles, AlertCircle, FileText, Pencil, BookOpen } from "lucide-react";
import { Link } from "react-router-dom";
import { createProject, ApiError, NetworkError } from "@/services";
import { FileUploader, type UploadedFile } from "@/components/FileUploader";

const difficultyMap: Record<string, string> = {
  "1": "beginner",
  "2": "beginner",
  "3": "intermediate",
  "4": "advanced",
  "5": "advanced",
};

export function NewProject() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const templateName = searchParams.get("template") ?? "";
  const templateSubject = searchParams.get("subject") ?? "";
  const templateDifficulty = searchParams.get("difficulty") ?? "";

  const [title, setTitle] = useState("");
  const [inputContent, setInputContent] = useState("");
  const [inputType, setInputType] = useState<"natural_language" | "file_upload">("natural_language");
  const [audience, setAudience] = useState("undergraduate_cs");
  const [difficulty, setDifficulty] = useState("intermediate");
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 从模板库跳转过来时预填充表单
  useEffect(() => {
    if (!templateName) return;
    setTitle(templateName);
    setInputContent(
      `讲解 ${templateName}，包括核心概念、工作原理和典型示例。`,
    );
    if (templateDifficulty && difficultyMap[templateDifficulty]) {
      setDifficulty(difficultyMap[templateDifficulty]);
    }
  }, [templateName, templateDifficulty]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    setSubmitting(true);
    setError(null);

    try {
      const res = await createProject({
        title: title.trim(),
        input_type: "natural_language",
        input_content: inputContent.trim(),
        audience,
        difficulty,
      });
      navigate(`/app/project/${res.id}?tab=plan`);
    } catch (err) {
      if (err instanceof NetworkError) {
        setError("无法连接到服务器，请检查后端是否已启动");
      } else if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("创建失败，请稍后重试");
      }
    } finally {
      setSubmitting(false);
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

      <h1 className="text-2xl font-bold text-slate-900 mb-2">新建推演</h1>
      {templateName ? (
        <p className="text-sm text-slate-500 mb-8 flex items-center gap-2">
          <BookOpen size={14} className="text-indigo-400" />
          从模板创建：
          <Badge variant="secondary" className="font-normal">{templateName}</Badge>
          {templateSubject && (
            <Badge variant="outline" className="text-[10px]">{templateSubject}</Badge>
          )}
        </p>
      ) : (
        <p className="text-sm text-slate-500 mb-8">描述你想讲解的知识点，AI 将为你生成教学计划</p>
      )}

      {error && (
        <div className="mb-6 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <AlertCircle size={18} className="mt-0.5 shrink-0" />
          <div>
            <p className="font-medium">创建失败</p>
            <p className="text-red-600">{error}</p>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="space-y-2">
          <Label htmlFor="title">推演标题 *</Label>
          <Input
            id="title"
            placeholder="例如：Dijkstra 最短路径算法"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            disabled={submitting}
          />
        </div>

        {/* 输入方式选择 */}
        <div className="flex items-center gap-1 rounded-lg bg-muted p-0.5 w-fit">
          <button
            type="button"
            onClick={() => setInputType("natural_language")}
            className={`inline-flex h-7 items-center gap-1 rounded-md px-2.5 text-xs font-medium transition-colors ${
              inputType === "natural_language"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Pencil size={12} /> 自然语言
          </button>
          <button
            type="button"
            onClick={() => setInputType("file_upload")}
            className={`inline-flex h-7 items-center gap-1 rounded-md px-2.5 text-xs font-medium transition-colors ${
              inputType === "file_upload"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <FileText size={12} /> 上传材料
          </button>
        </div>

        {/* 输入内容区域 */}
        {inputType === "natural_language" ? (
          <div className="space-y-1.5">
            <Textarea
              id="content"
              maxLength={500}
              placeholder="描述你想讲解的知识点内容、重点和注意事项..."
              className="h-32 resize-none overflow-y-auto"
              value={inputContent}
              onChange={(e) => setInputContent(e.target.value)}
              disabled={submitting}
            />
            <p className="text-right text-xs text-muted-foreground">
              {inputContent.length} / 500
            </p>
          </div>
        ) : (
          <FileUploader
            files={uploadedFiles}
            onFilesChange={setUploadedFiles}
            onTopicSelect={(topic) => {
              if (!title) setTitle(topic);
              setInputContent(`讲解 ${topic}，包括核心概念、原理和示例。`);
            }}
            disabled={submitting}
          />
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>目标受众</Label>
            <Select value={audience} onValueChange={(v) => setAudience(v ?? "undergraduate_cs")} disabled={submitting}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="undergraduate_cs">计算机本科</SelectItem>
                <SelectItem value="graduate_cs">计算机研究生</SelectItem>
                <SelectItem value="high_school">高中生</SelectItem>
                <SelectItem value="self_learner">自学者</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>难度等级</Label>
            <Select value={difficulty} onValueChange={(v) => setDifficulty(v ?? "intermediate")} disabled={submitting}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="beginner">入门</SelectItem>
                <SelectItem value="intermediate">中级</SelectItem>
                <SelectItem value="advanced">高级</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <Button
          type="submit"
          className="w-full gap-2"
          disabled={submitting || !title.trim()}
        >
          <Sparkles size={18} />
          {submitting ? "正在创建..." : "开始生成教学计划"}
        </Button>
      </form>
    </div>
  );
}