import {
  createContext, useContext, useEffect, useMemo, useState, type PropsWithChildren,
} from "react";
import {
  DARK_MEDIA_QUERY, resolveInitialPreference, resolveTheme,
  THEME_STORAGE_KEY, type ThemeId, type ThemePreference,
} from "./theme";

type ThemeContextValue = {
  preference: ThemePreference;
  resolvedTheme: ThemeId;
  setPreference: (theme: ThemePreference) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: PropsWithChildren) {
  const [preference, setPreference] = useState(resolveInitialPreference);
  const [prefersDark, setPrefersDark] = useState(
    () => window.matchMedia(DARK_MEDIA_QUERY).matches,
  );
  const resolvedTheme = resolveTheme(preference, prefersDark);

  useEffect(() => {
    const media = window.matchMedia(DARK_MEDIA_QUERY);
    const update = (event: MediaQueryListEvent) => setPrefersDark(event.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme;
    localStorage.setItem(THEME_STORAGE_KEY, preference);
  }, [preference, resolvedTheme]);

  const value = useMemo(
    () => ({ preference, resolvedTheme, setPreference }),
    [preference, resolvedTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("useTheme must be used inside ThemeProvider");
  return value;
}
