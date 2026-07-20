/**
 * 新建推演页 — 主题输入 + 约束配置 + 文件上传。
 *
 * 对接: POST /api/projects
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ArrowLeft, Sparkles, AlertCircle, FileText, Pencil } from "lucide-react";
import { Link } from "react-router-dom";
import { createProject, ApiError, NetworkError } from "@/services";
import { FileUploader, type UploadedFile } from "@/components/FileUploader";

export function NewProject() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [inputContent, setInputContent] = useState("");
  const [inputType, setInputType] = useState<"natural_language" | "file_upload">("natural_language");
  const [audience, setAudience] = useState("undergraduate_cs");
  const [difficulty, setDifficulty] = useState("intermediate");
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      navigate(`/app/project/${res.id}/plan`);
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
      <p className="text-sm text-slate-500 mb-8">描述你想讲解的知识点，AI 将为你生成教学计划</p>

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
        <Tabs
          value={inputType}
          onValueChange={(v) => setInputType(v as typeof inputType)}
        >
          <TabsList variant="line" className="w-full justify-stretch">
            <TabsTrigger value="natural_language" className="gap-1.5">
              <Pencil size={14} /> 自然语言
            </TabsTrigger>
            <TabsTrigger value="file_upload" className="gap-1.5">
              <FileText size={14} /> 上传材料
            </TabsTrigger>
          </TabsList>

          <TabsContent value="natural_language" className="mt-4">
            <div className="space-y-2">
              <Label htmlFor="content">知识点描述</Label>
              <Textarea
                id="content"
                rows={5}
                placeholder="描述你想讲解的知识点内容、重点和注意事项..."
                value={inputContent}
                onChange={(e) => setInputContent(e.target.value)}
                disabled={submitting}
              />
            </div>
          </TabsContent>

          <TabsContent value="file_upload" className="mt-4">
            <FileUploader
              files={uploadedFiles}
              onFilesChange={setUploadedFiles}
              onTopicSelect={(topic) => {
                // 将选中的主题填入标题
                if (!title) setTitle(topic);
                setInputContent(`讲解 ${topic}，包括核心概念、原理和示例。`);
              }}
              disabled={submitting}
            />
          </TabsContent>
        </Tabs>

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