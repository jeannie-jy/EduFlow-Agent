export const THEMES = [
  { id: "dawn", label: "晨光" },
  { id: "deep", label: "深海" },
  { id: "canvas", label: "画布" },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];

export const THEME_STORAGE_KEY = "eduflow-theme";

export const isThemeId = (value: string | null): value is ThemeId =>
  THEMES.some((theme) => theme.id === value);

export function resolveInitialTheme(): ThemeId {
  const saved = localStorage.getItem(THEME_STORAGE_KEY);
  if (isThemeId(saved)) return saved;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches
    ? "deep"
    : "canvas";
}
