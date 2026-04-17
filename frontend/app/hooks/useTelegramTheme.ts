"use client";

import { useEffect, useState } from "react";

export type TelegramTheme = "light" | "dark";

export function useTelegramTheme() {
  const [theme, setTheme] = useState<TelegramTheme>("dark");

  useEffect(() => {
    if (typeof window === "undefined" || !window.Telegram?.WebApp) {
      return;
    }

    const tg = window.Telegram.WebApp;

    // Get initial color scheme
    const initialTheme = tg.colorScheme || "dark";
    setTheme(initialTheme);

    // Apply class to root element
    const root = document.documentElement;
    root.classList.remove("light", "dark");
    root.classList.add(initialTheme);

    // Subscribe to theme changes
    const handleThemeChange = () => {
      const newTheme = tg.colorScheme || "dark";
      setTheme(newTheme);

      // Update root element classes
      root.classList.remove("light", "dark");
      root.classList.add(newTheme);
    };

    tg.onEvent("themeChanged", handleThemeChange);

    return () => {
      tg.offEvent("themeChanged", handleThemeChange);
    };
  }, []);

  return theme;
}
