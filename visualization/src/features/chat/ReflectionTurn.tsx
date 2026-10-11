/** c479ca0's maintenance bubble over the shared v2 Turn presentation. */
import { useRef } from "react";
import { Wrench, Square, PanelRightOpen } from "lucide-react";
import type { TurnSummary, TurnResult } from "../../api/v2/types";
import type { RuntimeTurnProjection } from "../../store/turnStore";
import { useTurnStore } from "../../store/turnStore";
import { useT } from "../../i18n";
import { Button } from "../../components/ui/Button";
import { Markdown } from "../../components/markdown/Markdown";
import { openTurnProcess } from "../trace/entries";
import { AgentRow, BudgetCard, InteractionRow, UserBubble } from "./ConversationRows";
import { useTurnPresentation } from "./useTurnPresentation";
import { useActivityDetails } from "./useActivityDetails";
import { LiveStatus } from "./LiveStatus";
import { cancelReflection } from "./turnController";
import type { ActivityPresentation } from "./presentation";

const EMPTY_ITEMS: RuntimeTurnProjection["items"] = [];
/** Status → translation key; resolved through t() at render time. */
const RESULT_LABELS: Record<string, string> = {
  completed: "Tidy-up completed", skipped: "Nothing to tidy up", partial: "Tidy-up partially completed", awaiting_user: "Awaiting your guidance",
  failed: "Tidy-up failed", stopped: "Tidy-up stopped", cancelled: "Tidy-up cancelled", exhausted: "Budget exhausted",
};
const REASON_LABELS: Record<string, string> = {
  no_home_differences: "Home has no pending differences to review.",
  target_sources_empty: "No conversations or memory to tidy up for this day.",
  target_day_is_future: "The target day has not arrived yet.",
};

export function ReflectionTurn({ epoch, summary, projection, latest }: {
  epoch: number; summary: TurnSummary; projection?: RuntimeTurnProjection; latest: boolean;
}) {
  const t = useT();
  const id = summary.turn_id ?? summary.request_id;
  const snapshot = projection?.snapshot ?? null;
  const items = projection?.items ?? EMPTY_ITEMS;
  const active = (snapshot?.state ?? summary.state) !== "finished";
  const enabled = snapshot?.turn_id != null && (active || latest);
  const presentation = useTurnPresentation(id, snapshot, items, enabled);
  const working = useActivityDetails(id, active, enabled);
  const captured = useRef<ActivityPresentation | null>(null);
  if (presentation?.activity) captured.current = { ...presentation.activity, working };
  const activity = captured.current;
  const result = snapshot?.result;
  const origin = snapshot?.reflection ?? summary.reflection;
  const day = snapshot?.active_day ?? summary.active_day;
  const outgoing = useTurnStore((s) => s.outgoing);
  const hasProcess = activity !== null && (active || activity.trail.length > 0 || activity.headline.phase !== null);
  return <section data-turn-root={id} data-turn-id={id} data-reflection={summary.kind} className="space-y-4 animate-fade-in">
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-2xl rounded-tr-sm border border-line bg-bg-sunken px-3.5 py-2 text-[12px] text-fg-muted">
        <div className="flex items-center gap-2"><Wrench size={12} />
          <span className="font-medium">{t("{kind} tidy-up", { kind: summary.kind === "home" ? "Home" : "Memory" })}</span>
          {origin?.target_day && <span className="font-mono text-[11px]" title={t("Tidy-up source day")}>{origin.target_day}</span>}
          <span className="text-[10px] text-fg-faint">{origin?.trigger === "scheduled" ? t("Auto") : t("Manual")}</span>
        </div>
        {origin?.instructions_excerpt && (origin.truncated ? <details className="mt-1.5">
          <summary className="cursor-pointer whitespace-pre-wrap">{origin.instructions_excerpt}…</summary>
          <p className="mt-2 whitespace-pre-wrap">{origin.instructions ?? origin.instructions_excerpt}</p>
        </details> : <p className="mt-1.5 whitespace-pre-wrap">{origin.instructions_excerpt}</p>)}
      </div>
    </div>
    <AgentRow>
      {hasProcess && <LiveStatus epoch={epoch} turnId={id} day={day} activity={activity}
        mode={active ? "live" : "settled"} status={presentation?.status} />}
      {!hasProcess && active && <div className="text-[12px] text-fg-faint">{summary.state === "queued" ? t("Waiting to start the tidy-up…") : t("Preparing the tidy-up…")}</div>}
      {items.filter((item) => item.role === "agent.question" || item.role === "user.reply").map((item) =>
        <InteractionRow key={item.id} item={item} fresh={false} view="live" turnId={id} nested
          origin={{ turnId: id, day: day ?? undefined, view: "live" }} />)}
      {outgoing.filter((echo) => echo.requestId === summary.request_id && (echo.kind !== "reply" || echo.state === "failed")).map((echo) => <UserBubble key={echo.echoId} text={echo.text} pending={echo.state === "failed" ? undefined : echo.state} />)}
      <BudgetCard snapshot={snapshot} />
      {!active && <ReflectionResult result={result ?? null} status={result?.status ?? summary.status} />}
      <div className="flex items-center justify-end gap-2">
        {active && <Button variant="ghost" size="xs" disabled={snapshot?.cancel_requested}
          onClick={() => void cancelReflection(epoch, summary.request_id)}><Square size={11} />{snapshot?.cancel_requested ? t("Stopping…") : summary.state === "queued" ? t("Cancel this tidy-up") : t("Stop the tidy-up")}</Button>}
        {(hasProcess || result?.tasks?.some((task) => task.turn !== undefined)) && <Button variant="ghost" size="xs" onClick={() => openTurnProcess(epoch, id, day)}><PanelRightOpen size={12} /> {t("Details")}</Button>}
      </div>
    </AgentRow>
  </section>;
}

function ReflectionResult({ result, status }: { result: TurnResult | null; status: string | null }) {
  const t = useT();
  return <div className="space-y-2 text-[13px] leading-6">
    <div className={status === "failed" ? "font-medium text-danger" : "font-medium text-fg-muted"}>{t(RESULT_LABELS[status ?? ""] ?? "Tidy-up has ended")}</div>
    {typeof result?.failure?.message === "string" && <p className="text-danger">{result.failure.message}</p>}
    {result?.tasks?.map((task, index) => {
      const text = task.turn?.completion?.text;
      const failure = task.turn?.failure?.message;
      return <div key={index}>
        {typeof text === "string" && <Markdown>{text}</Markdown>}
        {typeof failure === "string" && <p className="text-danger">{failure}</p>}
        {task.reason && <p className="text-fg-muted">{t(REASON_LABELS[task.reason] ?? task.reason)}</p>}
        {task.details.runtime_home_removed === true && <p className="text-[12px] text-fg-faint">{t("The unchanged runtime copy has been cleaned up.")}</p>}
        {typeof task.details.remaining_changes === "number" && task.details.remaining_changes > 0 && <p className="text-fg-muted">{t("{count} Home differences remain.", { count: task.details.remaining_changes })}</p>}
        {typeof task.details.remaining_skill_reviews === "number" && task.details.remaining_skill_reviews > 0 && <p className="text-fg-muted">{t("{count} Skill memory items remain under review.", { count: task.details.remaining_skill_reviews })}</p>}
      </div>;
    })}
  </div>;
}
