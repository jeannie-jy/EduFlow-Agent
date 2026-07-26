import { MonitorIcon, MoonIcon, SunIcon } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { THEMES, isThemePreference, type ThemePreference } from "@/theme/theme";
import { useTheme } from "@/theme/ThemeProvider";

const icons: Record<ThemePreference, typeof SunIcon> = {
  system: MonitorIcon,
  light: SunIcon,
  dark: MoonIcon,
};

export function ThemeSwitcher() {
  const { preference, resolvedTheme, setPreference } = useTheme();
  const current = THEMES.find(({ id }) => id === preference) ?? THEMES[0];
  const CurrentIcon = icons[preference];

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          className={buttonVariants({ variant: "outline", size: "icon" })}
          aria-label={`主题：${current.label}`}
        >
          <CurrentIcon aria-hidden="true" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuRadioGroup
            value={preference}
            onValueChange={(value) => {
              if (isThemePreference(value)) setPreference(value);
            }}
          >
            <DropdownMenuLabel>外观</DropdownMenuLabel>
            {THEMES.map(({ id, label }) => {
              const Icon = icons[id];
              return (
                <DropdownMenuRadioItem key={id} value={id} closeOnClick>
                  <Icon aria-hidden="true" />
                  {label}
                </DropdownMenuRadioItem>
              );
            })}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      <span className="sr-only" aria-live="polite" aria-atomic="true">
        当前主题：{current.label}，实际显示：{resolvedTheme}
      </span>
    </>
  );
}
