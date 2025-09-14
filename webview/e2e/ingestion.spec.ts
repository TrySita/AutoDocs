import { test, expect, Page, Locator } from "@playwright/test";
import { encodeTRPCResponse, type PublicProject } from "./test-utils";
import fs from "node:fs/promises";
import path from "node:path";

const REPO_URL = "https://github.com/aperswal/4buttons.git";
const apiBase = process.env.INGESTION_API_URL || "http://0.0.0.0:8000";

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
    const collapsed = tree.locator('[role="treeitem"][aria-expanded="false"]');
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
        const graphNodeCount = await page
          .locator("#file-graph .react-flow__node")
          .count()
          .catch(() => 0);
        return graphNodeCount > 0 ? true : null;
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
    let created = false;
    let createdProject: PublicProject | null = null;
    let sawPublicFetchAfterCreate = false;

    await page.route(
      "**/api/trpc/projects.getPublicProjects**",
      async (route) => {
        const reqBody = route.request().postData() || "[]";
        const idMatch = /"id"\s*:\s*(\d+)/.exec(reqBody);
        const id = idMatch ? Number.parseInt(idMatch[1], 10) : 0;

        const payload: PublicProject[] =
          created && createdProject ? [createdProject] : [];
        if (created) sawPublicFetchAfterCreate = true;
        await route.fulfill({
          contentType: "application/json",
          body: encodeTRPCResponse(id, payload),
        });
      },
    );

    await page.route(
      "**/api/trpc/projects.addPublicProject**",
      async (route) => {
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
        const bodyText = await enqueueRes.text();
        const jobMatch = /"job_id"\s*:\s*"([^"]+)"/.exec(bodyText);
        if (!jobMatch) {
          throw new Error("Unexpected enqueue response shape");
        }
        const jobIdValue = jobMatch[1];
        created = true;
        createdProject = {
          id: "00000000-0000-0000-0000-000000000001",
          name: repoName,
          slug,
          repositoryUrl: REPO_URL,
          isActive: true,
          sortOrder: 0,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          dbUrl: null,
          dbKey: null,
          latestJobId: jobIdValue,
          latestJobStatus: "queued",
          description: null,
          logoUrl: null,
        };

        const reqBody = route.request().postData() || "[]";
        const idMatch = /"id"\s*:\s*(\d+)/.exec(reqBody);
        const id = idMatch ? Number.parseInt(idMatch[1], 10) : 0;

        await route.fulfill({
          contentType: "application/json",
          body: encodeTRPCResponse(id, createdProject),
        });
      },
    );

    await page.goto("/workspace");
    await page.getByRole("button", { name: "Add New" }).click();
    await page.getByPlaceholder("e.g. Excalidraw").fill(repoName);
    await page.getByPlaceholder("https://github.com/org/repo").fill(REPO_URL);
    await page.getByRole("button", { name: "Add" }).click();
    await expect
      .poll(() => sawPublicFetchAfterCreate, { timeout: 15000 })
      .toBeTruthy();

    const scoped = page
      .locator(".grid")
      .filter({ has: page.getByText(repoName, { exact: true }) });
    await expect(
      scoped.getByRole("button", { name: "Sync" }).first(),
    ).toBeEnabled({ timeout: 15 * 60 * 1000 });

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
    await expect(page.getByLabel("File Explorer")).toBeVisible();
  });

  test("summaries exist for files and definitions (Docs)", async ({ page }) => {
    test.setTimeout(120_000);
    await page.goto(`/workspace/${slug}/docs`);
    await expect(page.getByLabel("File Explorer")).toBeVisible();

    const tree = page.getByLabel("File Explorer");
    await expandAllTreeItems(tree);

    const leaves = tree.locator('[role="treeitem"]:not([aria-expanded])');
    const leafCount = await leaves.count();
    expect(leafCount).toBeGreaterThan(0);

    let previousHeader = "";
    let filesWithDefinitionCards = 0;
    let definitionsWithSummary = 0;
    const maxFiles = Math.min(10, leafCount);

    for (let i = 0; i < maxFiles; i++) {
      const currentLeaves = tree.locator(
        '[role="treeitem"]:not([aria-expanded])',
      );
      const currentCount = await currentLeaves.count();
      if (i >= currentCount) break;

      const leaf = currentLeaves.nth(i);
      await leaf.scrollIntoViewIfNeeded();
      await leaf.click();

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

      const defCards = page
        .locator("div[id]")
        .filter({ has: page.getByRole("heading", { level: 3 }) })
        .filter({ has: page.getByRole("button", { name: "View in Source" }) });
      const cardCount = await defCards.count();
      if (cardCount > 0) {
        filesWithDefinitionCards++;
        for (let j = 0; j < Math.min(3, cardCount); j++) {
          const card = defCards.nth(j);
          const md = card.locator("div.markdown");
          if (await md.count()) {
            definitionsWithSummary++;
            break;
          }
        }
      }
    }

    expect(filesWithDefinitionCards).toBeGreaterThan(0);
    expect(definitionsWithSummary).toBeGreaterThan(0);
  });

  test("graph nodes navigate to correct URLs", async ({ page }) => {
    test.setTimeout(120_000);

    await page.goto(`/workspace/${slug}/docs`);
    await expect(page.getByLabel("File Explorer")).toBeVisible();

    const tree = page.getByLabel("File Explorer");
    await expandAllTreeItems(tree);
    const leaves = tree.locator('[role="treeitem"]:not([aria-expanded])');
    const leafCount = await leaves.count();
    expect(leafCount).toBeGreaterThan(0);
    const firstLeaf = tree
      .locator('[role="treeitem"]:not([aria-expanded])')
      .first();
    await firstLeaf.scrollIntoViewIfNeeded();
    await firstLeaf.click();
    await waitForFileLoad(page);

    {
      let nodes = page.locator("#file-graph .react-flow__node");
      const count = await nodes.count();
      expect(count).toBeGreaterThan(0);
      const initialFileId = getUrlParam(page.url(), "fileId");

      let fileNavOk = false;
      const maxClicks = Math.min(5, count);
      for (let i = 0; i < maxClicks; i++) {
        nodes = page.locator("#file-graph .react-flow__node");
        const node = nodes.nth(i);
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
      const defGraphs = page
        .locator(".react-flow")
        .filter({ hasNot: page.locator("#file-graph") });
      const graphs = await defGraphs.count();
      if (graphs > 0) {
        const maxGraphs = Math.min(2, graphs);
        for (let g = 0; g < maxGraphs; g++) {
          const graph = defGraphs.nth(g);
          await graph.scrollIntoViewIfNeeded().catch(() => {});
          let defNodes = graph.locator(".react-flow__node");
          const nodeTotal = await defNodes.count();
          if (nodeTotal === 0) continue;
          const maxNodes = Math.min(2, nodeTotal);
          for (let i = 0; i < maxNodes; i++) {
            defNodes = graph.locator(".react-flow__node");
            const node = defNodes.nth(i);
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
});
