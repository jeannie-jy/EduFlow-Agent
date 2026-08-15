import { describe, expect, it } from "vitest";
import { describeFrameChanges, normalizeFramesArtifact } from "./artifact-model";

describe("artifact-model", () => {
  it("normalizes legacy frame outputs and fills safe defaults", () => {
    const artifact = normalizeFramesArtifact({
      frames: [{ title: "初始化", visual_objects: [], state_snapshot: { step: 1 } }],
    });

    expect(artifact.schema_version).toBe("1.0");
    expect(artifact.frames[0]).toMatchObject({
      frame_id: "f_001",
      title: "初始化",
      narration: "",
      checks: [],
    });
  });

  it("describes snapshot and visual-object changes", () => {
    const [previous, current] = normalizeFramesArtifact({
      frames: [
        {
          frame_id: "f_001",
          title: "前一步",
          state_snapshot: { distance: 4 },
          visual_objects: [{ id: "arr", type: "array", cells: [{ value: 4 }] }],
        },
        {
          frame_id: "f_002",
          title: "当前步",
          state_snapshot: { distance: 2 },
          visual_objects: [{ id: "arr", type: "array", cells: [{ value: 2 }] }],
        },
      ],
    }).frames;

    expect(describeFrameChanges(previous, current)).toEqual(
      expect.arrayContaining(["distance：2", "arr 已更新"]),
    );
  });

  it("normalizes generated parameters for the experiment panel", () => {
    const artifact = normalizeFramesArtifact({
      parameters: [{ key: "speed", label: "速度", type: "number", default: 2, constraints: { min: 1 } }],
      frames: [],
    });

    expect(artifact.parameters[0]).toMatchObject({
      key: "speed",
      param_type: "number",
      current_value: 2,
      constraints: { min: 1 },
    });
  });
});
