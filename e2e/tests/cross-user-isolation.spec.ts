import { randomUUID } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

/**
 * User A creates a private todo; user B, in a separate browser session,
 * must not see it.
 *
 * Each user gets their own browser context, so each has its own
 * localStorage — which is where the app keeps its tokens — and neither can
 * inherit the other's session. Both users register through the UI; no
 * token, cookie or storage value is injected, and no API call is made.
 */

async function registerThroughUI(page: Page, email: string, password: string) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  // exact: the form also has "Confirm Password".
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm Password").fill(password);
  await page.getByRole("button", { name: "Create Account" }).click();

  // The header shows the email returned by /auth/me, so this confirms whose
  // session the page is running under.
  await expect(page).toHaveURL("/");
  await expect(page.getByText(email, { exact: true })).toBeVisible();
}

test("a todo created by one user is not visible to another user's session", async ({
  browser,
  baseURL,
}) => {
  const run = randomUUID().slice(0, 8);
  const userA = {
    email: `e2e-isolation-a-${run}@example.com`,
    password: `pw-${randomUUID()}`,
  };
  const userB = {
    email: `e2e-isolation-b-${run}@example.com`,
    password: `pw-${randomUUID()}`,
  };
  // Unique per run, so B not seeing it cannot be explained by a title that
  // simply was never there under that name.
  const privateTodo = `Private todo ${randomUUID()}`;

  // Contexts made with browser.newContext() do not inherit the config's use
  // options, so the base URL is passed explicitly.
  const userAContext = await browser.newContext({ baseURL });
  const userBContext = await browser.newContext({ baseURL });

  try {
    const pageA = await userAContext.newPage();
    const pageB = await userBContext.newPage();

    // --- User A creates a private todo -----------------------------------
    await registerThroughUI(pageA, userA.email, userA.password);

    await pageA.getByRole("button", { name: "Add Todo" }).click();
    const dialog = pageA.getByRole("dialog", { name: "Create Todo" });
    await dialog.getByLabel("Title").fill(privateTodo);
    await dialog.getByRole("button", { name: "Create" }).click();
    await expect(dialog).toBeHidden();

    // Confirm the todo really exists before looking for its absence
    // elsewhere; otherwise B's check below would pass for the wrong reason.
    await expect(
      pageA.getByRole("checkbox", { name: privateTodo })
    ).toBeVisible();
    await expect(pageA.getByText("Showing 1 of 1 todos")).toBeVisible();

    // --- User B, in a separate session -----------------------------------
    await registerThroughUI(pageB, userB.email, userB.password);

    // The two contexts must not have shared a session: B's header must show
    // B, and must not show A.
    await expect(pageB.getByText(userA.email, { exact: true })).toBeHidden();

    // The list has three states — loading, error and loaded — and A's todo
    // is absent from all three. Only the loaded state makes absence mean
    // anything, so wait for it first. "No todos yet" is rendered only once
    // the fetch has succeeded and returned no items.
    await expect(pageB.getByText("No todos yet")).toBeVisible();
    await expect(pageB.getByText("Loading todos...")).toBeHidden();
    await expect(pageB.getByText(/Failed to load todos/)).toBeHidden();

    // The assertion the scenario exists for.
    await expect(pageB.getByText(privateTodo, { exact: true })).toBeHidden();
    await expect(
      pageB.getByRole("checkbox", { name: privateTodo })
    ).toHaveCount(0);

    // --- A still has the todo --------------------------------------------
    // Reading it back from the server after B's check shows it existed the
    // whole time B could not see it, rather than having gone missing.
    await pageA.reload();
    await expect(
      pageA.getByRole("checkbox", { name: privateTodo })
    ).toBeVisible();
  } finally {
    await userAContext.close();
    await userBContext.close();
  }
});
