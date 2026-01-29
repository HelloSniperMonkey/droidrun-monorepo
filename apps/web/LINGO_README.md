# 🌍 Lingo.dev Multilingual Support

This application now supports **11 languages** using [lingo.dev](https://lingo.dev) - an AI-powered internationalization toolkit.

## Supported Languages

- 🇺🇸 English (en)
- 🇪🇸 Español (es)
- 🇫🇷 Français (fr)
- 🇩🇪 Deutsch (de)
- 🇯🇵 日本語 (ja)
- 🇨🇳 简体中文 (zh-CN)
- 🇸🇦 العربية (ar)
- 🇵🇹 Português (pt)
- 🇷🇺 Русский (ru)
- 🇰🇷 한국어 (ko)
- 🇮🇹 Italiano (it)

## How to Use

### For Users

1. Click the **language switcher** in the sidebar (globe icon with flag)
2. Select your preferred language from the dropdown
3. The page will reload with your selected language

### For Developers

#### Setup

The application is already configured with lingo.dev. The configuration is in:
- `vite.config.ts` - Vite plugin configuration
- `App.tsx` - LingoProvider wrapper
- `.lingo/` - Translation cache directory

#### How It Works

1. **Automatic Translation**: When you build the app, lingo.dev automatically:
   - Scans all text in your React components
   - Generates translations for all configured languages
   - Caches translations in `.lingo/cache/`

2. **Runtime Loading**: When users select a language:
   - The app loads the appropriate translation file
   - All text automatically displays in the selected language
   - Preference is saved in localStorage and cookies

#### Adding New Text

Simply write text normally in your components:

```tsx
<h1>Welcome to IronClaw</h1>
<p>This text will be automatically translated</p>
```

Lingo.dev will automatically detect and translate it!

#### Manual Translation Override

If you need to override AI translations for specific text:

```tsx
<h1 data-lingo-override={{ 
  de: "IronClaw", 
  fr: "IronClaw", 
  es: "IronClaw" 
}}>
  IronClaw
</h1>
```

#### Environment Variables

For production deployments with custom LLM providers:

```bash
# .env
LINGODOTDEV_API_KEY=your_api_key_here
```

#### Build Commands

```bash
# Development (uses pseudolocalization for testing)
npm run dev

# Production build (generates real translations)
npm run build
```

## Architecture

- **Vite Plugin**: Compiles and processes translations at build time
- **LingoProvider**: React context provider for managing locale state
- **LanguageSwitcher**: UI component for language selection
- **Cache**: Translation files stored in `.lingo/cache/`

## Troubleshooting

### Translations not showing?
- Make sure you've run the build at least once
- Check that `.lingo/cache/` contains translation files
- Verify the locale cookie is set correctly

### Adding a new language?
1. Add it to `vite.config.ts` in the `targetLocales` array
2. Add it to `LanguageSwitcher.tsx` in the `languages` array
3. Rebuild the application

## Resources

- [Lingo.dev Documentation](https://lingo.dev)
- [Lingo.dev GitHub](https://github.com/lingodotdev/lingo.dev)
