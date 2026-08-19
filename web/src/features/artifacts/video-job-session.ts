import type { ExportArtifact, ExportManimRequest } from "@/services/export";

export type VideoJobSession = {
  jobId: string;
  status: string;
  progress: number;
  artifacts: ExportArtifact[];
  error: string | null;
  config: ExportManimRequest;
  sourceFramesVersion?: string;
};

const keyFor = (projectId: string) => `eduflow:video-job:${projectId}`;

export function loadVideoJobSession(projectId?: string): VideoJobSession | null {
  if (!projectId || typeof window === "undefined") return null;
  try {
    const value = JSON.parse(window.localStorage.getItem(keyFor(projectId)) ?? "null") as VideoJobSession | null;
    return value?.jobId ? value : null;
  } catch {
    return null;
  }
}

export function saveVideoJobSession(projectId: string | undefined, session: VideoJobSession) {
  if (!projectId || typeof window === "undefined") return;
  try {
    window.localStorage.setItem(keyFor(projectId), JSON.stringify(session));
  } catch {
    // Storage can be unavailable in private browsing. Polling still works
    // while the component remains mounted.
  }
}
