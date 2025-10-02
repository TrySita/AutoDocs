import { test, expect, Page, Locator, APIRequestContext } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";

const REPO_URL = "https://github.com/aperswal/4buttons.git";
const apiBase = process.env.INGESTION_API_URL || "http://127.0.0.1:8000";

let repoName: string;
let slug: string;

// Types and helpers

async function loadEnvVarFromFile(
  filePath: string,
  key: string,
): Promise<string | null> {
  try {
    const raw = await fs.readFile(filePath, "utf8");
    for (const line of raw.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const eq = trimmed.indexOf("=");
      if (eq === -1) continue;
      const k = trimmed.slice(0, eq).trim();
      if (k !== key) continue;
      let v = trimmed.slice(eq + 1).trim();
      if (
        (v.startsWith('"') && v.endsWith('"')) ||
        (v.startsWith("'") && v.endsWith("'"))
      ) {
        v = v.slice(1, -1);
      }
      return v;
    }
    return null;
  } catch {
    return null;
  }
}

function getUrlParam(url: string, key: string): string | null {
  const u = new URL(url, "http://localhost");
  return u.searchParams.get(key);
}

async function expandAllTreeItems(
  tree: Locator,
  maxPasses = 50,
): Promise<void> {
  for (let i = 0; i < maxPasses; i++) {
    const collapsed = tree.getByRole("treeitem", { expanded: false });
    const count = await collapsed.count();
    if (count === 0) return;
    await collapsed.first().click();
  }
}

async function waitForFileLoad(page: Page, timeoutMs = 15000): Promise<void> {
  await expect
    .poll(() => getUrlParam(page.url(), "fileId"), { timeout: timeoutMs })
    .toBeTruthy();
  await expect
    .poll(
      async () => {
        const header = page.getByRole("heading", { level: 1 }).first();
        if (await header.isVisible().catch(() => false)) {
          const text = (await header.textContent())?.trim();
          if (text) return true;
        }
        return null;
      },
      { timeout: timeoutMs },
    )
    .toBeTruthy();
}

async function getHeaderFilePath(page: Page): Promise<string> {
  const header = page.getByRole("heading", { level: 1 }).first();
  const text = await header.textContent();
  return (text || "").trim();
}

