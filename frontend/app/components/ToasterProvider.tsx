"use client";

import { Toaster } from "react-hot-toast";

export default function ToasterProvider() {
  return (
    <Toaster
      position="top-center"
      toastOptions={{
        duration: 3000,
        style: {
          borderRadius: "12px",
          background: "var(--tg-theme-bg-color, #1a1a1a)",
          color: "var(--tg-theme-text-color, #ffffff)",
          padding: "12px 16px",
          fontSize: "14px",
          boxShadow: "0 4px 12px rgba(0, 0, 0, 0.3)",
        },
        success: {
          iconTheme: {
            primary: "#22c55e",
            secondary: "var(--tg-theme-bg-color, #1a1a1a)",
          },
        },
        error: {
          iconTheme: {
            primary: "#ef4444",
            secondary: "var(--tg-theme-bg-color, #1a1a1a)",
          },
        },
        loading: {
          iconTheme: {
            primary: "#3b82f6",
            secondary: "var(--tg-theme-bg-color, #1a1a1a)",
          },
        },
      }}
    />
  );
}
