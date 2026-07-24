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
