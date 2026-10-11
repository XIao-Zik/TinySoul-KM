/**
 * Execution tab (plan §14): what the Agent is doing right now — the active
 * Turn's formal state, its real wait reason with the way back to the
 * conversation, the finished Turn's bounded failure kept apart from
 * after-finish cleanup diagnostics, and the queued Turns. Cancelling a
 * queued Turn names that Turn's id explicitly; it never touches the running
 * one.
 */

import type { ReactElement } from "react";
import { CircleStop, ListTodo, PlayCircle } from "lucide-react";

import type { TurnResult, TurnSnapshot } from "../../api/v2/types";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Collapsible } from "../../components/ui/Collapsible";
import { CopyButton } from "../../components/ui/CopyButton";
import { EmptyState } from "../../components/ui/EmptyState";
import { JsonTree } from "../../components/ui/JsonTree";
import { useT } from "../../i18n";
import { useAppStore } from "../../store/appStore";
import { useConnectionStore } from "../../store/connectionStore";
import { cancelQueuedTurn } from "../chat/turnController";
import { shortTurnId, TURN_STATE_TONES } from "./runtimeModel";
import { useRuntimeUi } from "./store";
import { LoadingRow, ReadError } from "./shared";
import { waitReasonLabel, type ActiveTurnRead } from "./overview";

export function ExecutionTab({
  epoch,
  read,
}: {
  epoch: number;
  read: ActiveTurnRead;
}): ReactElement {
  const queued = useConnectionStore(
    (s) => s.status?.runtime.queued_request_ids ?? [],
  );
  return (
    <div className="space-y-4">
      <CurrentTurnCard read={read} />
      <QueueCard epoch={epoch} queued={queued} />
    </div>
  );
}

function CurrentTurnCard({ read }: { read: ActiveTurnRead }): ReactElement {
  const t = useT();
  if (!read.settled) return <LoadingRow text={t("Reading the active turn…")} />;
  if (read.turnId === null) {
    return (
      <EmptyState
        icon={<PlayCircle size={26} />}
        title={t("No turn is running")}
        description={t(
          "New turns start from the conversation; queued turns appear below.",
        )}
      />
    );
  }
  if (read.snapshot === null) {
    return (
      <ReadError
        message={read.error ?? t("the turn projection is unavailable")}
      />
    );
  }
  const snapshot = read.snapshot;
  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-line bg-bg-elev px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={TURN_STATE_TONES[snapshot.state] ?? "gray"}>
            {snapshot.state}
          </Badge>
          <Badge tone="accent">{t("{kind} turn", { kind: snapshot.kind })}</Badge>
          {snapshot.cancel_requested && (
            <Badge tone="yellow">{t("cancel requested")}</Badge>
          )}
          <span className="text-[12px] text-fg-faint" title={snapshot.turn_id ?? snapshot.request_id}>
            {shortTurnId(snapshot.turn_id ?? snapshot.request_id)}
          </span>
          <CopyButton text={() => snapshot.turn_id ?? snapshot.request_id} label={t("Copy turn id")} />
          <span className="flex-1" />
          <Button
            variant="outline"
            size="xs"
            onClick={() => useAppStore.getState().setActiveTab("chat")}
          >
            {t("Open in conversation")}
          </Button>
        </div>
        <WaitingLine snapshot={snapshot} />
        {snapshot.jobs.length > 0 && <JobsLine count={snapshot.jobs.length} />}
        {read.error !== null && (
          <div className="mt-2 text-[11px] text-warning">
            {t(
              "The latest refresh failed ({error}); the previous snapshot stays on screen.",
              { error: read.error },
            )}
          </div>
        )}
      </div>
      {snapshot.result !== null && <ResultCard result={snapshot.result} />}
    </div>
  );
}

/** The real wait reason, with the question/budget path back to the chat. */
function WaitingLine({ snapshot }: { snapshot: TurnSnapshot }): ReactElement | null {
  const t = useT();
  if (snapshot.state !== "waiting" || snapshot.wait_reason === null) {
    return null;
  }
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 text-[12px]">
      <Badge tone="yellow">{t(waitReasonLabel(snapshot.wait_reason))}</Badge>
      {snapshot.question !== null && (
        <span className="min-w-0 truncate text-fg-muted" title={snapshot.question.text}>
          {snapshot.question.text}
        </span>
      )}
      {snapshot.budget_request !== null && (
        <span className="text-fg-muted">
          {t("cycle {cycle} needs a grant", {
            cycle: snapshot.budget_request.next_cycle_index,
          })}
        </span>
      )}
    </div>
  );
}

