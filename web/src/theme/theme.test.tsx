import { act, renderHook } from "@testing-library/react";
import indexHtml from "../../index.html?raw";
import { ThemeProvider, useTheme } from "./ThemeProvider";
import { themeScript } from "./theme-script";

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
});

it("defaults a light system to canvas", () => {
  const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider });
  expect(result.current.theme).toBe("canvas");
});

it("persists a selected theme without replacing children", () => {
  const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider });
  act(() => result.current.setTheme("dawn"));
  expect(localStorage.getItem("eduflow-theme")).toBe("dawn");
  expect(document.documentElement.dataset.theme).toBe("dawn");
});

it("keeps the pre-hydration script aligned with its exported source", () => {
  const inlineScript = indexHtml.match(/<script>([\s\S]*?)<\/script>/)?.[1] ?? "";
  const normalize = (value: string) => value.replace(/\s+/g, "");
  expect(normalize(inlineScript)).toBe(normalize(themeScript));
});
