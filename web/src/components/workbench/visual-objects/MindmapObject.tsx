/**
 * MindmapObject — 思维导图可视化。
 * DSL VisualObject type="mindmap"
 *
 * 复用 MindmapView 组件进行渲染。
 */

import { memo } from "react";
import { MindmapView, type MindmapNode } from "../MindmapView";
import type { DSLVisualObject } from "../simulation-model";

export type MindmapObjectProps = {
  object: DSLVisualObject;
  className?: string;
};

export const MindmapObject = memo(function MindmapObject({
  object,
  className,
}: MindmapObjectProps) {
  const root = (object.root as Record<string, unknown>) ?? {};
  const children = (object.children as Record<string, unknown>[]) ?? [];

  const rootNode: MindmapNode = {
    id: root.id as string ?? "root",
    name: root.name as string ?? object.label ?? "思维导图",
    type: root.type as string ?? "definition",
    children: children.map((c) => ({
      id: c.id as string ?? "",
      name: c.name as string ?? "",
      type: c.type as string ?? "",
    })),
  };

  return (
    <MindmapView
      root={rootNode}
      className={className}
    />
  );
});

export default MindmapObject;
