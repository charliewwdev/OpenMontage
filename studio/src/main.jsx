import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { installClientGuard } from "./lib/clientGuard";
import "./styles.css";

try {
  const theme = localStorage.getItem("om.theme.v1") === "light" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", theme);
} catch {
  document.documentElement.setAttribute("data-theme", "dark");
}

installClientGuard();

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
