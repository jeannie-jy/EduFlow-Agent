export const THEMES = [
  { id: "light", label: "浅色" },
  { id: "dark", label: "深色" },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];

export const THEME_STORAGE_KEY = "eduflow-theme";

export const isThemeId = (value: string | null): value is ThemeId =>
  THEMES.some((theme) => theme.id === value);

export function resolveInitialTheme(): ThemeId {
  const saved = localStorage.getItem(THEME_STORAGE_KEY);
  if (isThemeId(saved)) return saved;
  return "light";
}
