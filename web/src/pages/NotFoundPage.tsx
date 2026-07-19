import { Link } from "react-router-dom";
import { EduFlowBrand } from "../components/brand/EduFlowBrand";

export function NotFoundPage() {
  return <main className="not-found"><EduFlowBrand /><p>404</p><h1>这一页还没有被编排</h1><Link className="button" to="/">回到首页</Link></main>;
}
