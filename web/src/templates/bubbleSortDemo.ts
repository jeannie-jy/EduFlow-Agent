/**
 * 冒泡排序交互推演 — 沙箱模板。
 *
 * 在 SandboxRenderer 的 iframe 沙箱中运行（无 import、React 全局变量、Tailwind CDN）。
 * 布局与配色按项目既定规范：
 * - 容器：flex flex-col gap-4 p-4 bg-gray-50 rounded-xl border border-gray-200
 * - 可视化区：水平柱状图（flex flex-row items-end justify-center gap-2 h-48 w-full），
 *   高度按数值动态计算，比较中 bg-amber-500、已排序 bg-gray-400、默认 bg-teal-600
 * - 状态说明：高信息密度小卡片（bg-blue-50 text-blue-700），无图标
 * - 控制面板：按钮组，主操作 bg-gray-900 text-white，其余细边框按钮
 */

export const bubbleSortInteractiveDemo = `const InteractiveDemo = () => {
  // ── 数据：冒泡排序初始数组 ──
  const initialArray = [8, 4, 6, 2, 9, 1, 5, 3, 7];

  // ── 预计算完整步骤序列（比较/交换为独立帧，swap 帧保留交换前的快照以呈现平移动画）──
  const steps = React.useMemo(() => {
    const arr = initialArray.slice();
    const seq = [];
    seq.push({ type: "init", array: arr.slice(), compare: null, swap: null, sortedFrom: arr.length });
    for (let i = 0; i < arr.length - 1; i++) {
      for (let j = 0; j < arr.length - 1 - i; j++) {
        seq.push({ type: "compare", array: arr.slice(), compare: [j, j + 1], swap: null, sortedFrom: arr.length - i });
        if (arr[j] > arr[j + 1]) {
          seq.push({ type: "swap", array: arr.slice(), compare: [j, j + 1], swap: [j, j + 1], sortedFrom: arr.length - i });
          const tmp = arr[j];
          arr[j] = arr[j + 1];
          arr[j + 1] = tmp;
        }
      }
    }
    seq.push({ type: "done", array: arr.slice(), compare: null, swap: null, sortedFrom: 0 });
    return seq;
  }, []);

  const [stepIdx, setStepIdx] = React.useState(0);
  const [playing, setPlaying] = React.useState(false);

  const step = steps[stepIdx];
  const total = steps.length;
  const isFirst = stepIdx === 0;
  const isLast = stepIdx === total - 1;
  const sortedCount = step.array.length - step.sortedFrom;
  const unit = 56; // 柱宽 w-12(48px) + 间距 gap-2(8px)

  // ── 自动演示：定时推进，到末尾自动停止 ──
  React.useEffect(() => {
    if (!playing) return;
    const timer = setInterval(() => {
      setStepIdx(function (i) {
        return i >= steps.length - 1 ? i : i + 1;
      });
    }, 450);
    return function () { clearInterval(timer); };
  }, [playing, steps.length]);

  React.useEffect(() => {
    if (playing && stepIdx >= steps.length - 1) setPlaying(false);
  }, [playing, stepIdx, steps.length]);

  // ── 操作 ──
  const reset = function () { setPlaying(false); setStepIdx(0); };
  const prev = function () { setPlaying(false); setStepIdx(function (i) { return Math.max(0, i - 1); }); };
  const next = function () { setPlaying(false); setStepIdx(function (i) { return Math.min(steps.length - 1, i + 1); }); };
  const togglePlay = function () {
    if (isLast) setStepIdx(0);
    setPlaying(function (p) { return !p; });
  };

  // ── 当前步骤操作说明 ──
  const narration = (function () {
    if (step.type === "init") return "准备开始：从左到右逐对比较，较大的元素向右冒泡";
    if (step.type === "done") return "排序完成：数组已按升序排列";
    const a = step.compare[0];
    const b = step.compare[1];
    const x = step.array[a];
    const y = step.array[b];
    if (step.type === "compare") {
      return x > y ? "正在比较 " + x + " 和 " + y + "：" + x + " > " + y + "，需要交换"
                   : "正在比较 " + x + " 和 " + y + "：" + x + " ≤ " + y + "，顺序正确";
    }
    return "发生交换：" + x + " 与 " + y + " 互换位置";
  })();

  return (
    <div className="flex flex-col gap-4 p-4 bg-gray-50 rounded-xl border border-gray-200">
      {/* ── 状态说明区：高信息密度小卡片（无图标） ── */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-block px-3 py-1.5 bg-blue-50 text-blue-700 rounded-md text-sm font-medium">
          {narration}
        </span>
        <span className="ml-auto font-mono text-xs text-gray-500 tabular-nums">
          步骤 {stepIdx + 1} / {total}
        </span>
      </div>

      {/* ── 核心可视化区：水平柱状图（绝对禁止垂直文本列表） ── */}
      <div className="flex flex-row items-end justify-center gap-2 h-48 w-full overflow-x-auto">
        {step.array.map(function (value, idx) {
          const compareA = step.compare ? step.compare[0] : -1;
          const compareB = step.compare ? step.compare[1] : -1;
          const swapA = step.swap ? step.swap[0] : -1;
          const swapB = step.swap ? step.swap[1] : -1;
          const isCompare = idx === compareA || idx === compareB;
          const isSwapping = idx === swapA || idx === swapB;
          const isSorted = idx >= step.sortedFrom;

          // 交换平移动画（swap 帧，快照为交换前状态）
          let translateX = 0;
          if (isSwapping) {
            const other = idx === swapA ? swapB : swapA;
            translateX = (other - idx) * unit;
          }

          // 状态色：比较/交换中 amber 高亮，已排序 gray 静默，默认 teal
          const barColor = isSwapping || isCompare ? "bg-amber-500" : isSorted ? "bg-gray-400" : "bg-teal-600";

          return (
            <div
              key={idx}
              className={
                "w-12 rounded-t-md text-white flex flex-col items-center justify-between py-2 transition-all duration-300 " + barColor
              }
              style={{
                height: value * 16 + "px",
                transform: translateX !== 0 ? "translateX(" + translateX + "px)" : undefined,
              }}
            >
              <span className="font-mono text-sm font-semibold">{value}</span>
              <span className="font-mono text-[10px] text-white/70">索引{idx}</span>
            </div>
          );
        })}
      </div>

      {/* ── 控制面板：按钮组 ── */}
      <div className="flex flex-row justify-center gap-3 mt-4">
        <button
          onClick={reset}
          className="px-4 py-2 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100 transition-colors"
        >
          重置
        </button>
        <button
          onClick={prev}
          disabled={isFirst}
          className="px-4 py-2 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100 transition-colors disabled:opacity-40 disabled:pointer-events-none"
        >
          上一步
        </button>
        <button
          onClick={togglePlay}
          className="px-4 py-2 text-sm rounded-lg bg-gray-900 text-white hover:bg-gray-800 transition-colors"
        >
          {playing ? "暂停" : isLast ? "重播" : "自动演示"}
        </button>
        <button
          onClick={next}
          disabled={isLast}
          className="px-4 py-2 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100 transition-colors disabled:opacity-40 disabled:pointer-events-none"
        >
          下一步
        </button>
      </div>
    </div>
  );
};
`;
