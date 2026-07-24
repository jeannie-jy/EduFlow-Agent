import { useEffect, useState } from "react";
import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import { EduFlowBrand } from "@/components/brand/EduFlowBrand";
import { ThemeSwitcher } from "@/components/layout/ThemeSwitcher";
import { cn } from "@/lib/utils";
import { landingNavigation } from "../landing-content";

export function SiteHeader() {
  const [hasScrolled, setHasScrolled] = useState(false);

  useEffect(() => {
    const updateSurface = () => setHasScrolled(window.scrollY > 24);
    updateSurface();
    window.addEventListener("scroll", updateSurface, { passive: true });
    return () => window.removeEventListener("scroll", updateSurface);
  }, []);

  return (
    <header className={cn("site-header", hasScrolled && "site-header--scrolled")}>
      <div className="site-header__inner">
        <Link to="/" aria-label="EduFlow 首页" className="site-header__brand">
          <EduFlowBrand />
        </Link>

        <nav className="site-header__nav" aria-label="主导航">
          {landingNavigation.map((item) => (
            <a key={item.href} href={item.href}>
              {item.label}
            </a>
          ))}
        </nav>

        <div className="site-header__actions">
          <ThemeSwitcher />
          <Link to="/login" className="site-header__login">登录</Link>
          <Link to="/app/new" className="site-header__create">
            开始创建 <ArrowUpRight aria-hidden="true" />
          </Link>
        </div>
      </div>
    </header>
  );
}
