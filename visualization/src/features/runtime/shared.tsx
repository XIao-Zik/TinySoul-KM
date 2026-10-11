/**
 * Small shared UI rows of the runtime-observation tabs (plan §14/P09).
 */

import type { ReactElement } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";

import { useT } from "../../i18n";

/** Loading row shared by the runtime tabs. */
export function LoadingRow({ text }: { text?: string }): ReactElement {
  const t = useT();
  return (
    <div className="flex items-center gap-2 px-1 py-3 text-[12px] text-fg-faint">
      <Loader2 size={13} className="animate-spin-slow" />
      {text ?? t("Reading…")}
    </div>
  );
}

/** Bounded read failure with an explicit retry. */
export function ReadError({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}): ReactElement {
  const t = useT();
  return (
    <div className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-[12px] text-danger">
      <AlertTriangle size={12} className="shrink-0" />
      <span className="min-w-0 flex-1">{t("The read failed ({message}).", { message })}</span>
      {onRetry !== undefined && (
        <button
          type="button"
          onClick={onRetry}
          className="shrink-0 font-medium hover:underline"
        >
          {t("Retry")}
        </button>
      )}
    </div>
  );
}
