/**
 * MindmapObject — 思维导图可视化。
 * DSL VisualObject type="mindmap"
 *
 * 复用 MindmapView 组件进行渲染。
 */

import { memo } from "react";
import { MindmapView, type MindmapNode } from "../MindmapView";
import type { DSLVisualObject } from "../simulation-model";

function toMindmapNode(value: unknown, fallbackId: string): MindmapNode {
  const source = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const children = Array.isArray(source.children) ? source.children : [];
  const relatedFrameIds = Array.isArray(source.relatedFrameIds ?? source.related_frame_ids)
    ? (source.relatedFrameIds ?? source.related_frame_ids) as unknown[]
    : [];
  return {
    id: String(source.id ?? fallbackId),
    name: String(source.name ?? source.label ?? "未命名概念"),
    type: source.type ? String(source.type) : undefined,
    relatedFrameIds: relatedFrameIds.map(String),
    children: children.map((child, index) => toMindmapNode(child, `${fallbackId}-${index + 1}`)),
  };
}

export type MindmapObjectProps = {
  object: DSLVisualObject;
  className?: string;
};

export const MindmapObject = memo(function MindmapObject({
  object,
  className,
}: MindmapObjectProps) {
  const rootSource = object.root && typeof object.root === "object"
    ? object.root
    : {
        id: object.id || "root",
        name: object.label ?? "思维导图",
        type: "definition",
        children: object.children,
      };
  const rootNode = toMindmapNode(rootSource, "root");

  return (
    <MindmapView
      root={rootNode}
      className={className}
    />
  );
});

export default MindmapObject;
