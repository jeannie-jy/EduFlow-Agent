import { useMemo, useState } from "react";
import { BookOpen, CheckCircle2, ChevronLeft, ChevronRight, CircleHelp, Lightbulb, RotateCcw, Trophy, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface QuizOption { id: string; text: string; is_correct?: boolean }
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
export interface QuizPanelProps { questions: QuizQuestion[] }

const DIFFICULTY: Record<number, string> = { 1: "入门", 2: "进阶", 3: "挑战" };
const TYPES: Record<QuizQuestion["type"], string> = {
  multiple_choice: "选择题", true_false: "判断题", fill_blank: "填空题", short_answer: "简答题",
};

function grade(question: QuizQuestion, answer: string): boolean | null {
  if (question.type === "multiple_choice") return answer === question.options?.find((item) => item.is_correct)?.id;
  if (question.type === "true_false") return answer === question.correct_answer;
  if (question.type === "fill_blank") {
    return (question.correct_answer ?? "").split("/").some(
      (item) => answer.trim().toLocaleLowerCase() === item.trim().toLocaleLowerCase(),
    );
  }
  return null;
}

export function QuizPanel({ questions }: QuizPanelProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});
  const [done, setDone] = useState(false);
  const currentQuestion = questions[currentIndex];
  const results = useMemo(
    () => questions.map((question) => question.id in answers ? grade(question, answers[question.id]) : undefined),
    [answers, questions],
  );
  const correctCount = results.filter((result) => result === true).length;
  const gradedCount = results.filter((result) => typeof result === "boolean").length;
  const answeredCount = Object.keys(answers).length;

  const restart = () => {
    setCurrentIndex(0); setAnswers({}); setDrafts({}); setRevealed({}); setDone(false);
  };

  if (!currentQuestion) return <div className="p-8 text-center text-[var(--muted-foreground)]">暂无练习题</div>;

  if (done) {
    const percentage = gradedCount ? Math.round(correctCount / gradedCount * 100) : 0;
    return (
      <section className="grid min-h-[31rem] place-items-center bg-[var(--stage-bg)] p-5">
        <div className="w-full max-w-2xl rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm sm:p-8">
          <div className="text-center">
            <span className="mx-auto grid size-16 place-items-center rounded-full bg-[color-mix(in_oklch,var(--warning)_15%,var(--card))] text-[var(--warning)]"><Trophy size={32} /></span>
            <h3 className="mt-4 font-serif text-2xl font-bold">练习完成！</h3>
            <p className="mt-2 font-mono text-4xl font-bold text-[var(--interactive)]">{correctCount} / {gradedCount}</p>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">自动评分正确率 {percentage}%</p>
          </div>
          <div className="mt-6 grid gap-2 sm:grid-cols-2">
            {questions.map((question, index) => (
              <button key={question.id} type="button" onClick={() => { setCurrentIndex(index); setDone(false); }} className="flex items-center gap-3 rounded-lg border border-[var(--border)] p-3 text-left hover:bg-[var(--secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--interactive)]">
                {results[index] === true ? <CheckCircle2 className="text-[var(--success)]" /> : results[index] === false ? <XCircle className="text-[var(--error)]" /> : <CircleHelp className="text-[var(--interactive)]" />}
                <span className="min-w-0"><span className="block font-mono text-[9px] text-[var(--muted-foreground)]">题目 {index + 1}</span><span className="block truncate text-xs">{question.question}</span></span>
              </button>
            ))}
          </div>
          <Button onClick={restart} variant="outline" className="mx-auto mt-6 flex"><RotateCcw />重新开始</Button>
        </div>
      </section>
    );
  }

  const answered = currentQuestion.id in answers;
  const selectedAnswer = answers[currentQuestion.id];
  const result = answered ? grade(currentQuestion, selectedAnswer) : null;
  const draft = drafts[currentQuestion.id] ?? "";
  const submit = (value: string) => {
    if (!answered && value.trim()) setAnswers((current) => ({ ...current, [currentQuestion.id]: value }));
  };

  return (
    <section className="grid min-h-[34rem] lg:grid-cols-[13rem_minmax(0,1fr)]">
      <aside className="border-b border-[var(--border)] bg-[var(--secondary)]/25 p-3 lg:border-b-0 lg:border-r">
        <div className="flex items-center justify-between gap-2 px-1">
          <div><h3 className="flex items-center gap-2 text-sm font-semibold"><CircleHelp size={16} />小练习</h3><p className="mt-1 text-[10px] text-[var(--muted-foreground)]">{answeredCount} / {questions.length} 已作答</p></div>
          <span className="font-mono text-[10px] text-[var(--muted-foreground)]">得分 {correctCount}</span>
        </div>
        <div className="mt-3 flex gap-2 overflow-x-auto pb-2 lg:flex-col" aria-label="练习题目导航">
          {questions.map((question, index) => {
            const questionResult = results[index];
            const questionAnswered = question.id in answers;
            return (
              <button key={question.id} type="button" aria-label={`查看第 ${index + 1} 题`} aria-current={index === currentIndex ? "step" : undefined} disabled={!questionAnswered && index > currentIndex} onClick={() => setCurrentIndex(index)} className={cn(
                "flex min-w-36 items-center gap-2 rounded-lg border px-3 py-2.5 text-left outline-none transition-[border-color,background-color,transform] hover:-translate-y-0.5 focus-visible:ring-2 focus-visible:ring-[var(--interactive)] disabled:cursor-not-allowed disabled:opacity-45 lg:min-w-0",
                index === currentIndex ? "border-[var(--interactive)] bg-[var(--card)]" : "border-[var(--border)] bg-[var(--card)]/65",
              )}>
                <span className={cn("grid size-6 shrink-0 place-items-center rounded-full border font-mono text-[10px]", questionResult === true && "border-[var(--success)] bg-[var(--success)] text-[var(--card)]", questionResult === false && "border-[var(--error)] bg-[var(--error)] text-[var(--card)]", questionResult === null && "border-[var(--interactive)] bg-[var(--interactive)] text-[var(--card)]")}>
                  {questionAnswered ? questionResult === true ? <CheckCircle2 size={13} /> : questionResult === false ? <XCircle size={13} /> : <CircleHelp size={13} /> : index + 1}
                </span>
                <span><span className="block text-[10px] font-medium">第 {index + 1} 题</span><span className="block text-[9px] text-[var(--muted-foreground)]">{question.related_concept ?? "待作答"}</span></span>
              </button>
            );
          })}
        </div>
      </aside>

      <main className="min-w-0 bg-[var(--stage-bg)] p-3 sm:p-5">
        <div className="mx-auto max-w-3xl rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm sm:p-7">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex gap-2"><Badge variant="outline" className="font-mono text-[10px]">{currentIndex + 1} / {questions.length}</Badge><Badge variant="outline">{TYPES[currentQuestion.type]}</Badge>{currentQuestion.related_concept && <Badge variant="secondary">{currentQuestion.related_concept}</Badge>}</div>
            <span className="flex items-center gap-1 text-[10px] text-[var(--muted-foreground)]">难度 <Badge variant="secondary">{DIFFICULTY[currentQuestion.difficulty] ?? currentQuestion.difficulty}</Badge></span>
          </div>
          <div className="mt-4 flex gap-1" aria-label="答题进度">{questions.map((question, index) => <span key={question.id} className={cn("h-1.5 flex-1 rounded-full", index === currentIndex ? "bg-[var(--interactive)]" : question.id in answers ? "bg-[var(--success)]/70" : "bg-[var(--border)]")} />)}</div>
          <h4 className="mt-6 font-serif text-xl font-semibold leading-8">{currentQuestion.question}</h4>

          {currentQuestion.type === "multiple_choice" && currentQuestion.options && (
            <div className="mt-5 grid gap-2">{currentQuestion.options.map((option) => {
              const selected = selectedAnswer === option.id;
              const correct = answered && option.is_correct;
              const wrong = answered && selected && !option.is_correct;
              return <button key={option.id} onClick={() => submit(option.id)} disabled={answered} aria-pressed={selected} className={cn(
                "flex min-h-14 items-center gap-3 rounded-lg border px-4 py-3 text-left text-sm outline-none transition-[border-color,background-color,transform] hover:-translate-y-0.5 hover:border-[var(--interactive)] focus-visible:ring-2 focus-visible:ring-[var(--interactive)] disabled:cursor-default disabled:hover:translate-y-0",
                correct && "border-[var(--success)] bg-[color-mix(in_oklch,var(--success)_10%,var(--card))]", wrong && "border-[var(--error)] bg-[color-mix(in_oklch,var(--error)_9%,var(--card))]",
              )}><span className={cn("grid size-8 shrink-0 place-items-center rounded-full border font-mono text-xs", correct && "border-[var(--success)] bg-[var(--success)] text-[var(--card)]", wrong && "border-[var(--error)] bg-[var(--error)] text-[var(--card)]")}>{correct ? <CheckCircle2 size={15} /> : wrong ? <XCircle size={15} /> : option.id.toUpperCase()}</span><span>{option.text}</span></button>;
            })}</div>
          )}

          {currentQuestion.type === "true_false" && <div className="mt-5 grid grid-cols-2 gap-3">{[["true", "正确"], ["false", "错误"]].map(([value, label]) => <button key={value} disabled={answered} onClick={() => submit(value)} className={cn("flex min-h-20 items-center justify-center gap-2 rounded-lg border font-semibold hover:border-[var(--interactive)] hover:bg-[var(--secondary)]", answered && value === currentQuestion.correct_answer && "border-[var(--success)] text-[var(--success)]", answered && value === selectedAnswer && value !== currentQuestion.correct_answer && "border-[var(--error)] text-[var(--error)]")}>{value === "true" ? <CheckCircle2 /> : <XCircle />}{label}</button>)}</div>}

          {(currentQuestion.type === "fill_blank" || currentQuestion.type === "short_answer") && <div className="mt-5 space-y-3">
            {currentQuestion.type === "fill_blank" ? <input value={draft} onChange={(event) => setDrafts((current) => ({ ...current, [currentQuestion.id]: event.target.value }))} onKeyDown={(event) => { if (event.key === "Enter") submit(draft); }} disabled={answered} placeholder="请输入你的答案..." className="h-12 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-4 outline-none focus:border-[var(--interactive)] focus:ring-2 focus:ring-[var(--interactive)]/20" /> : <textarea value={draft} onChange={(event) => setDrafts((current) => ({ ...current, [currentQuestion.id]: event.target.value }))} disabled={answered} rows={5} placeholder="请输入你的答案..." className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-4 py-3 outline-none focus:border-[var(--interactive)] focus:ring-2 focus:ring-[var(--interactive)]/20" />}
            {!answered && <Button className="w-full" disabled={!draft.trim()} onClick={() => submit(draft)}>{currentQuestion.type === "short_answer" ? "提交答案（教师评阅）" : "提交答案"}</Button>}
          </div>}

          {answered && <div className={cn("mt-5 rounded-lg border p-4", result === true ? "border-[var(--success)] bg-[color-mix(in_oklch,var(--success)_9%,var(--card))]" : result === false ? "border-[var(--error)] bg-[color-mix(in_oklch,var(--error)_8%,var(--card))]" : "border-[var(--interactive)] bg-[color-mix(in_oklch,var(--interactive)_8%,var(--card))]")}>
            <p className={cn("flex items-center gap-2 text-sm font-semibold", result === true ? "text-[var(--success)]" : result === false ? "text-[var(--error)]" : "text-[var(--interactive)]")}>{result === true ? <><CheckCircle2 />回答正确！</> : result === false ? <><XCircle />回答错误</> : <><Lightbulb />已提交，请查看参考解析</>}</p>
            {!revealed[currentQuestion.id] ? <Button variant="ghost" size="sm" className="mt-2" onClick={() => setRevealed((current) => ({ ...current, [currentQuestion.id]: true }))}><Lightbulb />查看解析</Button> : <div className="mt-3 border-t border-[var(--border)] pt-3 text-sm leading-6"><p className="mb-1 flex items-center gap-1 text-xs font-semibold text-[var(--muted-foreground)]"><BookOpen />解析</p><p>{currentQuestion.explanation}</p>{currentQuestion.expected_keywords?.length ? <div className="mt-3 flex flex-wrap gap-1">{currentQuestion.expected_keywords.map((keyword) => <Badge key={keyword} variant="outline">{keyword}</Badge>)}</div> : null}</div>}
          </div>}

          <div className="mt-5 flex items-center justify-between border-t border-[var(--border)] pt-4">
            <Button variant="outline" size="sm" disabled={currentIndex === 0} onClick={() => setCurrentIndex((index) => index - 1)}><ChevronLeft />上一题</Button>
            {answered && <Button onClick={() => currentIndex < questions.length - 1 ? setCurrentIndex((index) => index + 1) : setDone(true)}>{currentIndex < questions.length - 1 ? <>下一题<ChevronRight /></> : <>查看结果<Trophy /></>}</Button>}
          </div>
        </div>
      </main>
    </section>
  );
}
