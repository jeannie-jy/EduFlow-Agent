import { AudienceSection } from "./components/AudienceSection";
import { CapabilitySection } from "./components/CapabilitySection";
import { FinalActionSection } from "./components/FinalActionSection";
import { HeroSection } from "./components/HeroSection";
import { HowItWorksSection } from "./components/HowItWorksSection";
import { SiteHeader } from "./components/SiteHeader";
import { TemplateSection } from "./components/TemplateSection";

export function LandingPage() {
  return (
    <div className="landing-page min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main>
        <HeroSection />
        <HowItWorksSection />
        <AudienceSection />
        <CapabilitySection />
        <TemplateSection />
        <FinalActionSection />
      </main>
      <footer className="landing-footer">
        <p><strong>EduFlow</strong><span>AI 教学推演平台</span></p>
        <p>© 2026 EduFlow. 让知识的变化，有据可循。</p>
      </footer>
    </div>
  );
}
