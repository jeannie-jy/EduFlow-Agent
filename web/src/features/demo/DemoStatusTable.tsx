import { graphNodeIds, getDistanceLabel, type SimulationFrame } from "@/components/workbench/simulation-model";
import { cn } from "@/lib/utils";

type DemoStatusTableProps = {
  frame: SimulationFrame;
};

export function DemoStatusTable({ frame }: DemoStatusTableProps) {
  return (
    <section aria-labelledby="demo-distance-table-title" className="demo-status-table paper-surface">
      <div className="demo-status-table__heading">
        <p className="demo-eyebrow">实时状态</p>
        <h3 id="demo-distance-table-title">距离表（从 A 出发）</h3>
      </div>
      <table>
        <thead>
          <tr>
            <th scope="col">节点</th>
            <th scope="col">当前距离</th>
            <th scope="col">上一步</th>
          </tr>
        </thead>
        <tbody>
          {graphNodeIds.map((node) => {
            const changed = frame.changedEdges.some((edge) => edge.endsWith(node) || edge.startsWith(`${node}-`));
            const predecessor = frame.predecessors[node];

            return (
              <tr key={`${frame.id}-${node}`} aria-current={frame.currentNode === node ? "step" : undefined}>
                <th scope="row">{node}</th>
                <td className={cn("demo-status-table__distance", changed && "is-changed")}>{getDistanceLabel(frame.distances[node])}</td>
                <td>{predecessor ? `${predecessor} → ${node}` : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
