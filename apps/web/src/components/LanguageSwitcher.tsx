import { Languages } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { useLingoContext } from "@lingo.dev/compiler/react";
import type { LocaleCode } from "lingo.dev/spec";

interface Language {
  code: string;
  label: string;
  flag: string;
}

const languages: Language[] = [
  { code: "en", label: "English", flag: "🇺🇸" },
  { code: "es", label: "Español", flag: "🇪🇸" },
  { code: "fr", label: "Français", flag: "🇫🇷" },
  { code: "de", label: "Deutsch", flag: "🇩🇪" },
  { code: "ja", label: "日本語", flag: "🇯🇵" },
  { code: "zh-CN", label: "简体中文", flag: "🇨🇳" },
  { code: "ar", label: "العربية", flag: "🇸🇦" },
  { code: "pt", label: "Português", flag: "🇵🇹" },
  { code: "ru", label: "Русский", flag: "🇷🇺" },
  { code: "ko", label: "한국어", flag: "🇰🇷" },
  { code: "it", label: "Italiano", flag: "🇮🇹" },
];

export function LanguageSwitcher() {
  // Use the compiler's context hook which matches LingoProvider
  const { locale, setLocale, isLoading } = useLingoContext();
  const currentLocale = locale || "en";

  const changeLocale = (localeCode: string) => {
    // Use the context's setLocale which properly updates the state
    // Cast to LocaleCode as the codes are validated by the languages array
    setLocale(localeCode as LocaleCode);
  };

  const currentLanguage = languages.find((lang) => lang.code === currentLocale) || languages[0];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="gap-2 hover:bg-white/5 text-white/70 hover:text-white transition-colors"
        >
          <Languages className="h-4 w-4" />
          <span className="text-lg">{currentLanguage.flag}</span>
          <span className="hidden sm:inline">{currentLanguage.label}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56 bg-card border-white/10">
        <DropdownMenuLabel className="text-white/70">Select Language</DropdownMenuLabel>
        <DropdownMenuSeparator className="bg-white/10" />
        {languages.map((language) => (
          <DropdownMenuItem
            key={language.code}
            onClick={() => changeLocale(language.code)}
            className={`flex items-center gap-3 cursor-pointer ${currentLocale === language.code
              ? "bg-brand-pink/20 text-white"
              : "text-white/70 hover:text-white hover:bg-white/5"
              }`}
          >
            <span className="text-lg">{language.flag}</span>
            <span className="flex-1">{language.label}</span>
            {currentLocale === language.code && (
              <span className="text-brand-pink">✓</span>
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
