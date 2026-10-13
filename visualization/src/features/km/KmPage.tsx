import { useCallback, useEffect, useRef, useState } from "react";
import {
  BookOpen,
  GitBranch,
  Search,
  Upload,
  Loader2,
} from "lucide-react";
import { invoke } from "@tauri-apps/api/core";
import { isTauriShell } from "../../app/discovery";
import { useAppStore } from "../../store/appStore";
import { useConnectionStore } from "../../store/connectionStore";
import { sendUserMessage } from "../chat/turnController";

/**
 * Knowledge (km) views: search hand-off, card feed, link graph (one-hop
 * neighborhood explorer + whole-store overview), and the import panel.
 * Cards/graph read the local knowledge store through Tauri commands (desktop
 * shell only); search reuses the existing Turn flow so the conversation,
 * trace and refs stay in one place.
 */

type KmView = "search" | "cards" | "graph" | "ingest";

interface KmCardSource {
  id: string;
  title: string;
  path: string;
  source: string;
}

interface KmCardEntry {
  day: string;
  question: string;
  answer: string;
  tags: string[];
  confidence: string;
  sources: KmCardSource[];
}

interface KmDocument {
  id: string;
  title: string;
  path: string;
  source: string;
  markdown: string;
}

interface KmNode {
  id: string;
  title: string;
  path: string;
  source: string;
  tags: string[];
}

interface KmGraphData {
  nodes: KmNode[];
  edges: { from: string; to: string }[];
  truncated: boolean;
}

interface KmDocHit {
  id: string;
  title: string;
  path: string;
  source: string;
}

interface KmNeighbor {
  id: string;
  title: string;
  path: string;
  source: string;
  direction: "out" | "in" | "both";
}

interface KmNeighborhoodData {
  center: KmDocHit;
  neighbors: KmNeighbor[];
}

const SOURCE_COLORS: Record<string, string> = {
  obsidian: "#8b7cf6",
  chat: "#38bdf8",
  card: "#f59e0b",
};

export function KmPage() {
  const [view, setView] = useState<KmView>("search");
  const [viewing, setViewing] = useState<KmDocHit | null>(null);
  const views: { key: KmView; label: string; icon: typeof Search }[] = [
    { key: "search", label: "检索", icon: Search },
    { key: "cards", label: "卡片流", icon: BookOpen },
    { key: "graph", label: "图谱", icon: GitBranch },
    { key: "ingest", label: "导入", icon: Upload },
  ];
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-1 border-b border-line px-4 py-2">
        {views.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setView(key)}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] transition-colors ${
              view === key ? "bg-active text-accent" : "text-fg-dim hover:text-fg"
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <KmReflectionBanner />
        {view === "search" && <KmSearchView />}
        {view === "cards" && <KmCardsView onOpenDoc={setViewing} />}
        {view === "graph" && <KmGraphView />}
        {view === "ingest" && <KmIngestView />}
      </div>
      <KmDocDrawer doc={viewing} onClose={() => setViewing(null)} />
    </div>
  );
}

const REFLECTION_INSTRUCTIONS =
  "调用一次 km.generate_card 生成该日导入文档的知识卡片；随后用 memory.write_daily 完成当日 Memory。";

/**
 * Daily reflection review: the first thing shown when the app opens. The
 * nightly task (00:10) should keep the backend alive for the 00:15 schedule,
 * but a missed day is auto-caught-up here on first open — POST /v2/reflection
 * (kind=memory, target_day) fires without any click, at most once per day per
 * app session; a failed auto-request degrades to a manual retry button.
 */
const autoSubmitted = new Set<string>();

