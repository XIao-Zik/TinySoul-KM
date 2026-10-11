// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Timing-sensitive real-timer poll tests: they need extra wall clock when
// the full suite runs alongside the dev processes on a loaded machine.
vi.setConfig({ testTimeout: 30000 });

import type { JobDetail, JobList, JobOutputPage } from "../../api/v2/types";
import {
  FakeEndpoint,
  jsonResponse,
  makeStatus,
  resetAppStores,
  wireConnectedStores,
} from "../../app/testing";
import { useRuntimeUi } from "./store";
import { JobsTab } from "./jobsTab";

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const TURN = "turn_jobs_1";
const JOB = "job_1";

let container: HTMLDivElement;
let root: Root;
let endpoint: FakeEndpoint;
let epoch: number;

function jobSummary(state: string): JobDetail {
  return {
    job_id: JOB,
    kind: "execution.process",
    state,
    summary: "run the suite",
    reason: "",
    pending_inputs: [],
    result_refs: ["workspace:jobs/job_1"],
  };
}

function outputPage(
  items: { channel: string; text: string }[],
  next: string,
  truncated = false,
): JobOutputPage {
  return {
    job_id: JOB,
    items,
    next_continuation: next,
    truncated,
    result_locators: [],
  };
}

beforeEach(() => {
  resetAppStores();
  useRuntimeUi.setState({ tab: "jobs", selectedJobId: null });
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  endpoint = new FakeEndpoint();
  ({ epoch } = wireConnectedStores(
    endpoint,
    makeStatus({ activeTurnId: TURN, activeDay: "2026-09-29" }),
  ));
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  resetAppStores();
});

async function renderTab(): Promise<void> {
  await act(async () => {
    root.render(<JobsTab epoch={epoch} listIntervalMs={5} outputIntervalMs={5} />);
  });
}

/** Let the poll loops run for a while (real timers, tiny intervals). */
async function wait(ms = 40): Promise<void> {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, ms));
  });
}

/**
 * Retry under real timers until `ready` stops throwing or the deadline
 * passes. The poll loops need several real 5ms ticks per visible state; a
 * fixed sleep flakes when the suite runs under heavy machine load.
 */
async function waitUntil<T>(ready: () => T, timeoutMs = 5000): Promise<T> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    try {
      return ready();
    } catch {
      if (Date.now() > deadline) throw new Error("condition not met within timeout");
      await wait(20);
    }
  }
}

function jobRow(): HTMLButtonElement {
  const row = Array.from(container.querySelectorAll("button")).find((button) =>
    button.textContent?.includes("run the suite"),
  );
  if (!row) throw new Error("job row not rendered");
  return row as HTMLButtonElement;
}

function buttonByText(text: string): HTMLButtonElement {
  const button = Array.from(container.querySelectorAll("button")).find(
    (candidate) => candidate.textContent?.includes(text),
  );
  if (!button) throw new Error(`button "${text}" not rendered`);
  return button as HTMLButtonElement;
}

describe("JobsTab", () => {
  // Timing-sensitive real-timer poll test: needs extra wall clock when the
  // full suite runs alongside the dev processes on a loaded machine.
  it("lists the bound turn's jobs and reads detail/output only for the selected one", async () => {
    endpoint.get(`/v2/requests/${TURN}/jobs`, () =>
      jsonResponse({ request_id: TURN, jobs: [jobSummary("running")] } satisfies JobList),
    );
    endpoint.get(`/v2/requests/${TURN}/jobs/${JOB}`, () =>
      jsonResponse(jobSummary("running")),
    );
    let outputCalls = 0;
    endpoint.get(`/v2/requests/${TURN}/jobs/${JOB}/output`, (request) => {
      outputCalls += 1;
      const url = new URL(request.url);
      const continuation = url.searchParams.get("continuation");
      return continuation === null
        ? jsonResponse(outputPage([{ channel: "stdout", text: "ready\n" }], "c2"))
        : jsonResponse(outputPage([], "c2"));
    });

    await renderTab();
    const row = await waitUntil(() => jobRow());

    // Nothing job-specific is read before a selection.
    expect(endpoint.calls(`/v2/requests/${TURN}/jobs/${JOB}`)).toHaveLength(0);
    expect(container.textContent).toContain("execution.process");

    await act(async () => row.click());
    await waitUntil(() => {
      expect(container.textContent).toContain("ready");
      expect(container.textContent).toContain("stdout");
    });
    // A running job keeps polling its output position.
    await waitUntil(() => {
      expect(outputCalls).toBeGreaterThan(1);
    });
  });

  it("stops a job on the formal snapshot and drains remaining output", async () => {
    let state = "running";
    endpoint.get(`/v2/requests/${TURN}/jobs`, () =>
      jsonResponse({ request_id: TURN, jobs: [jobSummary(state)] } satisfies JobList),
    );
    endpoint.get(`/v2/requests/${TURN}/jobs/${JOB}`, () =>
      jsonResponse(jobSummary(state)),
    );
    endpoint.post(`/v2/requests/${TURN}/jobs/${JOB}/stop`, () => {
      state = "stopped";
      return jsonResponse(jobSummary("stopped"));
    });
    let outputCalls = 0;
    endpoint.get(`/v2/requests/${TURN}/jobs/${JOB}/output`, (request) => {
      outputCalls += 1;
      const continuation = new URL(request.url).searchParams.get("continuation");
      return continuation === null
        ? jsonResponse(outputPage([{ channel: "stdout", text: "line\n" }], "c2"))
        : jsonResponse(outputPage([], "c2"));
    });

    await renderTab();
    const row = await waitUntil(() => jobRow());
    await act(async () => row.click());
    await waitUntil(() => buttonByText("Stop job"));

    await act(async () => buttonByText("Stop job").click());
    await waitUntil(() => {
      expect(endpoint.calls(`/v2/requests/${TURN}/jobs/${JOB}/stop`, "POST")).toHaveLength(1);
      expect(container.textContent).toContain("stopped");
    });
    // Terminal + drained ⇒ exhausted: the output polling stops.
    const settled = outputCalls;
    await wait(60);
    expect(outputCalls).toBe(settled);
  });

  it("freezes the last read when the turn is reclaimed, keeping artifact links", async () => {
    let reclaimed = false;
    endpoint.get(`/v2/requests/${TURN}/jobs`, () =>
      jsonResponse(
        reclaimed
          ? { request_id: TURN, jobs: [] }
          : { request_id: TURN, jobs: [jobSummary("running")] },
      ),
    );
    endpoint.get(`/v2/requests/${TURN}/jobs/${JOB}`, () =>
      jsonResponse(jobSummary("running")),
    );
    endpoint.get(`/v2/requests/${TURN}/jobs/${JOB}/output`, () =>
      jsonResponse(outputPage([], "c2")),
    );

    await renderTab();
    const row = await waitUntil(() => jobRow());
    await act(async () => row.click());
    await waitUntil(() => {
      expect(container.textContent).toContain("Stop job");
    });

    reclaimed = true;
    await waitUntil(() => {
      expect(container.textContent).toContain("jobs were reclaimed");
    });
    expect(container.textContent).toContain("Turn process");
    // The frozen view keeps the last read but offers no job actions.
    expect(container.textContent).not.toContain("Stop job");
    const readsBefore = endpoint.calls(`/v2/requests/${TURN}/jobs/${JOB}`).length;
    await wait(60);
    expect(endpoint.calls(`/v2/requests/${TURN}/jobs/${JOB}`).length).toBe(readsBefore);
  });
});