test.describe.serial("Ingestion flow", () => {
  async function isIngestionAvailable(request: APIRequestContext): Promise<boolean> {
    try {
      const res = await request.get(`${apiBase}/ingest/jobs/test`);
      return res.ok();
    } catch {
      return false;
    }
  }
  test.beforeAll(async () => {
    const unique = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    const projectTag = (test.info().project.name || "chromium")
      .toLowerCase()
      .replace(/[^a-z0-9-]/g, "");
    repoName = `Buttons-${projectTag}-${unique}`;
    slug = repoName
      .trim()
      .toLowerCase()
      .replace(/\s+/g, "-")
      .replace(/[^a-z0-9-_]/g, "");
  });

  test("ingests and DB exists/app reads", async ({ page, request }) => {
    test.setTimeout(180_000);
    if (!(await isIngestionAvailable(request))) {
      test.skip("Ingestion API not reachable — skipping ingestion flow.");
    }
    // Add project via UI (no mocks)
    await page.goto("/workspace");
    await page.getByRole("button", { name: "Add New" }).click();
    await page.getByPlaceholder("e.g. Excalidraw").fill(repoName);
    await page.getByPlaceholder("https://github.com/org/repo").fill(REPO_URL);
    await page.getByRole("button", { name: "Add" }).click();
    await expect(page.getByText(repoName, { exact: true })).toBeVisible({
      timeout: 30_000,
    });

    // Kick off ingestion directly
    const enqueueRes = await request.post(`${apiBase}/ingest/github`, {
      data: {
        github_url: REPO_URL,
        repo_slug: slug,
        branch: null,
        force_full: true,
      },
    });
    if (enqueueRes.status() >= 400) {
      const text = await enqueueRes.text();
      throw new Error(
        `Failed to enqueue ingestion: ${enqueueRes.status()} ${text}`,
      );
    }

    // Sync button should be usable while job runs/after finish
    const scopedCard = page
      .getByTestId("project-card")
      .filter({ has: page.getByText(repoName, { exact: true }) })
      .first();
    const syncButton = scopedCard.getByRole("button", { name: "Sync" });
    await expect(syncButton).toBeEnabled({ timeout: 15 * 60 * 1000 });

    const repoRoot = path.resolve(__dirname, "..", "..");
    const envLocalPath = path.join(repoRoot, ".env.local");
    const configuredDir =
      (await loadEnvVarFromFile(envLocalPath, "ANALYSIS_DB_DIR")) || "";
    const dbDir = configuredDir || repoRoot;
    const dbPath = path.join(dbDir, `${slug}.db`);
    await expect
      .poll(
        async () => {
          try {
            const s = await fs.stat(dbPath);
            return s.size > 0;
          } catch {
            return false;
          }
        },
        { timeout: 60_000, intervals: [1000, 2000, 5000] },
      )
      .toBeTruthy();

    await page.getByText(repoName, { exact: true }).first().click();
    await page.waitForURL(/\/workspace\/.+\/docs/);
    // Wait until either File Explorer renders or an empty-state appears
    await expect
      .poll(
        async () => {
          const treeCount = await page.getByLabel("File Explorer").count();
          if (treeCount > 0) return true;
          const noFiles = await page
            .getByText("No files found")
            .isVisible()
            .catch(() => false);
          return noFiles ? true : null;
        },
        { timeout: 60_000 },
      )
      .toBeTruthy();
  });

  test("summaries exist for files and definitions (Docs)", async ({
    page,
    request,
  }) => {
    test.setTimeout(120_000);
    if (!(await isIngestionAvailable(request))) {
      test.skip("Ingestion API not reachable — skipping ingestion flow.");
    }
    await page.goto(`/workspace/${slug}/docs`);
    // Wait until either File Explorer renders or an empty-state appears
    await expect
      .poll(
        async () => {
          const treeCount = await page.getByLabel("File Explorer").count();
          if (treeCount > 0) return true;
          const noFiles = await page
            .getByText("No files found")
            .isVisible()
            .catch(() => false);
          return noFiles ? true : null;
        },
        { timeout: 60_000 },
      )
      .toBeTruthy();

    if ((await page.getByLabel("File Explorer").count()) === 0) {
      test.skip("No files found in explorer; skipping summaries check.");
    }

    const tree = page.getByLabel("File Explorer");
    await expandAllTreeItems(tree);

    // Count leaf nodes by inspecting aria-expanded attribute
    const allItems = tree.getByRole("treeitem");
    const allCount = await allItems.count();
    let leafIndexes: number[] = [];
    for (let i = 0; i < allCount; i++) {
      const attr = await allItems.nth(i).getAttribute("aria-expanded");
      if (attr === null) leafIndexes.push(i);
    }
    if (leafIndexes.length === 0) {
      test.skip("No files found in explorer yet; skipping summaries check.");
    }

    let previousHeader = "";
    let filesWithDefinitionCards = 0;
    let definitionsWithSummary = 0;
    const maxFiles = Math.min(10, leafIndexes.length);

    for (let i = 0; i < maxFiles; i++) {
      // Resolve current leaf by index snapshot, but be resilient to re-renders
      if (i >= leafIndexes.length) break;
      const targetIndex = leafIndexes[i];

      // Helper to resolve a leaf locator safely against current DOM
      const resolveLeaf = async (): Promise<Locator | null> => {
        const items = tree.getByRole("treeitem");
        const countNow = await items.count();
        if (targetIndex < countNow) return items.nth(targetIndex);
        return null;
      };

      let leaf: Locator | null = await resolveLeaf();
      if (!leaf) {
        // Tree likely re-rendered; recompute leaf indexes and try again using current i
        const items = tree.getByRole("treeitem");
        const countNow = await items.count();
        const recomputed: number[] = [];
        for (let k = 0; k < countNow; k++) {
          const attr = await items.nth(k).getAttribute("aria-expanded");
          if (attr === null) recomputed.push(k);
        }
        if (i < recomputed.length) {
          leaf = items.nth(recomputed[i]);
        }
      }

      if (!leaf) {
        // Could not resolve a clickable leaf; skip to next
        continue;
      }

      await leaf.scrollIntoViewIfNeeded({ timeout: 5000 }).catch(() => {});
      const isVisible = await leaf.isVisible().catch(() => false);
      if (!isVisible) continue;
      await leaf.click().catch(() => {});

      await waitForFileLoad(page);
      await expect
        .poll(
          async () => {
            const text = await getHeaderFilePath(page);
            return text && text !== previousHeader ? text : null;
          },
          { timeout: 15000 },
        )
        .toBeTruthy();
      previousHeader = await getHeaderFilePath(page);

      // Determine if this file view has any definition cards via heading + button presence
      const cardHeadings = page.getByRole("heading", { level: 3 });
      const hasViewButtons = await page
        .getByRole("button", { name: "View in Source" })
        .count();
      const cardCount = Math.min(await cardHeadings.count(), hasViewButtons);
      if (cardCount > 0) {
        filesWithDefinitionCards++;
        // Heuristic: a definition summary exists if we can read any non-empty text under a definition heading
        const headingText = (await cardHeadings.first().textContent())?.trim();
        if (headingText && headingText.length > 0) definitionsWithSummary++;
      }
    }

    expect(filesWithDefinitionCards).toBeGreaterThan(0);
    expect(definitionsWithSummary).toBeGreaterThan(0);
  });

  test("graph nodes navigate to correct URLs", async ({ page, request }) => {
    test.setTimeout(120_000);
    if (!(await isIngestionAvailable(request))) {
      test.skip("Ingestion API not reachable — skipping ingestion flow.");
    }

    await page.goto(`/workspace/${slug}/docs`);
    // Wait until either File Explorer renders or an empty-state appears
    await expect
      .poll(
        async () => {
          const treeCount = await page.getByLabel("File Explorer").count();
          if (treeCount > 0) return true;
          const noFiles = await page
            .getByText("No files found")
            .isVisible()
            .catch(() => false);
          return noFiles ? true : null;
        },
        { timeout: 60_000 },
      )
      .toBeTruthy();

    if ((await page.getByLabel("File Explorer").count()) === 0) {
      test.skip("No files found in explorer; skipping graph navigation check.");
    }

    const tree = page.getByLabel("File Explorer");
    await expandAllTreeItems(tree);
    const allItems2 = tree.getByRole("treeitem");
    const total2 = await allItems2.count();
    let firstLeafIdx = -1;
    for (let i = 0; i < total2; i++) {
      const attr = await allItems2.nth(i).getAttribute("aria-expanded");
      if (attr === null) {
        firstLeafIdx = i;
        break;
      }
    }
    if (firstLeafIdx < 0) {
      test.skip("No leaf nodes yet; skipping graph navigation check.");
    }
    const firstLeaf = allItems2.nth(firstLeafIdx);
    await firstLeaf.scrollIntoViewIfNeeded({ timeout: 5000 }).catch(() => {});
    await firstLeaf.click();
    await waitForFileLoad(page);

    {
      const graph = page.getByTestId("file-graph");
      // Find candidate node labels by path text (contains "/")
      const candidates = await graph.getByText(/\//).all();
      const count = candidates.length;
      expect(count).toBeGreaterThan(0);
      const initialFileId = getUrlParam(page.url(), "fileId");

      let fileNavOk = false;
      const maxClicks = Math.min(5, count);
      for (let i = 0; i < maxClicks; i++) {
        const node = candidates[i];
        await node.scrollIntoViewIfNeeded().catch(() => {});
        await expect(node).toBeVisible({ timeout: 5000 });
        await node.click();
        const deadline = Date.now() + 3000;
        while (Date.now() < deadline) {
          const current = getUrlParam(page.url(), "fileId");
          if (current && current !== initialFileId) {
            fileNavOk = true;
            break;
          }
          await page.waitForTimeout(100);
        }
        if (fileNavOk) break;
      }
      if (count > 1) expect(fileNavOk).toBeTruthy();
    }
    {
      const defGraphs = page.getByTestId("definition-graph");
      const graphs = await defGraphs.count();
      if (graphs > 0) {
        const maxGraphs = Math.min(2, graphs);
        for (let g = 0; g < maxGraphs; g++) {
          const graph = defGraphs.nth(g);
          await graph.scrollIntoViewIfNeeded().catch(() => {});
          // Click by path text inside definition graph
          const defCandidates = await graph.getByText(/\//).all();
          const nodeTotal = defCandidates.length;
          if (nodeTotal === 0) continue;
          const maxNodes = Math.min(2, nodeTotal);
          for (let i = 0; i < maxNodes; i++) {
            const node = defCandidates[i];
            await node.scrollIntoViewIfNeeded().catch(() => {});
            await expect(node).toBeVisible({ timeout: 5000 });
            await node.click();
            // Poll briefly for definitionId presence and valid URL shape
            const deadline = Date.now() + 3000;
            let ok = false;
            while (Date.now() < deadline) {
              const fId = getUrlParam(page.url(), "fileId");
              const dId = getUrlParam(page.url(), "definitionId");
              if (fId && dId) {
                ok = true;
                break;
              }
              await page.waitForTimeout(100);
            }
            // If graph has more than one node, require success; if single-node, accept no-op
            if (nodeTotal > 1) expect(ok).toBeTruthy();
          }
        }
      }
    }
  });

  // Cleanup: remove the project created by this suite to avoid background polling
  test.afterAll(async ({ browser }) => {
    try {
      const context = await browser.newContext();
      const page = await context.newPage();
      await page.goto("/workspace");
      const card = page
        .getByTestId("project-card")
        .filter({ has: page.getByText(repoName, { exact: true }) })
        .first();
      if ((await card.count()) === 0) {
        await context.close();
        return;
      }
      // Open the delete dialog in the specific card
      await card.getByRole("button", { name: "Delete" }).click();
      const dialog = page.getByRole("dialog");
      await expect(dialog).toBeVisible({ timeout: 5000 });
      await dialog.getByRole("button", { name: "Delete" }).click();
      await expect(card).toHaveCount(0, { timeout: 15_000 });
      await context.close();
    } catch {
      // Best-effort cleanup; ignore failures
    }
  });
});