function KmReflectionBanner() {
  const clients = useConnectionStore((s) => s.clients);
  const connected = useConnectionStore((s) => s.phase === "connected");
  const [missing, setMissing] = useState<string[] | null>(null);
  const [running, setRunning] = useState<string[]>([]);
  const [failed, setFailed] = useState<string[]>([]);
  const [hidden, setHidden] = useState(false);

  const load = useCallback(() => {
    if (!connected || clients === null) {
      setMissing(null);
      return;
    }
    clients.reflection
      .availability()
      .then((response) => setMissing(response.availability.missing_daily_days))
      .catch(() => setMissing(null));
  }, [connected, clients]);
  useEffect(() => {
    load();
  }, [load]);

  // Auto catch-up: submit once per missing day per session (newest first,
  // capped at 3); re-check availability shortly after so the banner settles.
  useEffect(() => {
    if (missing === null || missing.length === 0 || clients === null) return;
    for (const day of missing.slice(-3).reverse()) {
      if (autoSubmitted.has(day)) continue;
      autoSubmitted.add(day);
      setRunning((prev) => [...prev, day]);
      clients.reflection
        .request({
          kind: "memory",
          target_day: day,
          instructions: REFLECTION_INSTRUCTIONS,
        })
        .then(() => {
          setTimeout(load, 10000);
          setTimeout(load, 40000);
        })
        .catch(() => {
          autoSubmitted.delete(day);
          setRunning((prev) => prev.filter((d) => d !== day));
          setFailed((prev) => [...prev, day]);
        });
    }
  }, [missing, clients]);

  if (!connected || missing === null || hidden) return null;

  const retry = (day: string) => {
    if (clients === null) return;
    setFailed((prev) => prev.filter((d) => d !== day));
    autoSubmitted.add(day);
    setRunning((prev) => [...prev, day]);
    clients.reflection
      .request({
        kind: "memory",
        target_day: day,
        instructions: REFLECTION_INSTRUCTIONS,
      })
      .then(() => {
        setTimeout(load, 10000);
        setTimeout(load, 40000);
      })
      .catch(() => {
        autoSubmitted.delete(day);
        setRunning((prev) => prev.filter((d) => d !== day));
        setFailed((prev) => [...prev, day]);
      });
  };

  if (missing.length === 0) {
    return (
      <div className="border-b border-line px-4 py-1.5 text-[12px] text-fg-dim">
        每日反思：无缺口。
      </div>
    );
  }
  const shown = missing.slice(-3);
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-warning/30 bg-warning-soft px-4 py-2 text-[12px]">
      <span className="text-warning">
        有 {missing.length} 天未完成每日反思
        {missing.length > shown.length && "，仅显示最近 3 天"}：
      </span>
      {shown.map((day) => (
        <span key={day} className="flex items-center gap-1.5">
          <span className="rounded bg-bg-elev px-1.5 py-0.5">{day}</span>
          {running.includes(day) ? (
            <span className="flex items-center gap-1 rounded border border-warning/40 px-2 py-0.5 text-warning">
              <Loader2 size={10} className="animate-spin" />
              自动补跑中…
            </span>
          ) : failed.includes(day) ? (
            <button
              onClick={() => retry(day)}
              className="rounded border border-warning/40 px-2 py-0.5 text-warning hover:bg-warning/10"
            >
              自动提交失败，点击重试
            </button>
          ) : (
            <button
              onClick={() => retry(day)}
              className="rounded border border-warning/40 px-2 py-0.5 text-warning hover:bg-warning/10"
            >
              补跑
            </button>
          )}
        </span>
      ))}
      <button
        onClick={() => setHidden(true)}
        className="ml-auto text-fg-dim hover:text-fg"
        title="本次会话不再提示"
      >
        ✕
      </button>
    </div>
  );
}

function useProjectRoot(): string {
  return useAppStore((s) => s.projectRoot) || "";
}

