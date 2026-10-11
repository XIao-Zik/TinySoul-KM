import { Settings } from "lucide-react";

import { useT } from "../../i18n";
import { selectDraftCount, useConfigDraftStore } from "./draft/store";

/**
 * Floating reminder shown outside the settings tab while unapplied config
 * drafts exist (P10: leaving settings keeps the in-memory draft and shows its
 * count). Clicking it returns to the settings overview.
 */
export function SettingsDraftChip({ onOpen }: { onOpen: () => void }) {
  const t = useT();
  const draftCount = useConfigDraftStore(selectDraftCount);
  if (draftCount === 0) return null;
  return (
    <button
      onClick={onOpen}
      className="absolute bottom-3 left-3 z-(--z-overlay) inline-flex items-center gap-1.5 rounded-full border border-line bg-bg-elev px-3 py-1.5 text-[12px] font-medium text-fg shadow-pop transition-colors hover:border-accent/50 hover:text-accent"
      title={t("Unapplied settings changes — click to return to settings")}
    >
      <Settings size={13} />
      {t("{count} unsaved settings change(s)", { count: draftCount })}
    </button>
  );
}
