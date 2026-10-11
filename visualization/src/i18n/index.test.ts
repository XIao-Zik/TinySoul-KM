import { describe, expect, it } from "vitest";

import { collapseSource, translate } from ".";
import { DEFAULT_LOCALE } from "./locale";

describe("global i18n", () => {
  it("defaults to Chinese", () => {
    expect(DEFAULT_LOCALE).toBe("zh-CN");
  });

  it("renders the zh-CN dictionary value for translated sources", () => {
    expect(translate("zh-CN", "Organize")).toBe("整理");
    expect(translate("zh-CN", "disconnected")).toBe("未连接");
  });

  it("falls back to the English source when untranslated", () => {
    expect(translate("zh-CN", "No such dictionary entry")).toBe(
      "No such dictionary entry",
    );
  });

  it("renders the source itself in the en locale", () => {
    expect(translate("en", "Organize")).toBe("Organize");
  });

  it("interpolates {name} tokens and keeps unknown tokens", () => {
    expect(translate("zh-CN", "day {day}", { day: "2026-10-11" })).toBe(
      "业务日 2026-10-11",
    );
    expect(translate("en", "day {day}", { day: "2026-10-11" })).toBe(
      "day 2026-10-11",
    );
    expect(translate("en", "day {day}")).toBe("day {day}");
  });

  it("collapses multi-line JSX sources before lookup", () => {
    expect(collapseSource("The backend   is not responding —\n the conversation")).toBe(
      "The backend is not responding — the conversation",
    );
    expect(
      translate("zh-CN", "The backend\n  is not responding — the conversation stays in place and reconnects automatically."),
    ).toBe("后端无响应——对话保持原位，将自动重连。");
  });
});
