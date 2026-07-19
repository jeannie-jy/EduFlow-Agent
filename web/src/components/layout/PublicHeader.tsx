import { Menu, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { EduFlowBrand } from "../brand/EduFlowBrand";

export function PublicHeader() {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

  return (
    <header className="public-header">
      <div className="public-header__inner">
        <EduFlowBrand />
        <button
          className="nav-toggle"
          type="button"
          aria-label={open ? "关闭导航" : "打开导航"}
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <X /> : <Menu />}
        </button>
        <nav className={`public-nav${open ? " public-nav--open" : ""}`} aria-label="公开导航">
          <a href="#capabilities" onClick={close}>产品能力</a>
          <a href="#how-it-works" onClick={close}>工作方式</a>
          <a href="#scenarios" onClick={close}>使用场景</a>
        </nav>
        <div className={`header-actions${open ? " header-actions--open" : ""}`}>
          <Link className="header-login" to="/login" onClick={close}>登录</Link>
          <Link className="button button--small" to="/register" onClick={close}>免费开始</Link>
        </div>
      </div>
    </header>
  );
}
