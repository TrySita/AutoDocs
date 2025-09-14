import { test, expect } from "@playwright/test";
import { encodeTRPCResponse, type PublicProject } from "./test-utils";

test.describe.serial("Chat drawer messaging", () => {
  const REPO_NAME = "Chat Test Repo";
  const REPO_URL = "https://github.com/aperswal/4buttons.git";
  const slug = `chat-${Date.now().toString(36)}`;
  const userPrompt = "find me where we handle the love component";

  test("streams then persists messages with citations", async ({ page }) => {
    test.setTimeout(120_000);
    // Step: stub projects list and message history
    let messageHistoryCalls = 0;
    await page.route("**/api/trpc/projects.getPublicProjects**", async (route) => {
      const reqBody = route.request().postData() || "[]";
      const idMatch = /"id"\s*:\s*(\d+)/.exec(reqBody);
      const id = idMatch ? Number.parseInt(idMatch[1], 10) : 0;
      const payload: PublicProject[] = [
        {
          id: "00000000-0000-0000-0000-000000000001",
          name: REPO_NAME,
          slug,
          repositoryUrl: REPO_URL,
          isActive: true,
          sortOrder: 0,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          dbUrl: null,
          dbKey: null,
          latestJobId: null,
          latestJobStatus: null,
          description: null,
          logoUrl: null,
        },
      ];
      await route.fulfill({ contentType: "application/json", body: encodeTRPCResponse(id, payload) });
    });
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
    // Step: open workspace and repo
    await page.goto("/workspace");
    const card = page.getByText(REPO_NAME, { exact: true });
    await expect(card).toBeVisible();
    await card.click();
    await page.waitForURL(new RegExp(`/workspace/${slug}(/docs)?`));
    // Step: chat drawer visible
    await expect(page.getByText("Martin")).toBeVisible();
    // Step: send message
    const input = page.getByPlaceholder("Ask about this file...");
    await input.fill(userPrompt);
    await input.press("Enter");
    // Step: user message visible
    await expect(page.getByText(userPrompt, { exact: true })).toBeVisible();
    // Step: streaming placeholder visible
    const loadingDot = page.locator("div.w-2.h-2.bg-current.rounded-full");
    await expect(loadingDot.first()).toBeVisible({ timeout: 5000 });
    // Step: reload and verify persistence
    await page.reload();
    await expect(page.getByText("Martin")).toBeVisible();
    // Step: persisted user message visible
    await expect(page.getByText(userPrompt, { exact: true })).toBeVisible();
    // Step: citation link has correct href
    const citationHref = `/workspace/${slug}/docs?fileId=123&definitionId=456`;
    const citationLink = page.getByRole("link", { name: "love handler" });
    await expect(citationLink).toBeVisible();
    await expect(citationLink).toHaveAttribute("href", citationHref);
  });
});
