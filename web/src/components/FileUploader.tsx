/**
 * 文件上传组件（FileUploader）。
 *
 * 支持拖拽 + 点击上传，预览解析结果，选择主题。
 * 对接: POST /api/materials/upload + POST /api/materials/{id}/parse
 *
 * 对齐：开发任务 F2.7 + 需求文档 10.1 节。
 */

import {
  useCallback,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Upload, FileText, CheckCircle2, AlertCircle, Loader2, X } from "lucide-react";
import { api, ApiError, NetworkError } from "@/services";

/** 允许的文件类型 */
const ACCEPTED_TYPES = ".pdf,.txt,.md,.py,.c,.java,.cpp,.pptx";
const ACCEPTED_MIME = [
  "application/pdf",
  "text/plain",
  "text/markdown",
  "text/x-python",
  "text/x-csrc",
  "text/x-java-source",
  "text/x-c++src",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
];

export type UploadedFile = {
  id: string;
  filename: string;
  type: string;
  size_bytes: number;
  status: "uploading" | "uploaded" | "parsing" | "done" | "error";
  topics?: string[];
  error?: string;
};

export type FileUploaderProps = {
  files: UploadedFile[];
  onFilesChange: Dispatch<SetStateAction<UploadedFile[]>>;
  onTopicSelect?: (topic: string) => void;
  disabled?: boolean;
  className?: string;
};

export function FileUploader({
  files,
  onFilesChange,
  onTopicSelect,
  disabled,
  className,
}: FileUploaderProps) {
  const [dragOver, setDragOver] = useState(false);

  const uploadFile = useCallback(
    async (file: File) => {
      const tempId = `temp-${Date.now()}`;

      // 添加临时文件条目
      const tempFile: UploadedFile = {
        id: tempId,
        filename: file.name,
        type: file.name.split(".").pop() ?? "unknown",
        size_bytes: file.size,
        status: "uploading",
      };
      onFilesChange([...files, tempFile]);

      try {
        // 上传（经 api-client，统一错误契约）
        const uploaded = await api.upload<{ id: string }>("/materials/upload", file);

        // 更新为上传完成
        onFilesChange((prev: UploadedFile[]) =>
          prev.map((f) =>
            f.id === tempId
              ? { ...f, id: uploaded.id, status: "parsing" as const }
              : f,
          ),
        );

        // 解析
        const parsed = await api.post<{ parsed_result?: { topics?: string[] } }>(
          `/materials/${uploaded.id}/parse`,
        );

        // 更新为完成
        onFilesChange((prev: UploadedFile[]) =>
          prev.map((f) =>
            f.id === uploaded.id
              ? {
                  ...f,
                  status: "done" as const,
                  topics: parsed.parsed_result?.topics ?? [],
                }
              : f,
          ),
        );
      } catch (err) {
        const message =
          err instanceof NetworkError
            ? "无法连接到服务器"
            : err instanceof ApiError
              ? err.message
              : err instanceof Error
                ? err.message
                : "上传失败";
        onFilesChange((prev: UploadedFile[]) =>
          prev.map((f) =>
            f.id === tempId
              ? { ...f, status: "error" as const, error: message }
              : f,
          ),
        );
      }
    },
    [files, onFilesChange],
  );

  const removeFile = useCallback(
    (fileId: string) => {
      onFilesChange(files.filter((f) => f.id !== fileId));
    },
    [files, onFilesChange],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      if (disabled) return;

      const droppedFiles = Array.from(e.dataTransfer.files);
      for (const file of droppedFiles) {
        if (ACCEPTED_MIME.includes(file.type) || file.name.match(/\.(pdf|txt|md|py|c|java|cpp|pptx)$/i)) {
          uploadFile(file);
        }
      }
    },
    [disabled, uploadFile],
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFiles = Array.from(e.target.files ?? []);
      for (const file of selectedFiles) {
        uploadFile(file);
      }
      // 重置 input 以允许重复选择同一文件
      e.target.value = "";
    },
    [uploadFile],
  );

  return (
    <div className={cn("space-y-4", className)}>
      {/* 拖拽上传区 */}
      <div
        className={cn(
          "flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 transition-colors",
          dragOver
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 hover:border-muted-foreground/50",
          disabled && "opacity-50 cursor-not-allowed",
        )}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        role="button"
        tabIndex={0}
        aria-label="拖拽文件到此处上传"
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") document.getElementById("file-upload-input")?.click(); }}
      >
        <Upload size={36} className="text-muted-foreground mb-3" />
        <p className="text-sm font-medium mb-1">拖拽课件文件到此处</p>
        <p className="text-xs text-muted-foreground mb-3">
          支持 PDF、PPTX、Markdown、TXT、代码文件（最大 50MB）
        </p>
        <Button
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={() => document.getElementById("file-upload-input")?.click()}
        >
          选择文件
        </Button>
        <input
          id="file-upload-input"
          type="file"
          className="hidden"
          accept={ACCEPTED_TYPES}
          multiple
          onChange={handleFileInput}
          disabled={disabled}
        />
      </div>

      {/* 文件列表 */}
      {files.length > 0 && (
        <ul className="space-y-2">
          {files.map((file) => (
            <li
              key={file.id}
              className={cn(
                "flex items-start gap-3 rounded-lg border p-3 transition-colors",
                file.status === "error" && "border-red-200 bg-red-50",
                file.status === "done" && "border-green-200 bg-green-50/30",
              )}
            >
              <FileText size={18} className="text-muted-foreground shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium truncate">{file.filename}</p>
                  <Badge variant="outline" className="text-[10px] shrink-0">
                    {file.type}
                  </Badge>
                  {file.status === "uploading" && (
                    <Loader2 size={14} className="animate-spin text-muted-foreground shrink-0" />
                  )}
                  {file.status === "parsing" && (
                    <Loader2 size={14} className="animate-spin text-primary shrink-0" />
                  )}
                  {file.status === "done" && (
                    <CheckCircle2 size={14} className="text-green-500 shrink-0" />
                  )}
                  {file.status === "error" && (
                    <AlertCircle size={14} className="text-red-500 shrink-0" />
                  )}
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {(file.size_bytes / 1024).toFixed(0)} KB
                  {file.error && <span className="text-red-500 ml-2">{file.error}</span>}
                </p>

                {/* 解析出的主题 */}
                {file.status === "done" && file.topics && file.topics.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    <span className="text-[10px] text-muted-foreground">检测到的主题:</span>
                    {file.topics.map((topic) => (
                      <Badge
                        key={topic}
                        variant="secondary"
                        className="cursor-pointer hover:bg-primary/10 text-[10px]"
                        onClick={() => onTopicSelect?.(topic)}
                      >
                        {topic}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 shrink-0"
                onClick={() => removeFile(file.id)}
              >
                <X size={14} />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default FileUploader;
