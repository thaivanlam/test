import { expect, test } from "@playwright/test";

/**
 * Confirms the suite can reach a running frontend and that the app has
 * rendered, so that a failure in the real scenarios points at the scenario
 * rather than at the setup.
 */
test("login page loads and renders its form", async ({ page }) => {
  await page.goto("/login");

  // The app is a client-rendered SPA, so a 200 alone proves nothing. These are
  // the first elements React actually puts on the page.
  await expect(
    page.getByRole("heading", { name: "Welcome Back" })
  ).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Email" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Password" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign In" })).toBeVisible();
});