function JobsLine({ count }: { count: number }): ReactElement {
  const t = useT();
  const setTab = useRuntimeUi((s) => s.setTab);
  return (
    <div className="mt-2 flex items-center gap-2 text-[12px] text-fg-muted">
      <ListTodo size={12} className="text-fg-faint" />
      {count === 1
        ? t("1 background job in this turn")
        : t("{count} background jobs in this turn", { count })}
      <button
        type="button"
        onClick={() => setTab("jobs")}
        className="text-accent hover:underline"
      >
        {t("open Jobs")}
      </button>
    </div>
  );
}

/**
 * The finished Turn's result. An execution failure (result.failure) is the
 * Turn's own bounded failure; finish_failures/cleanup are diagnostics raised
 * after the fact — related, never merged into one red box.
 */
function ResultCard({ result }: { result: TurnResult }): ReactElement {
  const t = useT();
  const hasCleanup =
    (result.finish_failures?.length ?? 0) > 0 || (result.cleanup?.length ?? 0) > 0;
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-[12px]">
        <span className="text-fg-faint">{t("Result")}</span>
        <Badge tone={result.status === "answered" ? "green" : "gray"}>
          {result.status}
        </Badge>
      </div>
      {result.failure != null && (
        <Collapsible
          title={t("Execution failure")}
          meta={<Badge tone="red">{t("failed")}</Badge>}
          defaultOpen
        >
          <JsonTree value={result.failure} defaultExpanded={false} />
        </Collapsible>
      )}
      {result.output != null && (
        <Collapsible title={t("Output")}>
          <JsonTree value={result.output} defaultExpanded={false} />
        </Collapsible>
      )}
      {result.completion != null && (
        <Collapsible title={t("Completion")}>
          <JsonTree value={result.completion} defaultExpanded={false} />
        </Collapsible>
      )}
      {hasCleanup && (
        <Collapsible
          title={t("Finish and cleanup diagnostics")}
          meta={
            <Badge tone="yellow">
              {(result.finish_failures?.length ?? 0) + (result.cleanup?.length ?? 0)}
            </Badge>
          }
        >
          <div className="space-y-2 text-[12px] text-fg-muted">
            <p>
              {t(
                "Raised while finishing or cleaning up — separate from the Turn's own result above.",
              )}
            </p>
            {(result.finish_failures?.length ?? 0) > 0 && (
              <JsonTree value={result.finish_failures ?? []} defaultExpanded={false} />
            )}
            {(result.cleanup?.length ?? 0) > 0 && (
              <JsonTree value={result.cleanup ?? []} defaultExpanded={false} />
            )}
          </div>
        </Collapsible>
      )}
    </div>
  );
}

/** Queued turns; each cancel names its own turn id, never the running one. */
function QueueCard({
  epoch,
  queued,
}: {
  epoch: number;
  queued: string[];
}): ReactElement | null {
  const t = useT();
  if (queued.length === 0) return null;
  return (
    <div className="rounded-lg border border-line bg-bg-elev px-4 py-3">
      <div className="mb-2 flex items-center gap-2 text-[12px] text-fg-faint">
        {t("Queued turns — cancelling one never affects the running turn.")}
      </div>
      <div className="space-y-1">
        {queued.map((turnId) => (
          <div key={turnId} className="flex items-center gap-2 text-[13px]">
            <Badge tone="gray">{t("queued")}</Badge>
            <span className="font-medium" title={turnId}>
              {shortTurnId(turnId)}
            </span>
            <CopyButton text={() => turnId} label={t("Copy turn id")} />
            <span className="flex-1" />
            <Button
              variant="ghost"
              size="xs"
              onClick={() => void cancelQueuedTurn(epoch, turnId)}
            >
              <CircleStop size={12} />
              {t("Cancel")}
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}
