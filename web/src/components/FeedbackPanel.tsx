/**
 * 反馈提交面板（FeedbackPanel）。
 *
 * 支持帧级评分（1-5 星）、纠错、建议三种反馈类型。
 * 对接: POST /api/projects/{id}/feedback
 *
 * 对齐：需求文档 10.8 节 + 开发任务 F3.2。
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { api, ApiError, NetworkError } from "@/services";
import {
  Star,
  AlertTriangle,
  Lightbulb,
  Send,
  CheckCircle2,
  Loader2,
} from "lucide-react";

export type FeedbackType = "rating" | "correction" | "suggestion";

export type FeedbackPanelProps = {
  projectId: string;
  frameId?: string;
  className?: string;
};

/** 反馈类型配置 */
const FEEDBACK_TYPES: {
  key: FeedbackType;
  label: string;
  icon: typeof Star;
  placeholder: string;
}[] = [
  {
    key: "rating",
    label: "评分",
    icon: Star,
    placeholder: "你对这一帧内容的评分...",
  },
  {
    key: "correction",
    label: "纠错",
    icon: AlertTriangle,
    placeholder: "描述你发现的知识错误或问题...",
  },
  {
    key: "suggestion",
    label: "建议",
    icon: Lightbulb,
    placeholder: "分享你的改进建议...",
  },
];

export function FeedbackPanel({
  projectId,
  frameId,
  className,
}: FeedbackPanelProps) {
  const [feedbackType, setFeedbackType] = useState<FeedbackType>("rating");
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  const activeConfig = FEEDBACK_TYPES.find((t) => t.key === feedbackType)!;

  const handleSubmit = async () => {
    if (feedbackType === "rating" && rating === 0) return;
    if ((feedbackType === "correction" || feedbackType === "suggestion") && !content.trim()) return;

    setSubmitting(true);
    setError("");

    try {
      const body: Record<string, unknown> = {
        type: feedbackType,
        content: content.trim(),
      };
      if (frameId) body.frame_id = frameId;
      if (feedbackType === "rating") body.rating = rating;

      await api.post(`/projects/${projectId}/feedback`, body);

      setSubmitted(true);
      setTimeout(() => {
        setSubmitted(false);
        setRating(0);
        setContent("");
      }, 3000);
    } catch (err) {
      if (err instanceof NetworkError) setError("无法连接到服务器");
      else if (err instanceof ApiError) setError(err.message);
      else setError(err instanceof Error ? err.message : "提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={cn("space-y-4 rounded-xl border p-4", className)}>
      <h3 className="text-sm font-semibold">反馈</h3>

      {/* 反馈类型选择 */}
      <div className="flex gap-1.5">
        {FEEDBACK_TYPES.map((type) => {
          const Icon = type.icon;
          return (
            <Button
              key={type.key}
              variant={feedbackType === type.key ? "default" : "outline"}
              size="sm"
              className="gap-1.5"
              onClick={() => setFeedbackType(type.key)}
            >
              <Icon size={14} />
              {type.label}
            </Button>
          );
        })}
      </div>

      {/* 星级评分（仅 rating 类型） */}
      {feedbackType === "rating" && (
        <div className="flex items-center gap-1" role="radiogroup" aria-label="评分">
          {[1, 2, 3, 4, 5].map((star) => (
            <button
              key={star}
              type="button"
              role="radio"
              aria-checked={rating === star}
              aria-label={`${star} 星`}
              className="p-0.5 transition-transform hover:scale-110 focus:outline-none"
              onClick={() => setRating(star)}
              onMouseEnter={() => setHoverRating(star)}
              onMouseLeave={() => setHoverRating(0)}
            >
              <Star
                size={24}
                className={cn(
                  "transition-colors",
                  (hoverRating || rating) >= star
                    ? "fill-amber-400 text-amber-400"
                    : "text-muted-foreground/30",
                )}
              />
            </button>
          ))}
          {rating > 0 && (
            <span className="ml-2 text-xs text-muted-foreground">
              {rating === 1 ? "很差" : rating === 2 ? "较差" : rating === 3 ? "一般" : rating === 4 ? "好" : "非常好"}
            </span>
          )}
        </div>
      )}

      {/* 反馈内容 */}
      {(feedbackType === "correction" || feedbackType === "suggestion") && (
        <Textarea
          rows={3}
          placeholder={activeConfig.placeholder}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          disabled={submitting}
        />
      )}

      {/* 错误提示 */}
      {error && (
        <p className="text-xs text-red-500 flex items-center gap-1">
          <AlertTriangle size={12} />
          {error}
        </p>
      )}

      {/* 提交 */}
      <Button
        size="sm"
        className="w-full gap-1.5"
        onClick={handleSubmit}
        disabled={
          submitting ||
          submitted ||
          (feedbackType === "rating" && rating === 0) ||
          (feedbackType !== "rating" && !content.trim())
        }
      >
        {submitting ? (
          <><Loader2 size={14} className="animate-spin" /> 提交中...</>
        ) : submitted ? (
          <><CheckCircle2 size={14} /> 已提交</>
        ) : (
          <><Send size={14} /> 提交反馈</>
        )}
      </Button>
    </div>
  );
}

export default FeedbackPanel;