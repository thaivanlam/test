import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";

/**
 * Register → create a todo → complete it → verify → log out, entirely through
 * the browser. Nothing is set up or checked through the API.
 *
 * Every run registers its own account, so the test depends on no existing
 * user and can be repeated against the same database.
 */
test("a new user can register, create and complete a todo, then log out", async ({
  page,
}) => {
  const suffix = randomUUID().slice(0, 8);
  const email = `e2e-journey-${suffix}@example.com`;
  // Generated per run and never logged; it only has to satisfy the form's
  // six-character minimum.
  const password = `pw-${randomUUID()}`;
  const todoTitle = `E2E journey todo ${suffix}`;

  // --- Register -----------------------------------------------------------
  await page.goto("/register");
  await expect(
    page.getByRole("heading", { name: "Create Account" })
  ).toBeVisible();

  await page.getByLabel("Email").fill(email);
  // exact: the form also has "Confirm Password", which a substring match
  // would pick up as well.
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm Password").fill(password);
  await page.getByRole("button", { name: "Create Account" }).click();

  // Registration signs the user in and redirects to the dashboard. The header
  // shows the email from /auth/me, which proves the session belongs to this
  // account rather than merely that some page loaded.
  await expect(page).toHaveURL("/");
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  await expect(page.getByText("No todos yet")).toBeVisible();

  // --- Create a todo ------------------------------------------------------
  await page.getByRole("button", { name: "Add Todo" }).click();

  const dialog = page.getByRole("dialog", { name: "Create Todo" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("Title").fill(todoTitle);
  await dialog.getByRole("button", { name: "Create" }).click();
  await expect(dialog).toBeHidden();

  // The checkbox takes its accessible name from the <label for> that holds
  // the title, so it can be found by the title alone. exact: the row's
  // selection checkbox is named 'Select "<title>"', which a substring match
  // would also pick up.
  const checkbox = page.getByRole("checkbox", { name: todoTitle, exact: true });
  const titleLabel = page.getByText(todoTitle, { exact: true });

  await expect(checkbox).toBeVisible();
  await expect(page.getByText("Showing 1 of 1 todos")).toBeVisible();

  // Record the starting state, so the toggle below is shown to change it.
  await expect(checkbox).not.toBeChecked();
  await expect(titleLabel).toHaveCSS("text-decoration-line", "none");

  // --- Complete it --------------------------------------------------------
  await checkbox.click();

  // The checkbox is a Radix primitive rendered as role="checkbox" with
  // aria-checked, which is what toBeChecked reads.
  await expect(checkbox).toBeChecked();
  // TodoItem strikes the title through when completed. Asserting the computed
  // style checks what the user sees, not the class name that produces it.
  await expect(titleLabel).toHaveCSS("text-decoration-line", "line-through");

  // The toggle is applied optimistically, so a checked box alone could be the
  // client's own guess. Reloading discards the client state and reads the
  // todo back from the server.
  await page.reload();
  await expect(checkbox).toBeChecked();
  await expect(titleLabel).toHaveCSS("text-decoration-line", "line-through");

  // --- Log out ------------------------------------------------------------
  await page.getByRole("button", { name: "Logout" }).click();

  await expect(page).toHaveURL("/login");
  await expect(page.getByRole("heading", { name: "Welcome Back" })).toBeVisible();

  // Landing on /login does not by itself prove the session ended. Asking for
  // the protected dashboard does: without a session it redirects back.
  await page.goto("/");
  await expect(page).toHaveURL("/login");
  await expect(page.getByText(email, { exact: true })).toBeHidden();
});
