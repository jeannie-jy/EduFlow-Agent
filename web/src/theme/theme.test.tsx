import { render, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import indexHtml from "../../index.html?raw";
import { ThemeProvider, useTheme } from "./ThemeProvider";
import { themeScript } from "./theme-script";

function createMatchMedia(matches: boolean) {
  return (query: string) =>
    ({
      matches,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  window.matchMedia = createMatchMedia(false);
});

it("resolves system preference before explicit selection", () => {
  window.matchMedia = createMatchMedia(true);
  const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider });
  expect(result.current.preference).toBe("system");
  expect(result.current.resolvedTheme).toBe("dark");
  expect(document.documentElement.dataset.theme).toBe("dark");
});

it("persists an explicit Light selection", async () => {
  window.matchMedia = createMatchMedia(true);
  function Probe() {
    const { preference, resolvedTheme, setPreference } = useTheme();
    return (
      <>
        <span>{preference}:{resolvedTheme}</span>
        <button onClick={() => setPreference("light")}>Light</button>
      </>
    );
  }
  render(<ThemeProvider><Probe /></ThemeProvider>);
  await userEvent.click(screen.getByRole("button", { name: "Light" }));
  expect(screen.getByText("light:light")).toBeVisible();
  expect(localStorage.getItem("eduflow-theme")).toBe("light");
  expect(document.documentElement.dataset.theme).toBe("light");
});

it("keeps the pre-hydration script aligned with its exported source", () => {
  const inlineScript = indexHtml.match(/<script>([\s\S]*?)<\/script>/)?.[1] ?? "";
  const normalize = (value: string) => value.replace(/\s+/g, "");
  expect(normalize(inlineScript)).toBe(normalize(themeScript));
});
