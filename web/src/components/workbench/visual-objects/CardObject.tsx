/**
 * CardObject — 知识卡片可视化。
 * DSL VisualObject type="card"
 *
 * 复用 KnowledgeCard 组件进行渲染。
 */

import { memo } from "react";
import { KnowledgeCard, type KnowledgeCardData } from "../KnowledgeCard";
import type { DSLVisualObject } from "../simulation-model";

export type CardObjectProps = {
  object: DSLVisualObject;
  onFrameClick?: (frameId: string) => void;
  className?: string;
};

export const CardObject = memo(function CardObject({
  object,
  onFrameClick,
  className,
}: CardObjectProps) {
  const card: KnowledgeCardData = {
    id: object.id,
    title: (object.title as string) ?? (object.label as string) ?? "知识卡片",
    definition: (object.content as Record<string, string>)?.definition ?? "",
    intuition: (object.content as Record<string, string>)?.intuition ?? "",
    pitfalls: (object.content as Record<string, string[]>)?.pitfalls ?? [],
    formula: (object.content as Record<string, string>)?.formula,
    pseudocode: (object.content as Record<string, string>)?.pseudocode,
    relatedFrameIds: (object.related_frame_ids as string[]) ?? [],
    category: (object.category as string) ?? "",
    difficulty: (object.difficulty as number) ?? 3,
  };

  return (
    <KnowledgeCard
      card={card}
      onFrameClick={onFrameClick}
      className={className}
    />
  );
});

export default CardObject;
