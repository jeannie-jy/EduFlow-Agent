import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ProjectDetailResponse } from "@/services/projects";
import { SourceEvidencePanel } from "./SourceEvidencePanel";

function project(graph: Record<string, unknown>, scope = "open") {
  return {
    id: "project-1", title: "test", status: "done", audience: "undergraduate_cs",
    difficulty: "intermediate", teaching_plan: null, quality_report: null,
    module_outputs: null, selected_modules: null, frame_count: 0,
    created_at: "2026-09-30T00:00:00Z", updated_at: "2026-09-30T00:00:00Z",
    knowledge_graph: graph,
    dsl: { constraints: { knowledge_scope: scope } },
  } satisfies ProjectDetailResponse;
}

describe("SourceEvidencePanel", () => {
  it("shows material title, section locator and version without losing separate pages", () => {
    render(<SourceEvidencePanel project={project({ sources: [
      { source_id: "teacher-1", chunk_id: "page-2", title: "lecture.pdf",
        section: "搜索", locator: "page:2;char:0-80", version: "v1" },
      { source_id: "teacher-1", chunk_id: "page-9", title: "lecture.pdf",
        section: "搜索", locator: "page:9;char:0-50", version: "v1" },
    ] })} />);
    expect(screen.getAllByText(/lecture\.pdf/)).toHaveLength(2);
    expect(screen.getByText(/page:2/)).toBeInTheDocument();
    expect(screen.getByText(/page:9/)).toBeInTheDocument();
  });

  it("marks open model knowledge as uncited and strict missing evidence as insufficient", () => {
    const { rerender } = render(<SourceEvidencePanel project={project({ sources: [] })} />);
    expect(screen.getByText(/无检索来源/)).toBeInTheDocument();
    rerender(<SourceEvidencePanel project={project({ sources: [] }, "selected_materials")} />);
    expect(screen.getByText(/没有可核验的检索证据/)).toBeInTheDocument();
  });
});
