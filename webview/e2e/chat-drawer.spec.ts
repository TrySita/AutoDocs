import { test, expect } from "@playwright/test";

test.describe.serial("Chat drawer messaging", () => {
  const REPO_NAME = "Chat Test Repo";
  const REPO_URL = "https://github.com/aperswal/4buttons.git";

  function getUrlParam(url: string, key: string): string | null {
    const u = new URL(url, "http://localhost");
    return u.searchParams.get(key);
  }

  test("opens chat and navigates via citation link", async ({ page }) => {
    test.setTimeout(120_000);

    // Stub only message history to control assistant citations
    let messageHistoryCalls = 0;
    const userPrompt = "find me where we handle the love component";
    await page.route("**/api/messages**", async (route) => {
      messageHistoryCalls += 1;
      if (messageHistoryCalls === 1) {
        const body = {
          messages: [],
          summary: null,
          conversationId: "default",
        };
        await route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
        return;
      }
      const assistantContent = `Sure — see the handler here: [love handler](file::123:definition::456).`;
      const now = new Date().toISOString();
      const body = {
        messages: [
          { id: `user-0-${now}`, role: "user", content: userPrompt, timestamp: now },
          { id: `assistant-1-${now}`, role: "assistant", content: assistantContent, timestamp: now },
        ],
        summary: null,
        conversationId: "default",
      };
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    });

    // Create a unique repository via the UI (no mocks)
    const unique = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    const uniqueName = `${REPO_NAME}-${unique}`;
    const expectedSlug = uniqueName
      .trim()
      .toLowerCase()
      .replace(/\s+/g, "-")
      .replace(/[^a-z0-9-_]/g, "");

    await page.goto("/workspace");
    await page.getByRole("button", { name: "Add New" }).click();
    await page.getByPlaceholder("e.g. Excalidraw").fill(uniqueName);
    await page.getByPlaceholder("https://github.com/org/repo").fill(REPO_URL);
    await page.getByRole("button", { name: "Add" }).click();
    await expect(page.getByText(uniqueName, { exact: true })).toBeVisible({ timeout: 30_000 });

    // Open the repo workspace
    await page.getByText(uniqueName, { exact: true }).first().click();
    await page.waitForURL(new RegExp(`/workspace/${expectedSlug}(/docs)?`));
    // Chat drawer is open by default; verify it's visible
    await expect(page.getByText("Martin")).toBeVisible({ timeout: 60000 });

    // Send a message that contains a citation link; the UI should render it
    const input = page.getByPlaceholder("Ask about this file...");
    await input.fill(userPrompt);
    await input.press("Enter");
    await expect(page.getByText(userPrompt, { exact: true })).toBeVisible();

    // Reload to fetch stubbed assistant history with citation
    await page.reload();
    await expect(page.getByText("Martin")).toBeVisible();

    // Click the rendered citation link (assistant message) and verify navigation
    const citationLink = page.getByRole("link", { name: "love handler" });
    await expect(citationLink).toBeVisible();
    await citationLink.click();

    // Verify we navigated to docs with correct query params
    await expect
      .poll(() => {
        const url = page.url();
        const hasDocs = /\/workspace\/.+\/docs/.test(url);
        const f = getUrlParam(url, "fileId");
        const d = getUrlParam(url, "definitionId");
        return hasDocs && f === "123" && d === "456";
      }, { timeout: 15_000 })
      .toBeTruthy();
  });
});
