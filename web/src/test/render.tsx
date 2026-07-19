import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { AppProviders } from "@/app/AppProviders";

function TestProviders({ children }: { children: ReactNode }) {
  return <AppProviders>{children}</AppProviders>;
}

export function renderWithProviders(
  ui: ReactElement,
  options?: Omit<RenderOptions, "wrapper">,
) {
  return render(ui, { wrapper: TestProviders, ...options });
}
