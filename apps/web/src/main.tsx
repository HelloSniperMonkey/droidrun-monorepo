import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";

const rootElement = document.getElementById("root");

if (rootElement) {
  document.documentElement.classList.add("dark");
  createRoot(rootElement).render(<App />);
}
