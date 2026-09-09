import { Braces, GitBranch, Network, Play, Rows3, Share2, Workflow } from "lucide-react";
import { SandboxRenderer } from "@/components/workbench/SandboxRenderer";

type ExperienceKind = "network" | "hierarchy" | "sequence" | "collection" | "state" | "code" | "concept";

const EXPERIENCE_META: Record<ExperienceKind, {
  label: string;
  guidance: string;
  icon: typeof Network;
}> = {
  network: { label: "关系网络", guidance: "观察节点之间的连接、传播或路径变化", icon: Network },
  hierarchy: { label: "层级结构", guidance: "展开层级并比较父子关系与结构变化", icon: GitBranch },
  sequence: { label: "过程时序", guidance: "按步骤推进，观察参与者与信息如何流转", icon: Rows3 },
  collection: { label: "数据变化", guidance: "调整输入并逐步观察数据位置与状态变化", icon: Braces },
  state: { label: "状态演化", guidance: "触发事件，观察状态、条件和转移结果", icon: Workflow },
  code: { label: "代码执行", guidance: "修改参数或单步运行，联系代码与运行结果", icon: Play },
  concept: { label: "概念探索", guidance: "操作页面中的控件，从不同角度理解核心概念", icon: Share2 },
};

/**
 * Selects presentation language from topic semantics, never from a template id.
 * Generated interaction code remains authoritative; this layer provides a
 * consistent learning shell for built-in and user-created topics alike.
 */
export function inferExperienceKind(topic: string, code: string): ExperienceKind {
  const source = `${topic} ${code}`.toLowerCase();
  if (/graph|network|node|edge|路径|最短路|网络|拓扑|路由|关系图/.test(source)) return "network";
  if (/tree|heap|trie|hierarch|binary|avl|树|堆|层级|目录/.test(source)) return "hierarchy";
  if (/state|transition|process|schedule|lock|状态|流程|调度|事务|并发/.test(source)) return "state";
  if (/timeline|sequence|protocol|handshake|request|response|时序|协议|握手|生命周期|阶段/.test(source)) return "sequence";
  if (/array|sort|search|list|queue|stack|数组|排序|查找|队列|栈|链表/.test(source)) return "collection";
  if (/code|function|class|const |let |python|javascript|代码|函数|递归/.test(source)) return "code";
  return "concept";
}

export function InteractiveExperience({ code, topic = "当前知识主题" }: { code: string; topic?: string }) {
  const kind = inferExperienceKind(topic, code);
  const meta = EXPERIENCE_META[kind];
  const Icon = meta.icon;

  return (
    <section className="bg-[var(--background)] p-3 sm:p-5" data-experience-kind={kind}>
      <div className="mx-auto max-w-[1480px] overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-[0_18px_50px_color-mix(in_oklch,var(--foreground)_7%,transparent)]">
        <header className="flex flex-wrap items-center gap-3 border-b border-[var(--border)] bg-[color-mix(in_oklch,var(--card)_90%,var(--secondary))] px-4 py-3 sm:px-5">
          <span className="grid size-9 place-items-center rounded-xl bg-[var(--interactive)] text-[var(--card)] shadow-sm">
            <Icon size={18} aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-[var(--interactive)]">{meta.label}</p>
            <p className="truncate text-sm font-semibold text-[var(--foreground)]">{topic}</p>
          </div>
          <p className="w-full text-xs leading-5 text-[var(--muted-foreground)] sm:w-auto sm:max-w-md sm:text-right">{meta.guidance}</p>
        </header>
        <SandboxRenderer code={code} experienceKind={kind} />
      </div>
    </section>
  );
}
