import { Link } from "react-router-dom";

function LegalLayout({ title, children }: { title: string; children: React.ReactNode }) {
  return <main className="mx-auto max-w-3xl px-6 py-12 text-foreground">
    <Link to="/" className="text-sm text-primary">← 返回 EduFlow</Link>
    <h1 className="mt-6 text-3xl font-semibold">{title}</h1>
    <p className="mt-2 text-sm text-muted-foreground">版本：2026-09-14 · 正式上线前须经适用法域的专业法律审查</p>
    <div className="mt-8 space-y-6 text-sm leading-7">{children}</div>
  </main>;
}

export function PrivacyPage() {
  return <LegalLayout title="隐私说明">
    <section><h2 className="text-lg font-medium">我们处理什么</h2><p>服务会处理账户资料、教学主题、项目内容、用户主动上传的材料、生成产物、模型调用用量、安全日志和审计记录。用户的供应商 API Key 以加密形式保存，接口不会返回明文。</p></section>
    <section><h2 className="text-lg font-medium">第三方模型处理</h2><p>执行生成时，教学主题、提示内容以及用户明确选入上下文的材料片段会发送至用户选择的 DeepSeek 或阿里百炼账户。供应商对这些数据的处理同时受用户与该供应商之间的条款约束。</p></section>
    <section><h2 className="text-lg font-medium">密钥边界</h2><p>密钥通过 HTTPS 提交并在服务端进行信封加密。为代表用户调用模型，受授权的 API 或 Worker 可在内存中短暂解密，因此该设计不是端到端加密。解析和视频执行沙箱不持有密钥解密权限。</p></section>
    <section><h2 className="text-lg font-medium">保留与权利</h2><p>上传材料默认保留 30 天，安全审计默认保留 90 天。项目和产物在账户有效期间保存，用户可在账户设置导出数据或申请注销；注销有 7 天冷静期，随后会删除数据库记录、对象存储产物、缓存和待执行任务（受法律要求保留的不可变审计归档除外）。</p></section>
  </LegalLayout>;
}

export function TermsPage() {
  return <LegalLayout title="服务条款摘要">
    <section><h2 className="text-lg font-medium">自带模型账户</h2><p>用户自行提供 DeepSeek 或阿里百炼 API Key，并直接承担供应商产生的模型费用。EduFlow 展示的 Token 和金额仅是本系统内的参考估算，供应商账单为最终依据。</p></section>
    <section><h2 className="text-lg font-medium">合理使用</h2><p>不得利用服务访问他人数据、绕过配额、传播恶意文件或尝试突破运行沙箱。平台可对异常账户暂停生成、上传或视频能力。</p></section>
    <section><h2 className="text-lg font-medium">生成内容</h2><p>AI 生成内容可能不准确，不应直接替代教师审核。用户应确认其上传材料和发布内容具有必要授权。</p></section>
  </LegalLayout>;
}
