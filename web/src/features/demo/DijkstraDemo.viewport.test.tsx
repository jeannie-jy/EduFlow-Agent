import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const simulationGraphProps = vi.hoisted(() => [] as Array<{ compact?: boolean }>);

vi.mock("@/components/workbench/SimulationGraph", () => ({
  SimulationGraph: (props: { compact?: boolean }) => {
    simulationGraphProps.push({ compact: props.compact });
    return null;
  },
}));

import { DijkstraDemo } from "./DijkstraDemo";

describe("DijkstraDemo viewport behavior", () => {
  beforeEach(() => {
    simulationGraphProps.length = 0;
  });

  it("defers to SimulationGraph viewport compactness in full mode and forces it in compact mode", () => {
    const { unmount } = render(<DijkstraDemo />);
    expect(simulationGraphProps.at(-1)).toEqual({ compact: undefined });

    unmount();
    render(<DijkstraDemo compact />);
    expect(simulationGraphProps.at(-1)).toEqual({ compact: true });
  });
});
