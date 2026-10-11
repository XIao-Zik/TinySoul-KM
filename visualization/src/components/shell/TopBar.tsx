import { useState } from "react";
import { History, Layers, Power, RefreshCw, Wrench } from "lucide-react";
import { restartBackend } from "../../app/connection";
import { useT } from "../../i18n";
import { useConnectionStore } from "../../store/connectionStore";
import { openContextDrawer } from "../../features/context/entries";
import { openHistoryBrowser } from "../../features/history/entries";
import { Badge } from "../ui/Badge";
import { Button, IconButton } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { ReflectionDialog } from "../../features/resources/ReflectionDialog";

/**
 * The top bar: product title, the "turn active" badge, entry points for the
 * history browser (day directory / Session map), the Context drawer (P04)
 * and an explicit host restart, plus the reconnect indicator shown while the
 * connection is down.
 */
export function TopBar() {
  const status = useConnectionStore((s) => s.status);
  const epoch = useConnectionStore((s) => s.epoch);
  const connected = useConnectionStore((s) => s.phase === "connected");
  const t = useT();
  const [confirmingRestart, setConfirmingRestart] = useState(false);
  const [organizing, setOrganizing] = useState(false);

  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b border-line bg-bg-elev px-4">
      <div className="min-w-0 flex-1">
        <div className="text-sm font-semibold">TinySoul</div>
      </div>
      {connected && status?.turn_active && (
        <Badge tone="accent">
          <span className="animate-pulse-dot">●</span> {t("turn active")}
        </Badge>
      )}
      <IconButton
        label={t("History")}
        onClick={() => openHistoryBrowser(epoch)}
        disabled={!connected}
      >
        <History size={15} />
      </IconButton>
      <Button variant="ghost" size="xs" aria-label={t("Organize")} disabled={!connected} onClick={() => setOrganizing(true)}>
        <Wrench size={14} /><span className="hidden sm:inline">{t("Organize")}</span>
      </Button>
      <IconButton
        label={t("Context")}
        onClick={() => openContextDrawer(epoch)}
        disabled={!connected}
      >
        <Layers size={15} />
      </IconButton>
      <IconButton
        label={t("Restart backend")}
        onClick={() => setConfirmingRestart(true)}
        disabled={!connected}
      >
        <Power size={15} />
      </IconButton>
      <ReconnectIndicator />
      {organizing && <ReflectionDialog onClose={() => setOrganizing(false)} />}
      {confirmingRestart && (
        <RestartConfirm onClose={() => setConfirmingRestart(false)} />
      )}
    </header>
  );
}

function RestartConfirm({ onClose }: { onClose: () => void }) {
  const restartPending = useConnectionStore((s) => s.restartPending);
  const t = useT();
  return (
    <Modal title={t("Restart the backend?")} onClose={onClose} width="max-w-md">
      <p className="text-[13px] leading-5 text-fg-muted">
        {t("The host rebuilds the current Agent generation. The running turn is stopped and the view re-synchronizes afterwards. The endpoint itself keeps its address and event history.")}
      </p>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          {t("Cancel")}
        </Button>
        <Button
          variant="danger"
          loading={restartPending}
          onClick={() => {
            void restartBackend().finally(onClose);
          }}
        >
          {t("Restart")}
        </Button>
      </div>
    </Modal>
  );
}

function ReconnectIndicator() {
  const phase = useConnectionStore((s) => s.phase);
  const eventsPhase = useConnectionStore((s) => s.eventsPhase);
  const t = useT();
  if (phase === "connected" && eventsPhase === "live") return null;
  // The stream's first attach after a fresh handshake is still "connecting";
  // "reconnecting" is reserved for a dropped stream the client is recovering.
  const label =
    phase === "connecting"
      ? t("connecting…")
      : phase === "connected"
        ? eventsPhase === "reconnecting"
          ? t("reconnecting…")
          : t("connecting…")
        : t("disconnected");
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-fg-faint">
      <RefreshCw size={12} className="animate-spin-slow" />
      {label}
    </span>
  );
}
