import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, Menu, X } from "lucide-react";
import { Link } from "react-router-dom";
import { EduFlowBrand } from "@/components/brand/EduFlowBrand";
import { ThemeSwitcher } from "@/components/layout/ThemeSwitcher";
import { cn } from "@/lib/utils";
import { landingNavigation } from "../landing-content";

type SiteHeaderProps = {
  isAuthenticated?: boolean;
};

export function SiteHeader({ isAuthenticated = false }: SiteHeaderProps) {
  const [hasScrolled, setHasScrolled] = useState(false);
  const [isNavigationOpen, setIsNavigationOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const mobileNavigationRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const updateSurface = () => setHasScrolled(window.scrollY > 24);
    updateSurface();
    window.addEventListener("scroll", updateSurface, { passive: true });
    return () => window.removeEventListener("scroll", updateSurface);
  }, []);

  useEffect(() => {
    if (!isNavigationOpen) return;

    mobileNavigationRef.current?.querySelector<HTMLAnchorElement>("a")?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setIsNavigationOpen(false);
      triggerRef.current?.focus();
    };

    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [isNavigationOpen]);

  const closeMobileNavigation = () => setIsNavigationOpen(false);

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
          {isAuthenticated ? (
            <Link to="/app" className="site-header__create">
              打开工作台 <ArrowUpRight aria-hidden="true" />
            </Link>
          ) : (
            <>
              <Link to="/login" className="site-header__login">登录</Link>
              <Link to="/app/project/_new" className="site-header__create">
                开始创建 <ArrowUpRight aria-hidden="true" />
              </Link>
            </>
          )}
          <button
            ref={triggerRef}
            type="button"
            className="site-header__menu-trigger"
            aria-label={isNavigationOpen ? "关闭导航" : "打开导航"}
            aria-controls="site-mobile-navigation"
            aria-expanded={isNavigationOpen}
            onClick={() => setIsNavigationOpen((open) => !open)}
          >
            {isNavigationOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
          </button>
        </div>
      </div>

      {isNavigationOpen && (
        <div className="site-header__mobile-surface">
          <nav ref={mobileNavigationRef} id="site-mobile-navigation" className="site-header__mobile-nav" aria-label="移动主导航">
            {landingNavigation.map((item) => (
              <a key={item.href} href={item.href} onClick={closeMobileNavigation}>{item.label}</a>
            ))}
            {isAuthenticated ? (
              <Link to="/app" className="site-header__mobile-create" onClick={closeMobileNavigation}>
                打开工作台 <ArrowUpRight aria-hidden="true" />
              </Link>
            ) : (
              <>
                <Link to="/login" onClick={closeMobileNavigation}>登录</Link>
                <Link to="/app/project/_new" className="site-header__mobile-create" onClick={closeMobileNavigation}>开始创建 <ArrowUpRight aria-hidden="true" /></Link>
              </>
            )}
          </nav>
        </div>
      )}
    </header>
  );
}
