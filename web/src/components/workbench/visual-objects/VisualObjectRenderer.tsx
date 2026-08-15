/**
 * VisualObjectRenderer — 根据 DSL VisualObject.type 分派到对应渲染组件。
 *
 * 覆盖全部 14 种 VisualObject 类型。
 */

import { memo } from "react";
import type { DSLVisualObject } from "../simulation-model";
import { NodeObject } from "./NodeObject";
import { EdgeObject } from "./EdgeObject";
import { ArrayObject } from "./ArrayObject";
import { LinkedListObject } from "./LinkedListObject";
import { TableObject } from "./TableObject";
import { CodeBlockObject } from "./CodeBlockObject";
import { FormulaObject } from "./FormulaObject";
import { MemoryBlockObject } from "./MemoryBlockObject";
import { ProcessObject } from "./ProcessObject";
import { TimelineObject } from "./TimelineObject";
import { CardObject } from "./CardObject";
import { MindmapObject } from "./MindmapObject";
import { StructureGraphObject } from "./StructureGraphObject";

export type VisualObjectRendererProps = {
  object: DSLVisualObject;
  /** 之前的值映射（用于 change detection） */
  previousValues?: Record<string, unknown>;
  onFrameClick?: (frameId: string) => void;
  interactionMode?: "browse" | "edit";
  selectedNodeId?: string;
  selectedCodeLine?: number;
  onNodeSelect?: (nodeId: string) => void;
  onCodeLineSelect?: (line: number) => void;
  className?: string;
};

function UnknownObject({ object }: { object: DSLVisualObject }) {
  const objType = object.type ?? "unknown";
  return (
    <div
      className="rounded border border-dashed border-muted-foreground/30 px-3 py-1.5 text-xs text-muted-foreground"
      aria-label={`未知对象类型: ${objType}`}
    >
      [{objType}] {object.label ?? object.id ?? "?"}
    </div>
  );
}

export const VisualObjectRenderer = memo(function VisualObjectRenderer({
  object,
  previousValues,
  onFrameClick,
  interactionMode = "browse",
  selectedNodeId,
  selectedCodeLine,
  onNodeSelect,
  onCodeLineSelect,
  className,
}: VisualObjectRendererProps) {
  const objType = object.type ?? "";

  switch (objType) {
    case "node":
      return <NodeObject object={object} className={className} />;

    case "edge":
      return <EdgeObject object={object} className={className} />;

    case "array":
      return (
        <ArrayObject
          object={object}
          previousValues={previousValues}
          className={className}
        />
      );

    case "linked_list":
      return <LinkedListObject object={object} className={className} />;

    case "tree":
    case "graph":
      return (
        <StructureGraphObject
          object={object}
          interactionMode={interactionMode}
          selectedNodeId={selectedNodeId}
          onNodeSelect={onNodeSelect}
          className={className ?? "h-72 w-full"}
        />
      );

    case "table":
      return <TableObject object={object} className={className} />;

    case "code_block":
      return (
        <CodeBlockObject
          object={object}
          selectedLine={selectedCodeLine}
          onLineSelect={onCodeLineSelect}
          className={className}
        />
      );

    case "formula":
      return <FormulaObject object={object} className={className} />;

    case "memory_block":
      return <MemoryBlockObject object={object} className={className} />;

    case "process":
      return <ProcessObject object={object} className={className} />;

    case "timeline":
      return <TimelineObject object={object} className={className} />;

    case "card":
      return (
        <CardObject
          object={object}
          onFrameClick={onFrameClick}
          className={className}
        />
      );

    case "mindmap":
      return <MindmapObject object={object} className={className} />;

    default:
      return <UnknownObject object={object} />;
  }
});

export default VisualObjectRenderer;