/** Search hands off to the existing conversation flow (km.search domain). */
function KmSearchView() {
  const [query, setQuery] = useState("");
  const setActiveTab = useAppStore((s) => s.setActiveTab);
  const connected = useConnectionStore((s) => s.phase === "connected");
  const epoch = useConnectionStore((s) => s.epoch);
  const submit = useCallback(() => {
    const value = query.trim();
    if (!value || !connected) return;
    void sendUserMessage(
      epoch,
      `请用 km.search 检索：${value}，给出结果列表与出处 refs。`,
    );
    setActiveTab("chat");
  }, [query, connected, epoch, setActiveTab]);

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 p-8">
      <h2 className="text-lg font-semibold">知识检索</h2>
      <p className="text-[13px] text-fg-dim">
        输入问题后进入对话检索（km.search 域，词法 + 向量混合，结果带真实来源引用）。
      </p>
      <div className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
          }}
          placeholder="例如：混合检索怎么设计？"
          className="flex-1 rounded-lg border border-line bg-bg-elev px-3 py-2 text-[14px] outline-none focus:border-accent"
        />
        <button
          onClick={submit}
          disabled={!connected || !query.trim()}
          className="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-[14px] text-white disabled:opacity-40"
        >
          <Search size={14} />
          检索
        </button>
      </div>
    </div>
  );
}

