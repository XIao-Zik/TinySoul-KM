import { matchField, type CatalogField, type CatalogDocumentField, type SettingsCatalog } from "../draft/catalog";
import type { Locale } from "../../../i18n/locale";
import { DEFAULT_LOCALE } from "../../../i18n/locale";
import { useAppStore } from "../../../store/appStore";
import { documentText, fieldText } from "./catalog.zh-CN";
import { uiText } from "./ui.zh-CN";

/**
 * The Settings presentation dictionaries are Chinese overlays on English
 * sources: `en` renders the source itself, `zh-CN` applies the overlay.
 * The locale follows the global client preference, so the whole settings
 * surface switches together with the shell.
 */
function currentLocale(): Locale {
  return useAppStore.getState().locale ?? DEFAULT_LOCALE;
}

/** Source-copy fallback makes undeclared or newly added backend fields readable. */
export function settingsText(source: string): string {
  const collapsed = source.replace(/\s+/g, " ").trim();
  if (currentLocale() !== "zh-CN") return collapsed === "" ? source : collapsed;
  return uiText[collapsed] ?? collapsed;
}

export function localizeField(field: CatalogField): CatalogField {
  if (currentLocale() !== "zh-CN") return field;
  const text = fieldText[field.path];
  return {
    ...field,
    title: text?.[0] ?? field.title,
    description: text?.[1] ?? field.description,
    choices: field.choices.map((choice) => ({ ...choice, label: settingsText(choice.label) })),
  };
}

/** Match the authoritative catalog first; localization cannot invent a field or rule. */
export function translatedField(catalog: SettingsCatalog | null, path: string): CatalogField | null {
  const field = matchField(catalog, path);
  return field === null ? null : localizeField(field);
}

export function localizeDocument(field: CatalogDocumentField): CatalogDocumentField {
  if (currentLocale() !== "zh-CN") return field;
  const text = field.documentSet === "action.catalog" ? documentText[`${field.documentKind}:${field.path}`] : undefined;
  return text ? { ...field, title: text[0], description: text[1] } : field;
}
