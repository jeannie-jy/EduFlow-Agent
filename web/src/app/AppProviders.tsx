import type { PropsWithChildren } from "react";
import { MotionConfig } from "motion/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/theme/ThemeProvider";
import { AuthProvider } from "@/lib/auth";

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <AuthProvider>
      <ThemeProvider>
        <MotionConfig reducedMotion="user">
          <TooltipProvider>{children}</TooltipProvider>
        </MotionConfig>
      </ThemeProvider>
    </AuthProvider>
  );
}
