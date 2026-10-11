/**
 * Global UI text localization (gettext style).
 *
 * The English source string is the key: `en` renders the source itself and
 * the zh-CN dictionaries map selected sources to Chinese, so untranslated
 * strings degrade to English, never to a raw key. Dictionaries are split
 * per feature in `dicts/` and merged here; each segment is owned by its
 * feature so parallel edits never conflict.
 *
 * Sources are collapsed to single spaces before lookup, so JSX-wrapped
 * multi-line strings resolve without caring about source formatting.
 */

import { useCallback } from "react";

import { useAppStore } from "../store/appStore";
import { chatText } from "./dicts/zh-CN-chat";
import { contextText } from "./dicts/zh-CN-context";
import { historyText } from "./dicts/zh-CN-history";
import { homeText } from "./dicts/zh-CN-home";
import { memoryText } from "./dicts/zh-CN-memory";
import { resourcesText } from "./dicts/zh-CN-resources";
import { runtimeText } from "./dicts/zh-CN-runtime";
import { settingsUiText } from "./dicts/zh-CN-settings";
import { shellText } from "./dicts/zh-CN-shell";
import { traceText } from "./dicts/zh-CN-trace";
import { workspaceText } from "./dicts/zh-CN-workspace";
import { DEFAULT_LOCALE } from "./locale";
import type { Locale } from "./locale";

const zhCNSegments: Record<string, string>[] = [
  shellText,
  chatText,
  contextText,
  traceText,
  historyText,
  resourcesText,
  workspaceText,
  homeText,
  memoryText,
  runtimeText,
  settingsUiText,
];

const zhCN: Record<string, string> = Object.assign({}, ...zhCNSegments);

export type TextVars = Record<string, string | number>;

/** Collapse JSX multi-line sources to the single-spaced lookup form. */
export function collapseSource(source: string): string {
  return source.replace(/\s+/g, " ").trim();
}

export function translate(
  locale: Locale,
  source: string,
  vars?: TextVars,
): string {
  const resolved =
    locale === "zh-CN" ? (zhCN[collapseSource(source)] ?? source) : source;
  if (vars === undefined) return resolved;
  return resolved.replace(/\{(\w+)\}/g, (token, key: string) =>
    key in vars ? String(vars[key]) : token,
  );
}

/** Non-reactive translation for plain functions and module helpers. */
export function t(source: string, vars?: TextVars): string {
  return translate(useAppStore.getState().locale ?? DEFAULT_LOCALE, source, vars);
}

/** Reactive translator hook: re-renders the caller when the locale changes. */
export function useT() {
  const locale = useAppStore((s) => s.locale);
  return useCallback(
    (source: string, vars?: TextVars) => translate(locale, source, vars),
    [locale],
  );
}

export { DEFAULT_LOCALE, LOCALE_OPTIONS } from "./locale";
export type { Locale } from "./locale";