function useKmData<T>(loader: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const root = useProjectRoot();
  const reload = useCallback(() => {
    if (!isTauriShell() || !root) {
      setError("桌面端可用（浏览器版无法读取本地知识库文件）。");
      return;
    }
    setLoading(true);
    setError(null);
    loader()
      .then((value) => {
        setData(value);
        setError(null);
      })
      .catch((e: string) => setError(String(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [root, loader]);
  useEffect(() => {
    reload();
  }, [reload]);
  return { data, error, loading, reload };
}

const CONFIDENCE_STYLE: Record<string, string> = {
  high: "text-emerald-600 bg-emerald-500/10",
  medium: "text-amber-600 bg-amber-500/10",
  low: "text-fg-dim bg-line",
};

function KmCardsView({ onOpenDoc }: { onOpenDoc: (doc: KmDocHit) => void }) {
  const root = useProjectRoot();
  const loader = useCallback(
    () => invoke<KmCardEntry[]>("km_cards", { projectRoot: root }),
    [root],
  );
  const { data, error, loading, reload } = useKmData<KmCardEntry[]>(loader);
  if (error) return <KmNotice text={error} onRetry={reload} />;
  if (loading || data === null) return <KmLoading />;
  if (data.length === 0)
    return <KmNotice text="还没有知识卡片——每日反思会自动生成。" onRetry={reload} />;
  return (
    <div className="grid grid-cols-1 gap-4 p-6 lg:grid-cols-2 xl:grid-cols-3">
      {data.map((card, index) => (
        <div
          key={`${card.day}-${index}`}
          className="flex flex-col gap-2 rounded-xl border border-line bg-bg-elev p-4 text-[13px] leading-relaxed"
        >
          <div className="flex items-center justify-between text-[11px] text-fg-dim">
            <span className="rounded bg-accent-soft px-1.5 py-0.5 text-accent">
              知识卡片
            </span>
            <span className="flex items-center gap-2">
              <span
                className={`rounded px-1.5 py-0.5 ${
                  CONFIDENCE_STYLE[card.confidence] ?? CONFIDENCE_STYLE.low
                }`}
              >
                {card.confidence}
              </span>
              {card.day}
            </span>
          </div>
          <div className="font-semibold text-fg">{card.question}</div>
          <p className="whitespace-pre-wrap text-fg-dim">{card.answer}</p>
          {card.tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {card.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded bg-line px-1.5 py-0.5 text-[11px] text-fg-dim"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
          {card.sources.length > 0 && (
            <div className="mt-auto flex flex-wrap gap-1.5 border-t border-line pt-2.5">
              {card.sources.map((source) => (
                <button
                  key={source.id}
                  onClick={() =>
                    onOpenDoc({
                      id: source.id,
                      title: source.title,
                      path: source.path,
                      source: source.source,
                    })
                  }
                  className="flex items-center gap-1.5 rounded-md border border-line px-2 py-1 text-[11px] text-fg-dim transition-colors hover:border-accent hover:text-accent"
                  title={`查看来源：${source.title}`}
                >
                  <span
                    className="inline-block h-1.5 w-1.5 rounded-full"
                    style={{
                      background: SOURCE_COLORS[source.source] ?? "#94a3b8",
                    }}
                  />
                  {source.title.slice(0, 22)}
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/** Right-side drawer showing one knowledge document's full Markdown. */
function KmDocDrawer({
  doc,
  onClose,
}: {
  doc: KmDocHit | null;
  onClose: () => void;
}) {
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const root = useProjectRoot();

  useEffect(() => {
    if (!doc) {
      setContent(null);
      setError(null);
      return;
    }
    setContent(null);
    setError(null);
    invoke<KmDocument>("km_document", { projectRoot: root, kmId: doc.id })
      .then((document) => setContent(document.markdown))
      .catch((e: string) => setError(String(e)));
  }, [doc, root]);

  if (!doc) return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <aside className="relative z-10 flex h-full w-[560px] max-w-[85vw] flex-col border-l border-line bg-bg shadow-2xl">
        <header className="flex items-start gap-2 border-b border-line px-4 py-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-[11px] text-fg-dim">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ background: SOURCE_COLORS[doc.source] ?? "#94a3b8" }}
              />
              {doc.source}
            </div>
            <h3 className="truncate text-[15px] font-semibold">{doc.title}</h3>
            <p className="truncate text-[11px] text-fg-dim">{doc.path}</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg border border-line px-2 py-1 text-[12px] text-fg-dim hover:text-fg"
          >
            ✕
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
          {error && <p className="text-[13px] text-warning">{error}</p>}
          {!error && content === null && <KmLoading />}
          {content !== null && (
            <pre className="whitespace-pre-wrap font-sans text-[13px] leading-relaxed">
              {content}
            </pre>
          )}
        </div>
      </aside>
    </div>
  );
}

function KmGraphView() {
  const [mode, setMode] = useState<"local" | "overview">("local");
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-3 border-b border-line px-4 py-2 text-[12px]">
        <div className="flex gap-1">
          {(
            [
              ["local", "邻域浏览"],
              ["overview", "全图概览"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setMode(key)}
              className={`rounded-lg px-2.5 py-1 transition-colors ${
                mode === key ? "bg-active text-accent" : "text-fg-dim hover:text-fg"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <span className="text-fg-dim">
          {mode === "local"
            ? "从一篇文档出发，看它的真实引用边；点邻居继续走。"
            : "连接度最高的文档子图。"}
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        {mode === "local" ? <KmNeighborhoodExplorer /> : <KmOverviewGraph />}
      </div>
    </div>
  );
}

const DIRECTION_BADGE: Record<KmNeighbor["direction"], string> = {
  out: "出链 →",
  in: "← 入链",
  both: "↔ 双向",
};

/** One-hop explorer: pick a document, see (and walk) its real link edges. */
function KmNeighborhoodExplorer() {
  const root = useProjectRoot();
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<KmDocHit[] | null>(null);
  const [center, setCenter] = useState<KmNeighborhoodData | null>(null);
  const [stack, setStack] = useState<KmDocHit[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const openDoc = useCallback(
    (doc: KmDocHit, pushCurrent: boolean) => {
      setBusy(true);
      setError(null);
      setHits(null);
      setQuery("");
      invoke<KmNeighborhoodData>("km_neighborhood", {
        projectRoot: root,
        kmId: doc.id,
      })
        .then((data) => {
          setCenter(data);
          if (pushCurrent) {
            setStack((prev) => [...prev, doc].slice(-12));
          }
        })
        .catch((e: string) => setError(String(e)))
        .finally(() => setBusy(false));
    },
    [root],
  );

  // Default view: the most recently imported document (cards/chats surface
  // first in practice, which is exactly the interesting neighborhood).
  const rootRef = useRef(root);
  useEffect(() => {
    invoke<KmDocHit[]>("km_find_docs", {
      projectRoot: rootRef.current,
      query: "",
      limit: 1,
    })
      .then((found) => {
        if (found.length > 0) openDoc(found[0], false);
      })
      .catch((e: string) => setError(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Search-as-you-type (debounced).
  useEffect(() => {
    const value = query.trim();
    if (!value) {
      setHits(null);
      return;
    }
    const timer = setTimeout(() => {
      invoke<KmDocHit[]>("km_find_docs", {
        projectRoot: root,
        query: value,
        limit: 8,
      })
        .then(setHits)
        .catch(() => setHits([]));
    }, 250);
    return () => clearTimeout(timer);
  }, [query, root]);

  const back = useCallback(() => {
    setStack((prev) => {
      const previous = prev[prev.length - 1];
      if (previous) openDoc(previous, false);
      return prev.slice(0, -1);
    });
  }, [openDoc]);

  if (error)
    return (
      <KmNotice
        text={error}
        onRetry={() => center && openDoc(center.center, false)}
      />
    );
  if (!center) return <KmLoading />;

  return (
    <div className="flex flex-col gap-3 p-4">
      <div className="relative flex items-center gap-2">
        {stack.length > 0 && (
          <button
            onClick={back}
            className="rounded-lg border border-line px-2.5 py-1.5 text-[12px] text-fg-dim hover:text-fg"
          >
            ← 返回
          </button>
        )}
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="输入标题或路径关键词，选一篇文档作为中心…"
          className="flex-1 rounded-lg border border-line bg-bg-elev px-3 py-2 text-[13px] outline-none focus:border-accent"
        />
        {busy && <Loader2 size={14} className="animate-spin text-fg-dim" />}
        {hits !== null && hits.length > 0 && (
          <div className="absolute top-full left-10 z-10 mt-1 max-w-xl overflow-hidden rounded-lg border border-line bg-bg-elev shadow-lg">
            {hits.map((hit) => (
              <button
                key={hit.id}
                onClick={() => openDoc(hit, true)}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] hover:bg-active"
              >
                <span
                  className="inline-block h-2 w-2 shrink-0 rounded-full"
                  style={{ background: SOURCE_COLORS[hit.source] ?? "#94a3b8" }}
                />
                <span className="truncate">{hit.title}</span>
                <span className="ml-auto shrink-0 text-[11px] text-fg-dim">
                  {hit.source}
                </span>
              </button>
            ))}
          </div>
        )}
        {hits !== null && hits.length === 0 && (
          <div className="absolute top-full left-10 z-10 mt-1 rounded-lg border border-line bg-bg-elev px-3 py-2 text-[12px] text-fg-dim shadow-lg">
            没有匹配的文档
          </div>
        )}
      </div>

      {stack.length > 0 && (
        <div className="flex flex-wrap items-center gap-1 text-[11px] text-fg-dim">
          {stack.map((doc, index) => (
            <span
              key={`${doc.id}-${index}`}
              className="rounded bg-bg-elev px-1.5 py-0.5"
            >
              {doc.title.slice(0, 14)}
            </span>
          ))}
        </div>
      )}

      <KmNeighborhoodCanvas
        data={center}
        onSelect={(id) => {
          const hit = center.neighbors.find((n) => n.id === id);
          if (hit)
            openDoc(
              { id: hit.id, title: hit.title, path: hit.path, source: hit.source },
              true,
            );
        }}
      />
    </div>
  );
}

function KmNeighborhoodCanvas({
  data,
  onSelect,
}: {
  data: KmNeighborhoodData;
  onSelect: (id: string) => void;
}) {
  const size = 760;
  const cx = size / 2;
  const cy = 300;
  const radius = 210;
  const positions = new Map<string, { x: number; y: number }>();
  data.neighbors.forEach((neighbor, index) => {
    const angle =
      (2 * Math.PI * index) / Math.max(data.neighbors.length, 1) - Math.PI / 2;
    positions.set(neighbor.id, {
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
    });
  });
  if (data.neighbors.length === 0) {
    return (
      <div className="p-10 text-center text-[13px] text-fg-dim">
        「{data.center.title}
        」没有引用边——它没有出链，也没有任何文档引用它（孤立文档）。
      </div>
    );
  }
  return (
    <svg width={size} height={560} className="max-w-full">
      <defs>
        <marker
          id="km-arrow"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#8886" />
        </marker>
      </defs>
      {data.neighbors.map((neighbor) => {
        const position = positions.get(neighbor.id);
        if (!position) return null;
        const outward = neighbor.direction !== "in";
        const inward = neighbor.direction !== "out";
        return (
          <g key={neighbor.id}>
            {outward && (
              <line
                x1={cx}
                y1={cy}
                x2={position.x}
                y2={position.y}
                stroke="#8888"
                strokeWidth={1.2}
                markerEnd="url(#km-arrow)"
              />
            )}
            {inward && (
              <line
                x1={position.x}
                y1={position.y}
                x2={cx}
                y2={cy}
                stroke="#8884"
                strokeWidth={1}
                strokeDasharray="4 3"
                markerEnd="url(#km-arrow)"
              />
            )}
          </g>
        );
      })}
      {data.neighbors.map((neighbor) => {
        const position = positions.get(neighbor.id);
        if (!position) return null;
        return (
          <g
            key={neighbor.id}
            className="cursor-pointer"
            onClick={() => onSelect(neighbor.id)}
          >
            <circle
              cx={position.x}
              cy={position.y}
              r={8}
              fill={SOURCE_COLORS[neighbor.source] ?? "#94a3b8"}
            />
            <text
              x={position.x}
              y={position.y + 22}
              fontSize={11}
              textAnchor="middle"
              className="fill-fg"
            >
              {neighbor.title.slice(0, 18)}
            </text>
            <text
              x={position.x}
              y={position.y + 35}
              fontSize={9}
              textAnchor="middle"
              className="fill-fg-dim"
            >
              {DIRECTION_BADGE[neighbor.direction]}
            </text>
          </g>
        );
      })}
      <circle cx={cx} cy={cy} r={16} fill="#7c6cf6" />
      <text
        x={cx}
        y={cy + 34}
        fontSize={12}
        textAnchor="middle"
        className="fill-fg"
        fontWeight="600"
      >
        {data.center.title.slice(0, 24)}
      </text>
      <text
        x={cx}
        y={cy + 48}
        fontSize={10}
        textAnchor="middle"
        className="fill-fg-dim"
      >
        {data.center.source} · 点击邻居节点继续走
      </text>
    </svg>
  );
}

/** Whole-store overview: highest-degree subgraph on a circle. */
function KmOverviewGraph() {
  const root = useProjectRoot();
  const loader = useCallback(
    () => invoke<KmGraphData>("km_graph", { projectRoot: root, limit: 100 }),
    [root],
  );
  const { data, error, loading, reload } = useKmData<KmGraphData>(loader);
  if (error) return <KmNotice text={error} onRetry={reload} />;
  if (loading || data === null) return <KmLoading />;
  return (
    <div className="flex flex-col gap-3 p-4">
      <div className="flex items-center gap-4 text-[12px] text-fg-dim">
        <span>
          {data.nodes.length} 节点 · {data.edges.length} 条真实引用边
          {data.truncated && " · 已从全库按连接度截断"}
        </span>
        {Object.entries(SOURCE_COLORS).map(([source, color]) => (
          <span key={source} className="flex items-center gap-1">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ background: color }}
            />
            {source}
          </span>
        ))}
      </div>
      <KmGraphCanvas nodes={data.nodes} edges={data.edges} />
    </div>
  );
}

/** Deterministic circular layout: cheap, readable, no extra dependency. */
function KmGraphCanvas({
  nodes,
  edges,
}: {
  nodes: KmNode[];
  edges: { from: string; to: string }[];
}) {
  const size = 720;
  const radius = size / 2 - 60;
  const positions = new Map<string, { x: number; y: number }>();
  nodes.forEach((node, index) => {
    const angle = (2 * Math.PI * index) / Math.max(nodes.length, 1);
    positions.set(node.id, {
      x: size / 2 + radius * Math.cos(angle),
      y: size / 2 + radius * Math.sin(angle),
    });
  });
  return (
    <div className="overflow-auto rounded-xl border border-line bg-bg-elev p-2">
      <svg width={size} height={size} className="max-w-none">
        {edges.map((edge, index) => {
          const a = positions.get(edge.from);
          const b = positions.get(edge.to);
          if (!a || !b) return null;
          return (
            <line
              key={index}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke="#8884"
              strokeWidth={0.6}
            />
          );
        })}
        {nodes.map((node) => {
          const position = positions.get(node.id);
          if (!position) return null;
          const color = SOURCE_COLORS[node.source] ?? "#94a3b8";
          return (
            <g key={node.id}>
              <circle
                cx={position.x}
                cy={position.y}
                r={4}
                fill={color}
                className="cursor-pointer"
              >
                <title>{`${node.title} (${node.source})`}</title>
              </circle>
              {nodes.length <= 120 && (
                <text
                  x={position.x + 6}
                  y={position.y + 3}
                  fontSize={9}
                  className="fill-fg-dim"
                >
                  {node.title.slice(0, 18)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function KmIngestView() {
  const [vault, setVault] = useState("");
  const [dryRun, setDryRun] = useState(true);
  const [output, setOutput] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const root = useProjectRoot();

  const run = useCallback(() => {
    if (!isTauriShell()) {
      setOutput("桌面端可用（浏览器版无法调用本地 CLI）。");
      return;
    }
    setBusy(true);
    setOutput("");
    invoke<{ code: number; output: string }>("km_ingest", {
      projectRoot: root,
      obsidian: vault.trim() || null,
      dryRun,
    })
      .then((outcome) =>
        setOutput(`exit=${outcome.code}\n${outcome.output || "(no output)"}`),
      )
      .catch((e: string) => setOutput(`error: ${e}`))
      .finally(() => setBusy(false));
  }, [root, vault, dryRun]);

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 p-8">
      <h2 className="text-lg font-semibold">导入 Obsidian vault</h2>
      <p className="text-[13px] text-fg-dim">
        调用 <code>tinysoul km-ingest</code>
        ：增量导入（checksum 对比、删除记 tombstone）。先用 dry-run 预览变更。
      </p>
      <input
        value={vault}
        onChange={(e) => setVault(e.target.value)}
        placeholder="vault 目录的绝对路径，例如 D:\Obsidian\MyVault"
        className="rounded-lg border border-line bg-bg-elev px-3 py-2 text-[14px] outline-none focus:border-accent"
      />
      <label className="flex items-center gap-2 text-[13px]">
        <input
          type="checkbox"
          checked={dryRun}
          onChange={(e) => setDryRun(e.target.checked)}
        />
        dry-run（只预览，不写入）
      </label>
      <button
        onClick={run}
        disabled={busy || !vault.trim()}
        className="flex items-center gap-2 self-start rounded-lg bg-accent px-4 py-2 text-[14px] text-white disabled:opacity-40"
      >
        {busy && <Loader2 size={14} className="animate-spin" />}
        {dryRun ? "预览导入" : "执行导入"}
      </button>
      {output && (
        <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-bg-elev p-3 text-[12px]">
          {output}
        </pre>
      )}
    </div>
  );
}

function KmNotice({ text, onRetry }: { text: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 p-12 text-[13px] text-fg-dim">
      <span>{text}</span>
      <button
        onClick={onRetry}
        className="rounded-lg border border-line px-3 py-1.5 hover:text-fg"
      >
        重试
      </button>
    </div>
  );
}

function KmLoading() {
  return (
    <div className="flex items-center justify-center gap-2 p-12 text-[13px] text-fg-dim">
      <Loader2 size={14} className="animate-spin" />
      读取知识库…
    </div>
  );
}
