import { PaletteIcon } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { THEMES, isThemeId } from "@/theme/theme";
import { useTheme } from "@/theme/ThemeProvider";

export function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();
  const currentTheme = THEMES.find(({ id }) => id === theme) ?? THEMES[0];

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          className={buttonVariants({ variant: "outline" })}
          aria-label={`主题：${currentTheme.label}`}
        >
          <PaletteIcon data-icon="inline-start" />
          <span>主题：{currentTheme.label}</span>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuRadioGroup
            value={theme}
            onValueChange={(value) => {
              if (isThemeId(value)) setTheme(value);
            }}
          >
            <DropdownMenuLabel>界面主题</DropdownMenuLabel>
            {THEMES.map(({ id, label }) => (
              <DropdownMenuRadioItem key={id} value={id} closeOnClick>
                {label}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      <span className="sr-only" aria-live="polite" aria-atomic="true">
        当前主题：{currentTheme.label}
      </span>
    </>
  );
}
