// Example of how lingo.dev works in your components

// BEFORE (your original code):
export function Welcome() {
  return (
    <div>
      <h1>Welcome to IronClaw</h1>
      <p>Your AI-powered automation assistant</p>
      <button>Get Started</button>
    </div>
  );
}

// AFTER lingo.dev processes it (automatically at build time):
// The text is automatically extracted and translated
// Users see content in their selected language:
// 
// English:    "Welcome to IronClaw" → "Welcome to IronClaw"
// Spanish:    "Welcome to IronClaw" → "Bienvenido a IronClaw"
// French:     "Welcome to IronClaw" → "Bienvenue à IronClaw"
// German:     "Welcome to IronClaw" → "Willkommen bei IronClaw"
// Japanese:   "Welcome to IronClaw" → "IronClawへようこそ"
// Chinese:    "Welcome to IronClaw" → "欢迎来到IronClaw"
// Arabic:     "Welcome to IronClaw" → "مرحبا بك في IronClaw"
// Portuguese: "Welcome to IronClaw" → "Bem-vindo ao IronClaw"
// Russian:    "Welcome to IronClaw" → "Добро пожаловать в IronClaw"
// Korean:     "Welcome to IronClaw" → "IronClaw에 오신 것을 환영합니다"
// Italian:    "Welcome to IronClaw" → "Benvenuto in IronClaw"

// You don't need to change anything in your components!
// Just use the LanguageSwitcher component and lingo.dev handles the rest.
