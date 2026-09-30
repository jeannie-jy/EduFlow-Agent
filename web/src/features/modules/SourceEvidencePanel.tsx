import type { ProjectDetailResponse } from "@/services/projects";

type EvidenceSource = {
  source_id: string;
  title: string;
  scope?: string;
  version?: string;
  section?: string;
  locator?: string;
  source_url?: string;
  chunk_id?: string;
};

function sourcesFromProject(project: ProjectDetailResponse | null): EvidenceSource[] {
  const raw = project?.knowledge_graph?.sources;
  if (!Array.isArray(raw)) return [];
  return raw.filter((item): item is EvidenceSource => (
    item !== null && typeof item === "object"
    && typeof item.source_id === "string"
    && typeof item.title === "string"
  )).slice(0, 20);
}

export function SourceEvidencePanel({ project }: { project: ProjectDetailResponse | null }) {
  const sources = sourcesFromProject(project);
  const constraints = project?.dsl?.constraints;
  const selectedOnly = constraints && typeof constraints === "object"
    && (constraints as Record<string, unknown>).knowledge_scope === "selected_materials";
  if (sources.length === 0 && !project?.knowledge_graph) return null;

  return (
    <section aria-label="教学来源" className="border-b border-[var(--border)] bg-[var(--card)] px-4 py-3 text-xs">
      <h3 className="font-semibold">教学来源</h3>
      {sources.length === 0 ? (
        <p className="mt-1 text-[var(--muted-foreground)]">
          {selectedOnly
            ? "指定资料没有可核验的检索证据，请补充或重新索引资料。"
            : "无检索来源；基础讲解来自模型知识，需由教师核对。"}
        </p>
      ) : (
        <ul className="mt-2 space-y-1">
          {sources.map((source, index) => {
            const location = [source.section, source.locator].filter(Boolean).join(" · ");
            const safeUrl = source.source_url?.startsWith("https://") ? source.source_url : null;
            return (
              <li key={`${source.chunk_id || source.source_id}-${source.locator || index}`}>
                <span className="font-medium">{source.title}</span>
                {location && <span> · {location}</span>}
                {source.version && <span> · 版本 {source.version}</span>}
                {safeUrl && <a className="ml-1 underline" href={safeUrl} target="_blank" rel="noopener noreferrer">原文</a>}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
