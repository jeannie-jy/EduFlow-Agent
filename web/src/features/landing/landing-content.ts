export const landingNavigation = [
  { label: "产品原理", href: "/#product" },
  { label: "交互案例", href: "/#examples" },
  { label: "使用场景", href: "/#audiences" },
  { label: "模板库", href: "/#templates" },
] as const;

export const heroContent = {
  eyebrow: "AI 教学推演平台 / CHAPTER 01",
  title: "让抽象知识，变成可以亲手操控的推演",
  description: "从一个知识点出发，自动生成教学计划、逐帧动画、交互参数和可导出的教学内容。",
  nextHeading: "从一个问题，到一场完整推演",
} as const;

export const heroExamples = ["Dijkstra", "冒泡排序", "Round Robin"] as const;

export const processSteps = [
  ["理解知识", "识别学习目标、先修知识和常见误区"],
  ["规划教学", "安排从直觉、实例到总结的教学顺序"],
  ["生成推演", "把知识变化组织成连续、可操作的帧"],
  ["检查质量", "检查知识正确性、状态连续性和教学清晰度"],
  ["输出成果", "生成交互页面、讲解文本、字幕和视频"],
] as const;

export const templates = [
  ["Dijkstra", "图算法", "14 帧", "约 6 分钟"],
  ["冒泡排序", "数据结构", "12 帧", "约 4 分钟"],
  ["Round Robin", "操作系统", "16 帧", "约 7 分钟"],
] as const;

type TemplateName = (typeof templates)[number][0];

export type TemplatePreview = {
  objectType: string;
  label: string;
  before: string;
  focus: string;
  after: string;
};

export const templatePreviews: Record<TemplateName, TemplatePreview> = {
  Dijkstra: {
    objectType: "加权图",
    label: "Dijkstra 静态预览：节点 A 到 C 的距离从 ∞ 更新为 2",
    before: "A → C",
    focus: "dist(C): ∞ → 2",
    after: "边权 2",
  },
  冒泡排序: {
    objectType: "数组交换",
    label: "冒泡排序静态预览：5 与 3 交换后为 [3, 5, 8]",
    before: "[5, 3, 8]",
    focus: "5 ↔ 3",
    after: "[3, 5, 8]",
  },
  "Round Robin": {
    objectType: "进程队列",
    label: "Round Robin 静态预览：进程 B 在 2 ms 时间片后回到队尾",
    before: "A · B · C",
    focus: "B / 2 ms",
    after: "C · A · B",
  },
};
