import { ArrowRight, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { EduFlowBrand } from "../components/brand/EduFlowBrand";

export function AppEntryPlaceholder() {
  return (
    <main className="entry-page"><EduFlowBrand /><div className="entry-card"><span><Sparkles /></span><p>账号体验已准备好</p><h1>准备开始一次新的推演</h1><p>完整教学工作台将在下一阶段接入。现在可以返回首页继续浏览产品能力。</p><Link className="button" to="/">返回首页 <ArrowRight size={18} /></Link></div></main>
  );
}
