import { test, expect } from "@playwright/test";

const REPO_NAME = "Buttons";
const REPO_URL = "https://github.com/aperswal/4buttons.git";

test("Add New repository derives correct slug and accepts URL", async ({ page }) => {
  const unique = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
  const uniqueName = `${REPO_NAME}-${unique}`;

  await page.goto("/workspace");
  await page.getByRole("button", { name: "Add New" }).click();

  // First, verify base slug derivation for canonical name "Buttons" -> "buttons"
  const nameInput = page.getByPlaceholder("e.g. Excalidraw");
  await nameInput.fill(REPO_NAME);
  await page.getByPlaceholder("https://github.com/org/repo").fill(REPO_URL);
  await expect(page.getByText("Slug:")).toBeVisible();
  await expect(page.getByText(/Slug:\s*buttons\b/)).toBeVisible();

  // Now switch to a unique name to avoid duplicates in shared environments
  await nameInput.fill(uniqueName);
  const expectedSlug = uniqueName
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-_]/g, "");
  await expect(page.getByText(new RegExp(`Slug:\\s*${expectedSlug}`))).toBeVisible();

  const addButton = page.getByRole("button", { name: "Add" });
  await expect(addButton).toBeEnabled();
  await addButton.click();

  // Verify the new repo appears by its name
  await expect(page.getByText(uniqueName, { exact: true })).toBeVisible({ timeout: 30_000 });

  // Verify at least one "Repo Link" points to the provided URL (avoid CSS selectors)
  const repoLinks = page.getByRole("link", { name: "Repo Link" });
  await expect(repoLinks.first()).toBeVisible();
  await expect
    .poll(async () => {
      const hrefs = await repoLinks.evaluateAll((els) => els.map((e) => e.getAttribute("href")));
      return hrefs.includes(REPO_URL);
    }, { timeout: 15_000 })
    .toBeTruthy();
});

test("Add New repository blocks duplicate slug", async ({ page }) => {
  const unique = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
  const uniqueName = `${REPO_NAME}-${unique}`;

  await page.goto("/workspace");

  // First add should succeed
  await page.getByRole("button", { name: "Add New" }).click();
  await page.getByPlaceholder("e.g. Excalidraw").fill(uniqueName);
  await page.getByPlaceholder("https://github.com/org/repo").fill(REPO_URL);
  await page.getByRole("button", { name: "Add" }).click();
  await expect(page.getByText(uniqueName, { exact: true })).toBeVisible({ timeout: 30_000 });

  // Second add with same name should be blocked client-side (duplicate slug)
  await page.getByRole("button", { name: "Add New" }).click();
  await page.getByPlaceholder("e.g. Excalidraw").fill(uniqueName);
  await page.getByPlaceholder("https://github.com/org/repo").fill(REPO_URL);
  await page.getByRole("button", { name: "Add" }).click();

  await expect(
    page.getByText(
      "A repository with this name already exists. Try a different name.",
    ),
  ).toBeVisible();
});
