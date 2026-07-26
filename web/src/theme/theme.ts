export const THEMES = [
  { id: "system", label: "跟随系统" },
  { id: "light", label: "Light" },
  { id: "dark", label: "Dark" },
] as const;

export type ThemePreference = (typeof THEMES)[number]["id"];
export type ThemeId = Exclude<ThemePreference, "system">;

export const THEME_STORAGE_KEY = "eduflow-theme";
export const DARK_MEDIA_QUERY = "(prefers-color-scheme: dark)";

export const isThemePreference = (value: string | null): value is ThemePreference =>
  THEMES.some((theme) => theme.id === value);

export function resolveInitialPreference(): ThemePreference {
  const saved = localStorage.getItem(THEME_STORAGE_KEY);
  return isThemePreference(saved) ? saved : "system";
}

export function resolveTheme(
  preference: ThemePreference,
  prefersDark: boolean,
): ThemeId {
  return preference === "system" ? (prefersDark ? "dark" : "light") : preference;
}
