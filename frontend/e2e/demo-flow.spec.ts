import { expect, test } from "@playwright/test";

test("demo workflow: profile → date → rankings", async ({ page }) => {
  await page.goto("/demo");
  await expect(page.getByRole("heading", { name: /Saved demonstration run/i })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText(/SYNTHETIC DEMO/i).first()).toBeVisible();

  await page.getByRole("link", { name: /Browse a profile/i }).click();
  await expect(page.getByText(/Profile analysis/i)).toBeVisible();
  await expect(page.getByText(/Synthetic/i).first()).toBeVisible();

  await page.goto("/demo");
  await page.getByRole("link", { name: /Watch example date/i }).click();
  await expect(page.getByText(/Dating room/i)).toBeVisible();
  await expect(page.getByText(/Demo replay|Saved demo replay/i).first()).toBeVisible();

  await page.goto("/demo");
  await page.getByRole("link", { name: /Inspect rankings/i }).click();
  await expect(page.getByText(/Rankings/i).first()).toBeVisible();
  await expect(page.getByText(/Rank 1/i).first()).toBeVisible();

  // Switch participant via rankings directory
  await page.goto("/rankings");
  await expect(page.getByRole("heading", { name: /Personalized rankings/i })).toBeVisible();
  const links = page.locator('a[href^="/rankings/"]');
  await expect(links.first()).toBeVisible({ timeout: 30_000 });
  const count = await links.count();
  expect(count).toBeGreaterThan(1);
  await links.nth(1).click();
  await expect(page.getByText(/Rank 1/i).first()).toBeVisible({ timeout: 30_000 });
});
