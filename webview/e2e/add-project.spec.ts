import { test, expect } from "@playwright/test";
import { encodeTRPCResponse, type PublicProject } from "./test-utils";

const REPO_NAME = "Buttons";
const REPO_URL = "https://github.com/aperswal/4buttons.git";

test("Add New repository derives correct slug and accepts URL", async ({ page }) => {
  let created = false;

  const createdProject: PublicProject = {
    id: "00000000-0000-0000-0000-000000000001",
    name: REPO_NAME,
    slug: REPO_NAME,
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
  };

  let seenCreatedFetch = false;
  await page.route(
    "**/api/trpc/projects.getPublicProjects**",
    async (route) => {
      const reqBody = route.request().postData() || "[]";
      const idMatch = /"id"\s*:\s*(\d+)/.exec(reqBody);
      const id = idMatch ? Number.parseInt(idMatch[1], 10) : 0;
      const payload: PublicProject[] = created ? [createdProject] : [];
      if (created) seenCreatedFetch = true;
      await route.fulfill({
        contentType: "application/json",
        body: encodeTRPCResponse(id, payload),
      });
    },
  );

  await page.route("**/api/trpc/projects.addPublicProject**", async (route) => {
    created = true;
    const reqBody = route.request().postData() || "[]";
    const idMatch = /"id"\s*:\s*(\d+)/.exec(reqBody);
    const id = idMatch ? Number.parseInt(idMatch[1], 10) : 0;
    await route.fulfill({
      contentType: "application/json",
      body: encodeTRPCResponse(id, createdProject),
    });
  });

  await page.goto("/workspace");
  await page.getByRole("button", { name: "Add New" }).click();
  await page.getByPlaceholder("e.g. Excalidraw").fill(REPO_NAME);
  await page.getByPlaceholder("https://github.com/org/repo").fill(REPO_URL);
  await expect(page.getByText("Slug:")).toBeVisible();
  await expect(page.getByText(/Slug:\s*buttons/)).toBeVisible();
  const addButton = page.getByRole("button", { name: "Add" });
  await expect(addButton).toBeEnabled();
  await addButton.click();
  await expect.poll(() => seenCreatedFetch, { timeout: 15000 }).toBeTruthy();
  await expect(page.getByText(REPO_NAME, { exact: true })).toBeVisible();
  const repoLink = page.getByRole("link", { name: "Repo Link" });
  await expect(repoLink).toBeVisible();
  await expect(repoLink).toHaveAttribute("href", REPO_URL);
});

test("Add New repository blocks duplicate slug", async ({ page }) => {
  let created = false;
  let addCalls = 0;

  const createdProject: PublicProject = {
    id: "00000000-0000-0000-0000-000000000001",
    name: REPO_NAME,
    slug: "buttons", // slug must match derived lowercase for duplicate check
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
  };

  let seenCreatedFetch = false;
  await page.route("**/api/trpc/projects.getPublicProjects**", async (route) => {
    const reqBody = route.request().postData() || "[]";
    const idMatch = /"id"\s*:\s*(\d+)/.exec(reqBody);
    const id = idMatch ? Number.parseInt(idMatch[1], 10) : 0;
    const payload: PublicProject[] = created ? [createdProject] : [];
    if (created) seenCreatedFetch = true;
    await route.fulfill({ contentType: "application/json", body: encodeTRPCResponse(id, payload) });
  });

  await page.route("**/api/trpc/projects.addPublicProject**", async (route) => {
    addCalls += 1;
    created = true;
    const reqBody = route.request().postData() || "[]";
    const idMatch = /"id"\s*:\s*(\d+)/.exec(reqBody);
    const id = idMatch ? Number.parseInt(idMatch[1], 10) : 0;
    await route.fulfill({ contentType: "application/json", body: encodeTRPCResponse(id, createdProject) });
  });

  await page.goto("/workspace");

  await page.getByRole("button", { name: "Add New" }).click();
  await page.getByPlaceholder("e.g. Excalidraw").fill(REPO_NAME);
  await page.getByPlaceholder("https://github.com/org/repo").fill(REPO_URL);
  await page.getByRole("button", { name: "Add" }).click();
  await expect.poll(() => seenCreatedFetch, { timeout: 15000 }).toBeTruthy();
  await expect(page.getByText(REPO_NAME, { exact: true })).toBeVisible();
  expect(addCalls).toBe(1);
  await page.getByRole("button", { name: "Add New" }).click();
  await page.getByPlaceholder("e.g. Excalidraw").fill(REPO_NAME);
  await page.getByPlaceholder("https://github.com/org/repo").fill(REPO_URL);
  await page.getByRole("button", { name: "Add" }).click();

  await expect(
    page.getByText(
      "A repository with this name already exists. Try a different name.",
    ),
  ).toBeVisible();

  expect(addCalls).toBe(1);
});
