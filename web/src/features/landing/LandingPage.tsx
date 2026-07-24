import { HeroSection } from "./components/HeroSection";
import { SiteHeader } from "./components/SiteHeader";

export function LandingPage() {
  return (
    <div className="landing-page min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main>
        <HeroSection />
      </main>
    </div>
  );
}
