import js from "@eslint/js";
import ts from "typescript-eslint";
import hooks from "eslint-plugin-react-hooks";
export default ts.config(
  { ignores: ["dist", "test-results", "playwright-report"] },
  js.configs.recommended,
  ...ts.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    plugins: { "react-hooks": hooks },
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      ...hooks.configs.recommended.rules,
      "react-hooks/set-state-in-effect": "off",
    },
  },
);
