export interface UserFacingError {
  title: string;
  message: string;
  suggestion: string;
}

export type ErrorContext = "general" | "video";

/** Keep service details out of the learning UI while preserving an actionable cause. */
export function toUserFacingError(error: unknown, context: ErrorContext = "general"): UserFacingError {
  const raw = String(error ?? "").trim();
  const text = raw.toLowerCase();

  if (
    context === "video" &&
    /video_export_unavailable|video export is disabled|manim execution is disabled|isolated render worker|视频制作服务未启动/.test(text)
  ) {
    return {
      title: "视频制作服务未启动",
      message: "教学分镜已经生成完成，但本地视频 Worker 与隔离渲染沙箱尚未启动。",
      suggestion: "请使用视频开发模式启动服务后，再按当前设置开始制作。",
    };
  }

  if (/402|insufficient[ _-]?balance|余额|欠费|quota.*exceed|credit/.test(text)) {
    return {
      title: "智能生成额度不足",
      message: "当前接入的 AI 服务额度已用完，因此暂时无法生成这项成果。",
      suggestion: "请补充服务额度或更换可用的 AI 接入配置后重试。",
    };
  }
  if (/401|403|unauthori[sz]ed|forbidden|api.?key|鉴权|密钥/.test(text)) {
    return {
      title: "AI 服务接入未生效",
      message: "当前的 AI 服务密钥无效、已过期或没有访问权限。",
      suggestion: "请检查 AI 服务的接入配置后重试。",
    };
  }
  if (/429|rate.?limit|too many requests|限流|请求过多/.test(text)) {
    return {
      title: "AI 服务暂时繁忙",
      message: "短时间内生成请求较多，服务暂时无法继续处理。",
      suggestion: "请稍等片刻后重新生成。",
    };
  }
  if (/timeout|timed out|network|fetch|connection|503|502|504|网络|连接|超时/.test(text)) {
    return {
      title: "生成服务暂时无法连接",
      message: "应用暂时没有连接到内容生成服务，您的项目内容不会丢失。",
      suggestion: "请检查网络和服务状态，稍后重新生成。",
    };
  }
  if (/no frames|has no frames|缺少.*(推演|帧)|无.*帧/.test(text)) {
    return {
      title: "缺少推演脚本",
      message: "这个项目还没有可导出的逐帧推演内容，因此暂时无法制作视频。",
      suggestion: "请先重新生成推演脚本，再开始视频制作。",
    };
  }
  if (/render|compile|syntax|unexpected token|渲染|编译|脚本/.test(text)) {
    if (context === "video") {
      return {
        title: "视频渲染未完成",
        message: "视频脚本生成或隔离渲染阶段出现异常，已有教学成果不会丢失。",
        suggestion: "请重新开始制作；如果问题持续出现，请检查视频 Worker 日志。",
      };
    }
    return {
      title: "互动内容暂时无法展示",
      message: "这份互动内容的展示格式不完整，页面无法正常呈现。",
      suggestion: "请重新生成该成果；如果仍然失败，可调整主题描述后再试。",
    };
  }

  return {
    title: "这项成果暂时未生成成功",
    message: "生成过程中出现了异常，但其他已完成的成果仍可正常查看。",
    suggestion: "请点击“重新生成”；如果问题持续出现，请检查 AI 服务接入状态。",
  };
}
