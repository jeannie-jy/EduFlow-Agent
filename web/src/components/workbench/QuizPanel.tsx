/**
 * QuizPanel — 练习题交互面板。
 *
 * 展示生成的练习题，支持答题、即时反馈和得分统计。
 */

import { useState, useCallback, useMemo } from "react";
import { CheckCircle2, XCircle, Lightbulb, ChevronRight, RotateCcw, Trophy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// ============================================================================
// 类型
// ============================================================================

export interface QuizOption {
  id: string;
  text: string;
  is_correct?: boolean;
}

export interface QuizQuestion {
  id: string;
  type: "multiple_choice" | "true_false" | "fill_blank" | "short_answer";
  question: string;
  options?: QuizOption[];
  correct_answer?: string;
  explanation: string;
  expected_keywords?: string[];
  related_concept?: string;
  difficulty: number;
}

export interface QuizPanelProps {
  questions: QuizQuestion[];
}

// ============================================================================
// Helpers
// ============================================================================

const DIFFICULTY_LABELS: Record<number, string> = { 1: "入门", 2: "进阶", 3: "挑战" };
const DIFFICULTY_COLORS: Record<number, string> = {
  1: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  2: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
  3: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
};

// ============================================================================
// 组件
// ============================================================================

export function QuizPanel({ questions }: QuizPanelProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});
  const [score, setScore] = useState<{ correct: number; total: number }>({ correct: 0, total: 0 });
  const [done, setDone] = useState(false);

  const currentQuestion = questions[currentIndex] ?? null;
  const totalQuestions = questions.length;

  // 检查当前题目是否已回答
  const hasAnswered = useMemo(() => {
    if (!currentQuestion) return false;
    return currentQuestion.id in answers;
  }, [currentQuestion, answers]);

  // 判断是否正确
  const isCorrect = useMemo(() => {
    if (!currentQuestion || !hasAnswered) return null;
    const answer = answers[currentQuestion.id];
    if (currentQuestion.type === "multiple_choice") {
      const correctOpt = currentQuestion.options?.find((o) => o.is_correct);
      return answer === correctOpt?.id;
    }
    if (currentQuestion.type === "true_false") {
      return answer === currentQuestion.correct_answer;
    }
    if (currentQuestion.type === "fill_blank") {
      const accepted = (currentQuestion.correct_answer ?? "").split("/");
      return accepted.some((a) => answer.trim().toLowerCase() === a.trim().toLowerCase());
    }
    // short_answer: always show explanation, no auto-grading
    return null;
  }, [currentQuestion, hasAnswered, answers]);

  const handleSelect = useCallback((value: string) => {
    if (!currentQuestion || hasAnswered) return;
    const newAnswers = { ...answers, [currentQuestion.id]: value };
    setAnswers(newAnswers);

    // auto-grade
    let correct = false;
    if (currentQuestion.type === "multiple_choice") {
      const correctOpt = currentQuestion.options?.find((o) => o.is_correct);
      correct = value === correctOpt?.id;
    } else if (currentQuestion.type === "true_false") {
      correct = value === currentQuestion.correct_answer;
    } else if (currentQuestion.type === "fill_blank") {
      const accepted = (currentQuestion.correct_answer ?? "").split("/");
      correct = accepted.some((a) => value.trim().toLowerCase() === a.trim().toLowerCase());
    }
    setScore((prev) => ({
      correct: prev.correct + (correct ? 1 : 0),
      total: prev.total + 1,
    }));
  }, [currentQuestion, hasAnswered, answers]);

  const handleReveal = useCallback(() => {
    if (!currentQuestion) return;
    setRevealed((prev) => ({ ...prev, [currentQuestion.id]: true }));
  }, [currentQuestion]);

  const handleNext = useCallback(() => {
    if (currentIndex < totalQuestions - 1) {
      setCurrentIndex((prev) => prev + 1);
    } else {
      setDone(true);
    }
  }, [currentIndex, totalQuestions]);

  const handleRestart = useCallback(() => {
    setCurrentIndex(0);
    setAnswers({});
    setRevealed({});
    setScore({ correct: 0, total: 0 });
    setDone(false);
  }, []);

  // ── 完成页面 ──
  if (done) {
    const pct = score.total > 0 ? Math.round((score.correct / score.total) * 100) : 0;
    return (
      <div className="flex flex-col items-center gap-6 p-8">
        <Trophy size={64} className="text-yellow-500" />
        <div className="text-center">
          <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100">练习完成！</h3>
          <p className="mt-2 text-3xl font-bold text-blue-600 dark:text-blue-400">
            {score.correct} / {score.total}
          </p>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            正确率 {pct}%
          </p>
        </div>
        <Button onClick={handleRestart} variant="outline" className="gap-2">
          <RotateCcw size={16} /> 重新开始
        </Button>
      </div>
    );
  }

  if (!currentQuestion) {
    return (
      <div className="flex items-center justify-center p-8 text-gray-400">
        暂无练习题
      </div>
    );
  }

  // ── 题目页面 ──
  return (
    <div className="flex flex-col gap-4 p-4">
      {/* 进度条 */}
      <div className="flex items-center gap-3">
        <span className="text-sm text-gray-500 dark:text-gray-400">
          {currentIndex + 1} / {totalQuestions}
        </span>
        <div className="h-1.5 flex-1 rounded-full bg-gray-200 dark:bg-gray-700">
          <div
            className="h-full rounded-full bg-blue-500 transition-all"
            style={{ width: `${((currentIndex + 1) / totalQuestions) * 100}%` }}
          />
        </div>
        <Badge className={cn("text-xs", DIFFICULTY_COLORS[currentQuestion.difficulty] ?? "")}>
          {DIFFICULTY_LABELS[currentQuestion.difficulty] ?? currentQuestion.difficulty}
        </Badge>
      </div>

      {/* 题目类型标签 */}
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="text-xs">
          {currentQuestion.type === "multiple_choice" ? "选择题" :
           currentQuestion.type === "true_false" ? "判断题" :
           currentQuestion.type === "fill_blank" ? "填空题" : "简答题"}
        </Badge>
        {currentQuestion.related_concept && (
          <Badge variant="outline" className="text-xs opacity-50">
            {currentQuestion.related_concept}
          </Badge>
        )}
      </div>

      {/* 题干 */}
      <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100 leading-relaxed">
        {currentQuestion.question}
      </h3>

      {/* 选择题选项 */}
      {currentQuestion.type === "multiple_choice" && currentQuestion.options && (
        <div className="flex flex-col gap-2">
          {currentQuestion.options.map((opt) => {
            const isSelected = answers[currentQuestion.id] === opt.id;
            const showCorrect = hasAnswered && opt.is_correct;
            const showWrong = hasAnswered && isSelected && !opt.is_correct;

            return (
              <button
                key={opt.id}
                onClick={() => handleSelect(opt.id)}
                disabled={hasAnswered}
                className={cn(
                  "flex items-center gap-3 rounded-lg border px-4 py-3 text-left text-sm transition-all",
                  "hover:border-blue-300 hover:bg-blue-50 dark:hover:border-blue-700 dark:hover:bg-blue-950",
                  hasAnswered ? "cursor-default" : "cursor-pointer",
                  showCorrect && "border-green-400 bg-green-50 dark:border-green-700 dark:bg-green-950",
                  showWrong && "border-red-400 bg-red-50 dark:border-red-700 dark:bg-red-950",
                  isSelected && !hasAnswered && "border-blue-500 bg-blue-50 dark:border-blue-400 dark:bg-blue-950",
                )}
              >
                <span className={cn(
                  "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-sm font-medium",
                  showCorrect && "border-green-500 bg-green-500 text-white",
                  showWrong && "border-red-500 bg-red-500 text-white",
                  isSelected && !hasAnswered && "border-blue-500 bg-blue-500 text-white",
                  !isSelected && !hasAnswered && "border-gray-300 text-gray-500 dark:border-gray-600",
                )}>
                  {showCorrect ? <CheckCircle2 size={14} /> :
                   showWrong ? <XCircle size={14} /> :
                   opt.id.toUpperCase()}
                </span>
                <span className={cn(
                  showCorrect && "text-green-800 dark:text-green-200 font-medium",
                  showWrong && "text-red-800 dark:text-red-200",
                )}>
                  {opt.text}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {/* 判断题 */}
      {currentQuestion.type === "true_false" && (
        <div className="flex gap-3">
          {["true", "false"].map((val) => {
            const isSelected = answers[currentQuestion.id] === val;
            const showCorrect = hasAnswered && val === currentQuestion.correct_answer;
            const showWrong = hasAnswered && isSelected && val !== currentQuestion.correct_answer;
            return (
              <Button
                key={val}
                onClick={() => handleSelect(val)}
                disabled={hasAnswered}
                variant={showCorrect ? "default" : showWrong ? "destructive" : isSelected ? "default" : "outline"}
                className={cn("flex-1", showCorrect && "bg-green-500 hover:bg-green-500")}
              >
                {val === "true" ? "✓ 正确" : "✗ 错误"}
              </Button>
            );
          })}
        </div>
      )}

      {/* 填空题 */}
      {currentQuestion.type === "fill_blank" && (
        <div className="space-y-3">
          <input
            type="text"
            className="w-full rounded-lg border border-gray-300 px-4 py-3 text-sm dark:border-gray-600 dark:bg-gray-800"
            placeholder="请输入你的答案..."
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleSelect((e.target as HTMLInputElement).value);
              }
            }}
            disabled={hasAnswered}
          />
          {!hasAnswered && (
            <Button
              onClick={() => {
                const input = document.querySelector("input") as HTMLInputElement;
                if (input?.value) handleSelect(input.value);
              }}
              className="w-full"
            >
              提交答案
            </Button>
          )}
        </div>
      )}

      {/* 简答题 */}
      {currentQuestion.type === "short_answer" && (
        <div className="space-y-3">
          <textarea
            className="w-full rounded-lg border border-gray-300 px-4 py-3 text-sm dark:border-gray-600 dark:bg-gray-800"
            rows={3}
            placeholder="请输入你的答案..."
            disabled={hasAnswered}
          />
          {!hasAnswered && (
            <Button
              onClick={() => {
                const input = document.querySelector("textarea") as HTMLTextAreaElement;
                if (input?.value) handleSelect(input.value);
              }}
              className="w-full"
            >
              提交答案（教师评阅）
            </Button>
          )}
          {hasAnswered && !revealed[currentQuestion.id] && (
            <p className="text-xs text-gray-400">简答题不自动判分，点击查看参考答案</p>
          )}
        </div>
      )}

      {/* 反馈区域 */}
      {hasAnswered && (
        <div className={cn(
          "rounded-lg border p-4",
          isCorrect === true && "border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950",
          isCorrect === false && "border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950",
          isCorrect === null && "border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950",
        )}>
          {isCorrect === true && (
            <p className="flex items-center gap-2 text-sm font-medium text-green-700 dark:text-green-300">
              <CheckCircle2 size={16} /> 回答正确！
            </p>
          )}
          {isCorrect === false && (
            <p className="flex items-center gap-2 text-sm font-medium text-red-700 dark:text-red-300">
              <XCircle size={16} /> 回答错误
              {currentQuestion.correct_answer && (
                <span>（正确答案：{currentQuestion.correct_answer}）</span>
              )}
            </p>
          )}
          {isCorrect === null && (
            <p className="flex items-center gap-2 text-sm font-medium text-blue-700 dark:text-blue-300">
              <Lightbulb size={16} /> 已提交，请查看参考解析
            </p>
          )}

          {!revealed[currentQuestion.id] && (
            <Button
              onClick={handleReveal}
              variant="ghost"
              size="sm"
              className="mt-2 gap-1 text-xs"
            >
              <Lightbulb size={14} /> 查看解析
            </Button>
          )}

          {revealed[currentQuestion.id] && (
            <div className="mt-3 rounded-md bg-white/50 p-3 text-sm text-gray-700 dark:bg-gray-900/50 dark:text-gray-300">
              <p className="font-medium mb-1 text-xs text-gray-500">📖 解析</p>
              {currentQuestion.explanation}
              {currentQuestion.expected_keywords && currentQuestion.expected_keywords.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs text-gray-500 mb-1">关键词：</p>
                  <div className="flex flex-wrap gap-1">
                    {currentQuestion.expected_keywords.map((kw) => (
                      <Badge key={kw} variant="outline" className="text-xs">{kw}</Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 下一题按钮 */}
      {hasAnswered && (
        <Button onClick={handleNext} className="gap-2 self-end">
          {currentIndex < totalQuestions - 1 ? (
            <>下一题 <ChevronRight size={16} /></>
          ) : (
            <>查看结果 <Trophy size={16} /></>
          )}
        </Button>
      )}
    </div>
  );
}
