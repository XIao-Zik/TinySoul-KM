import { beforeEach } from "vitest";

import { useAppStore } from "../src/store/appStore";

/**
 * UI-string tests assert the English source (the i18n key itself), so every
 * test runs in the en locale regardless of the user-facing default. zh-CN
 * rendering has dedicated coverage in src/i18n/index.test.ts and the
 * settings localization test, which opt into that locale explicitly.
 */
beforeEach(() => {
  useAppStore.setState({ locale: "en" });
});
