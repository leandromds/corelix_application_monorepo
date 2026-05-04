import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  // ── Ignored paths ────────────────────────────────────────────────────────
  { ignores: ["dist", "coverage", "node_modules"] },

  // ── Main config — all TypeScript / TSX source files ──────────────────────
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      // React Hooks — enforces Rules of Hooks and exhaustive-deps
      ...reactHooks.configs.recommended.rules,

      // React Refresh — warn (not error) when a module exports both a component
      // and a non-component value (e.g. Avatar + getInitials, Button + buttonVariants).
      // These are intentional co-location patterns in this codebase.
      // Set to 'error' only after moving utilities to dedicated files.
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],

      // Unused vars — ignore anything prefixed with _ (standard TS convention
      // for intentionally unused destructured variables or parameters).
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          varsIgnorePattern: "^_",
          argsIgnorePattern: "^_",
          destructuredArrayIgnorePattern: "^_",
        },
      ],
    },
  },

  // ── Test files — relax rules that don't apply to tests ───────────────────
  {
    files: ["src/test/**", "**/*.test.{ts,tsx}"],
    rules: {
      // Test helper modules export setup utilities, not React components —
      // react-refresh is irrelevant here.
      "react-refresh/only-export-components": "off",
    },
  },
);
