import {
  InfoIcon,
  PauseIcon,
  PlayIcon,
  RotateCcwIcon,
  SkipBackIcon,
  SkipForwardIcon,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ButtonGroup } from "@/components/ui/button-group";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

const nodes = [
  { id: "A", distance: "0", x: 10, y: 52, state: "fixed" },
  { id: "B", distance: "2", x: 34, y: 20, state: "fixed" },
  { id: "C", distance: "3", x: 45, y: 52, state: "current" },
  { id: "D", distance: "6", x: 23, y: 82, state: "unvisited" },
  { id: "E", distance: "6", x: 70, y: 76, state: "unvisited" },
  { id: "F", distance: "4", x: 84, y: 35, state: "unvisited" },
] as const;

const edges = [
  { key: "ab", from: "A", to: "B", label: "2", left: 12, top: 49, width: 29, rotate: -38 },
  { key: "ac", from: "A", to: "C", label: "5", left: 13, top: 52, width: 30, rotate: 0 },
  { key: "ad", from: "A", to: "D", label: "9", left: 13, top: 55, width: 23, rotate: 48 },
  { key: "bc", from: "B", to: "C", label: "1", left: 36, top: 24, width: 28, rotate: 68 },
  { key: "bf", from: "B", to: "F", label: "2", left: 38, top: 21, width: 45, rotate: 16 },
  { key: "cd", from: "C", to: "D", label: "3", left: 28, top: 74, width: 24, rotate: -48 },
  { key: "ce", from: "C", to: "E", label: "3", left: 48, top: 55, width: 27, rotate: 34 },
  { key: "cf", from: "C", to: "F", label: "4", left: 49, top: 49, width: 35, rotate: -25 },
  { key: "de", from: "D", to: "E", label: "5", left: 27, top: 82, width: 43, rotate: -6 },
  { key: "ef", from: "E", to: "F", label: "1", left: 72, top: 72, width: 39, rotate: -66 },
];

const distanceRows = [
  { node: "A", distance: "0", previous: "—", status: "已确定" },
  { node: "B", distance: "2", previous: "A", status: "已确定" },
  { node: "C", distance: "3", previous: "B", status: "当前节点" },
  { node: "D", distance: "6", previous: "C", status: "未访问" },
  { node: "E", distance: "6", previous: "C", status: "未访问" },
  { node: "F", distance: "4", previous: "B", status: "未访问" },
];

const nodeStateLabels = {
  fixed: "已确定",
  current: "当前节点",
  unvisited: "未访问",
} as const;

function LegendDot({ state }: { state: (typeof nodes)[number]["state"] }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "size-2 rounded-full",
        state === "fixed" && "bg-primary",
        state === "current" && "bg-destructive",
        state === "unvisited" && "bg-muted-foreground",
      )}
    />
  );
}

export function SimulationPreview() {
  return (
    <section
      aria-labelledby="preview-heading"
      className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded-xl border bg-card md:col-span-2 xl:col-span-1"
    >
      <header className="flex flex-wrap items-start justify-between gap-3 border-b px-4 py-4">
        <div className="flex items-start gap-3">
          <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
            3
          </span>
          <div>
            <h2 id="preview-heading" className="font-semibold tracking-tight">
              互动预览
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              预览可讲、可停、可复盘的算法过程
            </p>
          </div>
        </div>
        <Badge variant="outline">步骤 3 / 14</Badge>
      </header>

      <div className="flex flex-1 flex-col gap-4 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold tracking-tight">Dijkstra 最短路径算法</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              当前选择距离最小的节点 C，并更新相邻节点。
            </p>
          </div>
          <div className="flex flex-wrap gap-2" aria-label="节点状态图例">
            <Badge variant="outline"><LegendDot state="fixed" />已确定</Badge>
            <Badge variant="outline"><LegendDot state="current" />当前节点</Badge>
            <Badge variant="outline"><LegendDot state="unvisited" />未访问</Badge>
          </div>
        </div>

        <div className="grid min-h-0 min-w-0 flex-1 gap-4 2xl:grid-cols-[minmax(0,1fr)_minmax(0,0.62fr)]">
          <figure className="relative min-h-80 min-w-0 overflow-hidden rounded-xl border bg-muted/20">
            <figcaption className="sr-only">
              六节点 Dijkstra 演示图，节点 C 为当前节点
            </figcaption>
            <ol className="absolute inset-4" aria-label="Dijkstra 六节点图">
              {edges.map((edge) => (
                <li
                  key={edge.key}
                  aria-label={`边 ${edge.from} 到 ${edge.to}，权重 ${edge.label}`}
                  className="absolute h-px origin-left bg-border"
                  style={{
                    left: `${edge.left}%`,
                    top: `${edge.top}%`,
                    width: `${edge.width}%`,
                    transform: `rotate(${edge.rotate}deg)`,
                  }}
                >
                  <span className="absolute -top-5 left-1/2 rounded bg-card px-1 text-xs tabular-nums text-muted-foreground">
                    {edge.label}
                  </span>
                </li>
              ))}
              {nodes.map((node) => (
                <li
                  key={node.id}
                  aria-label={`节点 ${node.id}，${nodeStateLabels[node.state]}，距离 ${node.distance}`}
                  className={cn(
                    "absolute flex size-12 -translate-x-1/2 -translate-y-1/2 flex-col items-center justify-center rounded-full border-2 text-sm font-semibold shadow-sm",
                    node.state === "fixed" && "border-primary bg-primary text-primary-foreground",
                    node.state === "current" && "border-destructive bg-destructive text-white",
                    node.state === "unvisited" && "border-border bg-card text-card-foreground",
                  )}
                  style={{ left: `${node.x}%`, top: `${node.y}%` }}
                >
                  <span>{node.id}</span>
                  <span className="text-[0.65rem] font-normal">{node.distance}</span>
                </li>
              ))}
            </ol>
          </figure>

          <div className="min-w-0 overflow-hidden rounded-xl border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>节点</TableHead>
                  <TableHead>距离</TableHead>
                  <TableHead>前驱</TableHead>
                  <TableHead>状态</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {distanceRows.map((row) => (
                  <TableRow key={row.node} data-state={row.node === "C" ? "selected" : undefined}>
                    <TableCell className="font-medium">{row.node}</TableCell>
                    <TableCell className="tabular-nums">{row.distance}</TableCell>
                    <TableCell>{row.previous}</TableCell>
                    <TableCell>{row.status}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <ButtonGroup aria-label="演示播放控制">
            <Button type="button" variant="outline" size="icon" aria-label="上一步">
              <SkipBackIcon />
            </Button>
            <Button type="button" size="icon" aria-label="播放演示">
              <PlayIcon />
            </Button>
            <Button type="button" variant="outline" size="icon" aria-label="下一步">
              <SkipForwardIcon />
            </Button>
          </ButtonGroup>
          <Progress value={24} aria-label="演示进度" className="min-w-40 flex-1" />
          <Button type="button" variant="outline" size="sm">
            <RotateCcwIcon data-icon="inline-start" />
            重置
          </Button>
          <Button type="button" variant="ghost" size="sm">
            <PauseIcon data-icon="inline-start" />
            暂停点
          </Button>
        </div>

        <Alert>
          <InfoIcon />
          <AlertTitle>本步更新规则</AlertTitle>
          <AlertDescription>
            若 dist[C] + w(C, v) &lt; dist[v]，则更新 dist[v] 与前驱。本步将 D 与 E 的距离更新为 6；F 通过 B 保持为 4。
          </AlertDescription>
        </Alert>
      </div>
    </section>
  );
}
