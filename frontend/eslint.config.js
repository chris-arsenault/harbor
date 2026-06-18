import js from "@eslint/js";
import * as aharaRules from "@ahara/standards/eslint-rules";
import prettier from "eslint-config-prettier";
import jsxA11y from "eslint-plugin-jsx-a11y";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import reactPerf from "eslint-plugin-react-perf";
import reactRefresh from "eslint-plugin-react-refresh";
import sonarjs from "eslint-plugin-sonarjs";
import tseslint from "typescript-eslint";

const ahara = {
  rules: {
    "max-jsx-props": aharaRules.maxJsxProps,
    "no-direct-fetch": aharaRules.noDirectFetch,
    "no-direct-store-import": aharaRules.noDirectStoreImport,
    "no-escape-hatches": aharaRules.noEscapeHatches,
    "no-inline-styles": aharaRules.noInlineStyles,
    "no-js-file-extension": aharaRules.noJsFileExtension,
    "no-manual-async-state": aharaRules.noManualAsyncState,
    "no-manual-expand-state": aharaRules.noManualExpandState,
    "no-manual-view-header": aharaRules.noManualViewHeader,
    "no-non-vitest-testing": aharaRules.noNonVitestTesting,
    "no-raw-undefined-union": aharaRules.noRawUndefinedUnion,
  },
};

const typedFiles = ["src/**/*.{ts,tsx}", "vite.config.ts", "tailwind.config.ts"];

export default tseslint.config(
  {
    ignores: ["coverage", "dist", "node_modules"],
  },
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked.map((config) => ({
    ...config,
    files: typedFiles,
  })),
  {
    files: typedFiles,
    languageOptions: {
      parserOptions: {
        project: ["./tsconfig.json", "./tsconfig.node.json"],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      ahara,
      "jsx-a11y": jsxA11y,
      react,
      "react-hooks": reactHooks,
      "react-perf": reactPerf,
      "react-refresh": reactRefresh,
      sonarjs,
    },
    settings: {
      react: {
        version: "detect",
      },
    },
    rules: {
      ...react.configs.recommended.rules,
      ...react.configs["jsx-runtime"].rules,
      ...reactHooks.configs.recommended.rules,
      ...jsxA11y.configs.recommended.rules,
      ...sonarjs.configs.recommended.rules,
      complexity: ["error", 10],
      "max-depth": ["warn", 4],
      "max-lines": ["error", { max: 400, skipBlankLines: true, skipComments: true }],
      "max-lines-per-function": ["error", { max: 75, skipBlankLines: true, skipComments: true }],
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      "ahara/max-jsx-props": ["warn", { max: 12 }],
      "ahara/no-direct-fetch": "error",
      "ahara/no-direct-store-import": "warn",
      "ahara/no-escape-hatches": "error",
      "ahara/no-inline-styles": "error",
      "ahara/no-js-file-extension": "error",
      "ahara/no-manual-async-state": "warn",
      "ahara/no-manual-expand-state": "warn",
      "ahara/no-manual-view-header": "warn",
      "ahara/no-non-vitest-testing": "error",
      "ahara/no-raw-undefined-union": "warn",
    },
  },
  prettier
);
