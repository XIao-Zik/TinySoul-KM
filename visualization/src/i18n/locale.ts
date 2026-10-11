/**
 * Supported presentation locales. The English source string is the
 * translation key everywhere: `en` renders the source itself, and the
 * zh-CN dictionaries map selected sources to Chinese. Untranslated strings
 * degrade to English, never to a raw key.
 */
export type Locale = "zh-CN" | "en";

export const DEFAULT_LOCALE: Locale = "zh-CN";

export const LOCALE_OPTIONS: { value: Locale; label: string }[] = [
  { value: "zh-CN", label: "中文" },
  { value: "en", label: "English" },
];
