import { Link } from "react-router-dom";

export function EduFlowBrand({ compact = false }: { compact?: boolean }) {
  return (
    <Link className="brand" to="/" aria-label="EduFlow 首页">
      <span className="brand__mark" aria-hidden="true">
        <img src="/brand/eduflow-mark.png" alt="" />
      </span>
      {!compact && <span className="brand__name">EduFlow</span>}
    </Link>
  );
}
