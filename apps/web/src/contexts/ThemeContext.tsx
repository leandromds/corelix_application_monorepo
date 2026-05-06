/**
 * ThemeContext — dark-only.
 * The HTML root always has data-theme="dark".
 * ThemeProvider sets the attribute once on mount.
 * useTheme returns { resolvedTheme: 'dark' } — kept for backward-compat
 * with any consumer that reads resolvedTheme.
 */

import { createContext, useContext, useEffect, type ReactNode } from "react";

interface ThemeContextValue {
  resolvedTheme: "dark";
}

const ThemeContext = createContext<ThemeContextValue>({
  resolvedTheme: "dark",
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", "dark");
  }, []);

  return (
    <ThemeContext.Provider value={{ resolvedTheme: "dark" }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}
