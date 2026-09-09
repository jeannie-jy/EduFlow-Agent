import type { DSLVisualObject } from "@/components/workbench/simulation-model";

export type ArtifactCheck = {
  type?: string;
  message?: string;
  passed?: boolean;
  [key: string]: unknown;
};

export type ArtifactFrame = {
  frame_id: string;
  title: string;
  learning_goal?: string;
  narration: string;
  visual_objects: DSLVisualObject[];
  state_snapshot: Record<string, unknown>;
  animations: Array<Record<string, unknown>>;
  interaction_hooks: Array<Record<string, unknown>>;
  checks: ArtifactCheck[];
  duration_ms?: number;
  is_locked?: boolean;
  depends_on_parameters?: string[];
};

export type ArtifactParameter = {
  id?: string;
  key: string;
  label: string;
  param_type: string;
  default_value: unknown;
  current_value: unknown;
  constraints: Record<string, unknown>;
  recompute_scope: string;
  affects_frame_ids?: string[];
};

export type FramesArtifact = {
  schema_version: string;
  artifact_version?: string;
  frames: ArtifactFrame[];
  parameters: ArtifactParameter[];
};

export type VideoArtifact = {
  schema_version?: string;
  source_frames_version?: string;
  job_id?: string;
  status?: string;
  message?: string;
  config?: Record<string, unknown>;
};

const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};

const asRecordArray = (value: unknown): Array<Record<string, unknown>> =>
  Array.isArray(value) ? value.map(asRecord) : [];

export function normalizeFramesArtifact(value: unknown): FramesArtifact {
  const source = asRecord(value);
  const frames = asRecordArray(source.frames).map((frame, index): ArtifactFrame => ({
    frame_id: String(frame.frame_id ?? `f_${String(index + 1).padStart(3, "0")}`),
    title: String(frame.title ?? `步骤 ${index + 1}`),
    learning_goal: frame.learning_goal ? String(frame.learning_goal) : undefined,
    narration: String(frame.narration ?? ""),
    visual_objects: Array.isArray(frame.visual_objects)
      ? (frame.visual_objects as DSLVisualObject[])
      : [],
    state_snapshot: asRecord(frame.state_snapshot),
    animations: asRecordArray(frame.animations),
    interaction_hooks: asRecordArray(frame.interaction_hooks),
    checks: asRecordArray(frame.checks) as ArtifactCheck[],
    duration_ms: typeof frame.duration_ms === "number" ? frame.duration_ms : undefined,
    is_locked: Boolean(frame.is_locked),
    depends_on_parameters: Array.isArray(frame.depends_on_parameters)
      ? frame.depends_on_parameters.map(String)
      : [],
  }));

  const parameters = asRecordArray(source.parameters).map((parameter): ArtifactParameter => ({
    id: parameter.id ? String(parameter.id) : undefined,
    key: String(parameter.key ?? ""),
    label: String(parameter.label ?? parameter.key ?? "参数"),
    param_type: String(parameter.param_type ?? parameter.type ?? "number"),
    default_value: parameter.default_value ?? parameter.default,
    current_value: parameter.current_value ?? parameter.default_value ?? parameter.default,
    constraints: asRecord(parameter.constraints),
    recompute_scope: String(parameter.recompute_scope ?? "all_frames"),
    affects_frame_ids: Array.isArray(parameter.affects_frame_ids)
      ? parameter.affects_frame_ids.map(String)
      : [],
  })).filter((parameter) => parameter.key);

  return {
    schema_version: String(source.schema_version ?? "1.0"),
    artifact_version: source.artifact_version ? String(source.artifact_version) : undefined,
    frames,
    parameters,
  };
}

export function normalizeVideoArtifact(value: unknown): VideoArtifact {
  const source = asRecord(value);
  return {
    schema_version: source.schema_version ? String(source.schema_version) : undefined,
    source_frames_version: source.source_frames_version
      ? String(source.source_frames_version)
      : undefined,
    job_id: source.job_id ? String(source.job_id) : undefined,
    status: source.status ? String(source.status) : undefined,
    message: source.message ? String(source.message) : undefined,
    config: asRecord(source.config),
  };
}

export function formatSnapshotValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export function describeFrameChanges(
  previous: ArtifactFrame | undefined,
  current: ArtifactFrame,
): string[] {
  if (!previous) return ["建立初始状态"];

  const keys = new Set([
    ...Object.keys(previous.state_snapshot),
    ...Object.keys(current.state_snapshot),
  ]);
  const changes = [...keys]
    .filter(
      (key) =>
        formatSnapshotValue(previous.state_snapshot[key]) !==
        formatSnapshotValue(current.state_snapshot[key]),
    )
    .map((key) => `${key}：${formatSnapshotValue(current.state_snapshot[key])}`);

  const previousObjects = new Map(
    previous.visual_objects.map((object) => [object.id, formatSnapshotValue(object)]),
  );
  const changedObjects = current.visual_objects
    .filter((object) => previousObjects.get(object.id) !== formatSnapshotValue(object))
    .map((object) => `${object.label ?? object.id} 已更新`);

  return [...changes, ...changedObjects].slice(0, 8);
}
