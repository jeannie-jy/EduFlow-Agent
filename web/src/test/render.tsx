import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
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

/**
 * 渲染页面组件（包含 MemoryRouter）
 */
export function renderPage(
  ui: ReactElement,
  route: string = "/",
  options?: Omit<RenderOptions, "wrapper">,
) {
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={[route]}>
        <AppProviders>{children}</AppProviders>
      </MemoryRouter>
    );
  }

  return render(ui, { wrapper: Wrapper, ...options });
}
