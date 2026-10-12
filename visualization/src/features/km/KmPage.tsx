import { useCallback, useEffect, useState } from "react";
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
 * Knowledge (km) views: search hand-off, card feed, link graph, and the
 * import panel. Cards/graph read the local knowledge store through Tauri
 * commands (desktop shell only); search reuses the existing Turn flow so the
 * conversation, trace and refs stay in one place.
 */

type KmView = "search" | "cards" | "graph" | "ingest";

interface KmCard {
  day: string;
  path: string;
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

const SOURCE_COLORS: Record<string, string> = {
  obsidian: "#8b7cf6",
  chat: "#38bdf8",
  card: "#f59e0b",
};

export function KmPage() {
  const [view, setView] = useState<KmView>("search");
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
        {view === "search" && <KmSearchView />}
        {view === "cards" && <KmCardsView />}
        {view === "graph" && <KmGraphView />}
        {view === "ingest" && <KmIngestView />}
      </div>
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

function KmCardsView() {
  const root = useProjectRoot();
  const loader = useCallback(
    () => invoke<KmCard[]>("km_cards", { projectRoot: root }),
    [root],
  );
  const { data, error, loading, reload } = useKmData<KmCard[]>(loader);
  if (error) return <KmNotice text={error} onRetry={reload} />;
  if (loading || data === null) return <KmLoading />;
  if (data.length === 0)
    return <KmNotice text="还没有知识卡片——每日反思会自动生成。" onRetry={reload} />;
  return (
    <div className="grid grid-cols-1 gap-4 p-6 lg:grid-cols-2 xl:grid-cols-3">
      {data.flatMap((card) =>
        card.markdown
          .split("## 卡片")
          .slice(1)
          .map((section, index) => (
            <div
              key={`${card.day}-${index}`}
              className="rounded-xl border border-line bg-bg-elev p-4 text-[13px] leading-relaxed"
            >
              <div className="mb-2 flex items-center justify-between text-[11px] text-fg-dim">
                <span className="rounded bg-accent-soft px-1.5 py-0.5 text-accent">
                  知识卡片
                </span>
                <span>{card.day}</span>
              </div>
              <pre className="whitespace-pre-wrap font-sans">{section.trim()}</pre>
            </div>
          )),
      )}
    </div>
  );
}

function KmGraphView() {
  const root = useProjectRoot();
  const loader = useCallback(
    () => invoke<KmGraphData>("km_graph", { projectRoot: root, limit: 100 }),
    [root],
  );
  const { data, error, loading, reload } = useKmData<KmGraphData>(loader);
  if (error) return <KmNotice text={error} onRetry={reload} />;
  if (loading || data === null) return <KmLoading />;
  return (
    <div className="flex flex-col gap-3 p-6">
      <div className="flex items-center gap-4 text-[12px] text-fg-dim">
        <span>
          {data.nodes.length} 节点（按连接度取前 {data.nodes.length}）· {data.edges.length} 条真实引用边
          {data.truncated && "· 已从全库截断"}
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
        setOutput(
          `exit=${outcome.code}\n${outcome.output || "(no output)"}`,
        ),
      )
      .catch((e: string) => setOutput(`error: ${e}`))
      .finally(() => setBusy(false));
  }, [root, vault, dryRun]);

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 p-8">
      <h2 className="text-lg font-semibold">导入 Obsidian vault</h2>
      <p className="text-[13px] text-fg-dim">
        调用 <code>tinysoul km-ingest</code>：增量导入（checksum 对比、删除记
        tombstone）。先用 dry-run 预览变更。
      </p>
      <input
        value={vault}
        onChange={(e) => setVault(e.target.value)}
        placeholder="vault 目录的绝对路径，例如 D:\\Obsidian\\MyVault"
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
