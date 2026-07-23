import { render, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
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

it("defaults to the light theme regardless of system preference", () => {
  const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider });
  expect(result.current.theme).toBe("light");
});

it("persists a selected theme without replacing children", async () => {
  function StatefulThemeProbe() {
    const { setTheme } = useTheme();
    const [edits, setEdits] = useState(0);

    return (
      <>
        <button onClick={() => setEdits((count) => count + 1)}>编辑草稿</button>
        <button onClick={() => setTheme("dark")}>切换到深色</button>
        <span>草稿编辑次数：{edits}</span>
      </>
    );
  }

  render(
    <ThemeProvider>
      <StatefulThemeProbe />
    </ThemeProvider>,
  );

  await userEvent.click(screen.getByRole("button", { name: "编辑草稿" }));
  const stateNode = screen.getByText("草稿编辑次数：1");
  await userEvent.click(screen.getByRole("button", { name: "切换到深色" }));

  expect(screen.getByText("草稿编辑次数：1")).toBe(stateNode);
  expect(localStorage.getItem("eduflow-theme")).toBe("dark");
  expect(document.documentElement.dataset.theme).toBe("dark");
});

it("keeps the pre-hydration script aligned with its exported source", () => {
  const inlineScript = indexHtml.match(/<script>([\s\S]*?)<\/script>/)?.[1] ?? "";
  const normalize = (value: string) => value.replace(/\s+/g, "");
  expect(normalize(inlineScript)).toBe(normalize(themeScript));
});
