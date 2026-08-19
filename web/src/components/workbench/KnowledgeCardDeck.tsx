import { useEffect, useMemo, useState } from "react";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Layers3,
  Search,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { KnowledgeCard, type KnowledgeCardData } from "./KnowledgeCard";

export type KnowledgeCardDeckProps = {
  cards: KnowledgeCardData[];
  onFrameClick?: (frameId: string) => void;
  className?: string;
};

export function KnowledgeCardDeck({ cards, onFrameClick, className }: KnowledgeCardDeckProps) {
  const [selectedId, setSelectedId] = useState(cards[0]?.id);
  const [category, setCategory] = useState("全部");
  const [query, setQuery] = useState("");
  const [reviewedIds, setReviewedIds] = useState<Set<string>>(() => new Set());

  const categories = useMemo(
    () => ["全部", ...new Set(cards.map((card) => card.category).filter(Boolean) as string[])],
    [cards],
  );
  const visibleCards = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    return cards.filter((card) => {
      if (category !== "全部" && card.category !== category) return false;
      if (!normalizedQuery) return true;
      return [card.title, card.definition, card.intuition, ...(card.pitfalls ?? [])]
        .filter(Boolean)
        .some((value) => String(value).toLocaleLowerCase().includes(normalizedQuery));
    });
  }, [cards, category, query]);

  const selectedIndex = Math.max(0, visibleCards.findIndex((card) => card.id === selectedId));
  const selectedCard = visibleCards[selectedIndex];

  useEffect(() => {
    if (selectedCard || visibleCards.length === 0) return;
    setSelectedId(visibleCards[0]?.id);
  }, [selectedCard, visibleCards]);

  const moveTo = (index: number) => {
    const target = visibleCards[Math.min(Math.max(index, 0), visibleCards.length - 1)];
    if (target) setSelectedId(target.id);
  };

  if (cards.length === 0) {
    return <p className={cn("p-8 text-center text-sm text-[var(--muted-foreground)]", className)}>暂无知识卡片</p>;
  }

  return (
    <section
      className={cn("grid min-h-[34rem] gap-0 lg:grid-cols-[17rem_minmax(0,1fr)]", className)}
      tabIndex={0}
      onKeyDown={(event) => {
        if ((event.target as HTMLElement).closest("input, button, a")) return;
        if (event.key === "ArrowLeft") moveTo(selectedIndex - 1);
        if (event.key === "ArrowRight") moveTo(selectedIndex + 1);
      }}
    >
      <aside className="border-b border-[var(--border)] bg-[var(--secondary)]/25 p-3 lg:border-b-0 lg:border-r">
        <div className="flex items-center justify-between gap-2 px-1">
          <div>
            <h3 className="flex items-center gap-2 text-sm font-semibold"><Layers3 size={16} />知识卡片</h3>
            <p className="mt-1 text-[10px] text-[var(--muted-foreground)]">{reviewedIds.size} / {cards.length} 已阅读</p>
          </div>
          <span className="font-mono text-[10px] text-[var(--muted-foreground)]">{visibleCards.length}</span>
        </div>

        <label className="relative mt-3 block">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]" size={13} />
          <input
            aria-label="搜索知识卡片"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索概念"
            className="h-8 w-full rounded-md border border-[var(--border)] bg-[var(--background)] pl-8 pr-2 text-xs outline-none focus:border-[var(--interactive)] focus:ring-2 focus:ring-[color-mix(in_oklch,var(--interactive)_15%,transparent)]"
          />
        </label>

        <div className="mt-2 flex gap-1 overflow-x-auto pb-1 lg:flex-wrap" aria-label="知识卡片分类">
          {categories.map((item) => (
            <button
              key={item}
              type="button"
              aria-pressed={category === item}
              onClick={() => setCategory(item)}
              className={cn(
                "shrink-0 rounded-full border px-2 py-1 text-[10px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--interactive)]",
                category === item
                  ? "border-[var(--interactive)] bg-[var(--interactive)] text-[var(--card)]"
                  : "border-[var(--border)] bg-[var(--card)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]",
              )}
            >
              {item}
            </button>
          ))}
        </div>

        <div
          className="mt-3 flex gap-2 overflow-x-auto pb-2 lg:max-h-[27rem] lg:flex-col lg:overflow-y-auto lg:pb-0"
          aria-label="知识卡片目录"
          onWheel={(event) => {
            if (window.matchMedia("(min-width: 1024px)").matches) return;
            event.currentTarget.scrollLeft += event.deltaY;
          }}
        >
          {visibleCards.map((card, index) => (
            <button
              key={card.id}
              type="button"
              aria-label={`阅读卡片 ${index + 1}：${card.title}`}
              aria-pressed={selectedCard?.id === card.id}
              onClick={() => setSelectedId(card.id)}
              className={cn(
                "group min-w-48 rounded-lg border p-3 text-left outline-none transition-[border-color,box-shadow,transform] hover:-translate-y-0.5 focus-visible:ring-2 focus-visible:ring-[var(--interactive)] lg:min-w-0",
                selectedCard?.id === card.id
                  ? "border-[var(--interactive)] bg-[var(--card)] shadow-sm"
                  : "border-[var(--border)] bg-[var(--card)]/70 hover:border-[color-mix(in_oklch,var(--interactive)_45%,var(--border))]",
              )}
            >
              <span className="flex items-center justify-between gap-2">
                <span className="font-mono text-[9px] text-[var(--muted-foreground)]">CARD {String(index + 1).padStart(2, "0")}</span>
                {reviewedIds.has(card.id) && <Check size={13} className="text-[var(--success)]" aria-label="已阅读" />}
              </span>
              <span className="mt-1.5 block text-xs font-semibold leading-5">{card.title}</span>
              {card.category && <span className="mt-1 block text-[9px] text-[var(--muted-foreground)]">{card.category}</span>}
            </button>
          ))}
          {visibleCards.length === 0 && (
            <p className="p-4 text-center text-xs leading-5 text-[var(--muted-foreground)]">没有匹配的卡片</p>
          )}
        </div>
      </aside>

      <main className="min-w-0 bg-[var(--stage-bg)] p-3 sm:p-5">
        {selectedCard && (
          <div className="mx-auto flex h-full max-w-3xl flex-col">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="font-mono text-[10px]">{selectedIndex + 1} / {visibleCards.length}</Badge>
                {selectedCard.difficulty != null && (
                  <span className="text-[10px] text-[var(--muted-foreground)]">难度 {Math.max(1, Math.min(5, selectedCard.difficulty))} / 5</span>
                )}
              </div>
              <Button
                variant={reviewedIds.has(selectedCard.id) ? "secondary" : "outline"}
                size="sm"
                onClick={() => setReviewedIds((current) => {
                  const next = new Set(current);
                  if (next.has(selectedCard.id)) next.delete(selectedCard.id);
                  else next.add(selectedCard.id);
                  return next;
                })}
              >
                <Check />{reviewedIds.has(selectedCard.id) ? "已阅读" : "标记已阅读"}
              </Button>
            </div>

            <KnowledgeCard card={selectedCard} onFrameClick={onFrameClick} featured className="flex-1" />

            <div className="mt-3 flex items-center justify-between gap-3">
              <Button variant="outline" size="sm" disabled={selectedIndex === 0} onClick={() => moveTo(selectedIndex - 1)}>
                <ChevronLeft />上一张
              </Button>
              <div className="flex flex-1 gap-1" aria-label="卡片阅读进度">
                {visibleCards.map((card, index) => (
                  <button
                    key={card.id}
                    type="button"
                    aria-label={`跳转到卡片 ${index + 1}`}
                    onClick={() => setSelectedId(card.id)}
                    className={cn(
                      "h-1.5 flex-1 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--interactive)]",
                      card.id === selectedCard.id
                        ? "bg-[var(--interactive)]"
                        : reviewedIds.has(card.id) ? "bg-[var(--success)]/70" : "bg-[var(--border)]",
                    )}
                  />
                ))}
              </div>
              <Button variant="outline" size="sm" disabled={selectedIndex === visibleCards.length - 1} onClick={() => moveTo(selectedIndex + 1)}>
                下一张<ChevronRight />
              </Button>
            </div>
          </div>
        )}
      </main>
    </section>
  );
}

export default KnowledgeCardDeck;
