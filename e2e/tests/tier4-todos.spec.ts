import { randomUUID } from "node:crypto";
import {
  expect,
  test,
  type APIResponse,
  type Page,
  type Request,
} from "@playwright/test";

/**
 * Tier 4: filtering, pagination, tags, bulk status, and the regressions they
 * could have reintroduced.
 *
 * Every test registers its own user through the UI, so it depends on no
 * existing data and tolerates whatever earlier runs left in the database.
 *
 * Background data (a batch of todos, a tag attached in advance) is created
 * through the API with the page's own token, because building it through the
 * UI would make the tests slow without testing anything. The behaviour each
 * test is about is always driven through the UI.
 */

const API_URL = process.env.API_URL ?? "http://localhost:8000";

interface ApiTodo {
  id: string;
  title: string;
  created_at: string;
}

async function registerThroughUI(page: Page, label: string): Promise<string> {
  const email = `e2e-t4-${label}-${randomUUID().slice(0, 8)}@example.com`;
  // Generated per run and never logged.
  const password = `pw-${randomUUID()}`;
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  // exact: the form also has "Confirm Password".
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm Password").fill(password);
  await page.getByRole("button", { name: "Create Account" }).click();
  await expect(page).toHaveURL("/");
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  return email;
}

/** API calls made as the user currently signed in on `page`. */
async function apiAs(page: Page) {
  const token = await page.evaluate(() => localStorage.getItem("access_token"));
  expect(token).toBeTruthy();
  const headers = { Authorization: `Bearer ${token}` };
  const url = (path: string) => `${API_URL}/api/v1${path}`;
  const ok = async (response: APIResponse, status: number) => {
    expect(response.status(), await response.text()).toBe(status);
    return response;
  };

  return {
    async createTodo(title: string, description?: string): Promise<ApiTodo> {
      const response = await page.request.post(url("/todos"), {
        headers,
        data: { title, description },
      });
      return (await ok(response, 201)).json();
    },
    async setCompleted(todoId: string, completed: boolean) {
      await ok(
        await page.request.put(url(`/todos/${todoId}`), {
          headers,
          data: { completed },
        }),
        200
      );
    },
    async deleteTodo(todoId: string) {
      await ok(await page.request.delete(url(`/todos/${todoId}`), { headers }), 204);
    },
    async createTag(name: string): Promise<{ id: string }> {
      const response = await page.request.post(url("/tags"), {
        headers,
        data: { name },
      });
      return (await ok(response, 201)).json();
    },
    async attachTag(todoId: string, tagId: string) {
      await ok(
        await page.request.post(url(`/todos/${todoId}/tags`), {
          headers,
          data: { tag_id: tagId },
        }),
        204
      );
    },
    get: (path: string) => page.request.get(url(path), { headers }),
    post: (path: string, data: unknown) =>
      page.request.post(url(path), { headers, data }),
  };
}

/** Todo titles in the list, in display order. */
const todoTitles = (page: Page) => page.locator('label[for^="todo-"]');

/** The completion checkbox, named by the title alone (see TodoItem). */
const completionBox = (page: Page, title: string) =>
  page.getByRole("checkbox", { name: title, exact: true });

/** YYYY-MM-DD of an API timestamp, in UTC as the API stores it. */
const utcDay = (timestamp: string) => new Date(timestamp).toISOString().slice(0, 10);

function shiftDay(day: string, days: number): string {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

test.describe("filtering", () => {
  test("keyword, status, tag, dates, combined, and clear", async ({ page }) => {
    await registerThroughUI(page, "filters");
    const api = await apiAs(page);
    // Created in this order, so listed newest first: the reverse.
    const groceries = await api.createTodo("Buy groceries", "milk and eggs");
    const report = await api.createTodo("Quarterly REPORT", "numbers");
    const parcel = await api.createTodo("Errand", "collect the Parcel");
    await api.createTodo("Call mom");
    await api.setCompleted(report.id, true);
    await api.setCompleted(groceries.id, true);
    const tag = await api.createTag("errands");
    await api.attachTag(parcel.id, tag.id);
    await api.attachTag(groceries.id, tag.id);
    await page.reload();

    const everything = ["Call mom", "Errand", "Quarterly REPORT", "Buy groceries"];
    await expect(todoTitles(page)).toHaveText(everything);

    const search = page.getByLabel("Search", { exact: true });
    const status = page.getByLabel("Status", { exact: true });
    const tagSelect = page.getByLabel("Tag", { exact: true });
    const from = page.getByLabel("From", { exact: true });
    const to = page.getByLabel("To", { exact: true });

    // Keyword matches the title...
    await search.fill("groceries");
    await expect(todoTitles(page)).toHaveText(["Buy groceries"]);
    // ...and the description...
    await search.fill("parcel");
    await expect(todoTitles(page)).toHaveText(["Errand"]);
    // ...case-insensitively, with surrounding spaces ignored.
    await search.fill("  report  ");
    await expect(todoTitles(page)).toHaveText(["Quarterly REPORT"]);
    await search.fill("");
    await expect(todoTitles(page)).toHaveText(everything);

    await status.selectOption("active");
    await expect(todoTitles(page)).toHaveText(["Call mom", "Errand"]);
    await status.selectOption("completed");
    await expect(todoTitles(page)).toHaveText(["Quarterly REPORT", "Buy groceries"]);
    await status.selectOption("all");
    await expect(todoTitles(page)).toHaveText(everything);

    await tagSelect.selectOption({ label: "errands" });
    await expect(todoTitles(page)).toHaveText(["Errand", "Buy groceries"]);
    await tagSelect.selectOption({ label: "All tags" });
    await expect(todoTitles(page)).toHaveText(everything);

    // Dates are whole UTC days, inclusive at both ends. The day is taken from
    // the API's own timestamp rather than this machine's clock.
    const today = utcDay(parcel.created_at);
    await from.fill(shiftDay(today, 1));
    await expect(page.getByText("No todos match your filters")).toBeVisible();
    await from.fill(today);
    await expect(todoTitles(page)).toHaveText(everything);
    await from.fill("");
    await to.fill(shiftDay(today, -1));
    await expect(page.getByText("No todos match your filters")).toBeVisible();
    await to.fill(today);
    await expect(todoTitles(page)).toHaveText(everything);

    // Every filter at once: only one todo satisfies all of them.
    await from.fill(today);
    await tagSelect.selectOption({ label: "errands" });
    await status.selectOption("completed");
    await search.fill("MILK");
    await expect(todoTitles(page)).toHaveText(["Buy groceries"]);
    await expect(page.getByText("Showing 1 of 1 todos")).toBeVisible();

    await page.getByRole("button", { name: "Clear filters" }).click();
    await expect(todoTitles(page)).toHaveText(everything);
    await expect(search).toHaveValue("");
    await expect(status).toHaveValue("all");
    await expect(tagSelect).toHaveValue("");
    await expect(from).toHaveValue("");
    await expect(to).toHaveValue("");
    await expect(page.getByRole("button", { name: "Clear filters" })).toBeDisabled();
  });
});

test.describe("pagination", () => {
  test("pages through todos with page and page_size, never size=10000", async ({
    page,
  }) => {
    const listRequests: Request[] = [];
    page.on("request", (request) => {
      if (new URL(request.url()).pathname === "/api/v1/todos" && request.method() === "GET") {
        listRequests.push(request);
      }
    });

    await registerThroughUI(page, "pages");
    const api = await apiAs(page);
    for (let index = 1; index <= 23; index++) {
      // Zero-padded, so the titles also sort in creation order.
      await api.createTodo(`Paged ${String(index).padStart(2, "0")}`);
    }
    await page.reload();

    await expect(page.getByText("Page 1 of 2")).toBeVisible();
    await expect(page.getByText("Showing 20 of 23 todos")).toBeVisible();
    await expect(todoTitles(page).first()).toHaveText("Paged 23");

    await page.getByRole("button", { name: "Next" }).click();
    await expect(page.getByText("Page 2 of 2")).toBeVisible();
    await expect(todoTitles(page)).toHaveText(["Paged 03", "Paged 02", "Paged 01"]);
    await expect(page.getByRole("button", { name: "Next" })).toBeDisabled();

    await page.getByRole("button", { name: "Previous" }).click();
    await expect(page.getByText("Page 1 of 2")).toBeVisible();
    await expect(todoTitles(page).first()).toHaveText("Paged 23");

    await page.getByLabel("Per page").selectOption("10");
    await expect(page.getByText("Page 1 of 3")).toBeVisible();
    await expect(todoTitles(page)).toHaveCount(10);
    await page.getByRole("button", { name: "Next" }).click();
    await expect(page.getByText("Page 2 of 3")).toBeVisible();
    await expect(todoTitles(page).first()).toHaveText("Paged 13");

    // A filter change from page 2 starts again at page 1.
    await page.getByLabel("Search", { exact: true }).fill("paged 1");
    await expect(page.getByText("Page 1 of 1")).toBeVisible();
    await expect(todoTitles(page)).toHaveText([
      "Paged 19", "Paged 18", "Paged 17", "Paged 16", "Paged 15",
      "Paged 14", "Paged 13", "Paged 12", "Paged 11", "Paged 10",
    ]);

    // The contract as sent: page and page_size, within the API's limit, and
    // no longer the old size=10000.
    expect(listRequests.length).toBeGreaterThan(0);
    for (const request of listRequests) {
      const params = new URL(request.url()).searchParams;
      expect(params.has("size"), request.url()).toBe(false);
      expect(Number(params.get("page_size")), request.url()).toBeLessThanOrEqual(100);
      expect(Number(params.get("page")), request.url()).toBeGreaterThanOrEqual(1);
    }
  });
});

test.describe("tags", () => {
  test("create, rename, attach, detach and delete a tag", async ({ page }) => {
    await registerThroughUI(page, "tags");
    await (await apiAs(page)).createTodo("Tagged todo");
    await page.reload();
    await expect(completionBox(page, "Tagged todo")).toBeVisible();

    // Create.
    await page.getByRole("button", { name: "Manage Tags" }).click();
    const manager = page.getByRole("dialog", { name: "Manage Tags" });
    await manager.getByLabel("Tag name").fill("Work");
    await manager.getByLabel("Color (optional)").fill("#ff0000");
    await manager.getByRole("button", { name: "Add tag" }).click();
    await expect(manager.getByRole("button", { name: "Rename tag Work" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(manager).toBeHidden();

    // Attach.
    await page
      .getByRole("combobox", { name: 'Add tag to "Tagged todo"' })
      .selectOption({ label: "Work" });
    const removeWork = page.getByRole("button", {
      name: 'Remove tag Work from "Tagged todo"',
    });
    await expect(removeWork).toBeVisible();

    // Rename and recolor: the todo shows the new name without a reload.
    await page.getByRole("button", { name: "Manage Tags" }).click();
    await manager.getByRole("button", { name: "Rename tag Work" }).click();
    // The rename form sits beside the "new tag" form, so both have a
    // "Tag name" field; the rename form's ids start with edit-tag-.
    await manager.locator("input[id^='edit-tag-'][id$='-name']").fill("Office");
    await manager.locator("input[id^='edit-tag-'][id$='-color']").fill("blue");
    await manager.getByRole("button", { name: "Save" }).click();
    await expect(manager.getByRole("button", { name: "Rename tag Office" })).toBeVisible();
    await page.keyboard.press("Escape");
    const removeOffice = page.getByRole("button", {
      name: 'Remove tag Office from "Tagged todo"',
    });
    await expect(removeOffice).toBeVisible();
    await expect(removeWork).toHaveCount(0);

    // Detach: the badge goes, the tag stays.
    await removeOffice.click();
    await expect(removeOffice).toHaveCount(0);
    await expect(
      page.getByRole("combobox", { name: 'Add tag to "Tagged todo"' })
    ).toBeVisible();

    // Delete: gone from the manager and from the filter's options.
    await page.getByRole("button", { name: "Manage Tags" }).click();
    await manager.getByRole("button", { name: "Delete tag Office" }).click();
    await expect(manager.getByText("No tags yet.")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(
      page.getByLabel("Tag", { exact: true }).locator("option", { hasText: "Office" })
    ).toHaveCount(0);
  });

  test("duplicate names and invalid names are rejected", async ({ page }) => {
    await registerThroughUI(page, "tag-invalid");
    await page.getByRole("button", { name: "Manage Tags" }).click();
    const manager = page.getByRole("dialog", { name: "Manage Tags" });
    const name = manager.getByLabel("Tag name");
    const add = manager.getByRole("button", { name: "Add tag" });

    await name.fill("Work");
    await add.click();
    await expect(manager.getByRole("button", { name: "Rename tag Work" })).toBeVisible();

    // Same name in another case: rejected by the API (409), shown on the field.
    await name.fill("work");
    await add.click();
    await expect(manager.getByText("Tag with this name already exists")).toBeVisible();

    await name.fill("   ");
    await add.click();
    await expect(manager.getByText("Name is required")).toBeVisible();

    await name.fill("x".repeat(51));
    await add.click();
    await expect(manager.getByText("Name must be at most 50 characters")).toBeVisible();

    // Nothing but the first tag was created.
    await expect(manager.getByRole("button", { name: /^Rename tag / })).toHaveCount(1);
  });
});

test.describe("bulk status", () => {
  test("mark several completed, then active again, clearing the selection", async ({
    page,
  }) => {
    await registerThroughUI(page, "bulk");
    const api = await apiAs(page);
    for (const title of ["Bulk one", "Bulk two", "Bulk three"]) {
      await api.createTodo(title);
    }
    await page.reload();

    const markCompleted = page.getByRole("button", { name: "Mark completed" });
    const markActive = page.getByRole("button", { name: "Mark active" });
    await expect(markCompleted).toBeDisabled();
    await expect(markActive).toBeDisabled();

    await page.getByRole("checkbox", { name: 'Select "Bulk one"' }).click();
    await page.getByRole("checkbox", { name: 'Select "Bulk two"' }).click();
    await expect(page.getByText("2 selected")).toBeVisible();
    await markCompleted.click();

    await expect(page.getByText("0 selected")).toBeVisible();
    await expect(completionBox(page, "Bulk one")).toBeChecked();
    await expect(completionBox(page, "Bulk two")).toBeChecked();
    await expect(completionBox(page, "Bulk three")).not.toBeChecked();

    await page.getByRole("checkbox", { name: 'Select "Bulk one"' }).click();
    await page.getByRole("checkbox", { name: 'Select "Bulk two"' }).click();
    await markActive.click();
    await expect(page.getByText("0 selected")).toBeVisible();

    // Read back from the server, not from the client's state.
    await page.reload();
    for (const title of ["Bulk one", "Bulk two", "Bulk three"]) {
      await expect(completionBox(page, title)).not.toBeChecked();
    }
  });

  test("a failed bulk update changes nothing and keeps the selection", async ({
    page,
  }) => {
    await registerThroughUI(page, "bulk-fail");
    const api = await apiAs(page);
    const kept = await api.createTodo("Still here");
    const doomed = await api.createTodo("Deleted elsewhere");
    await page.reload();

    await page.getByRole("checkbox", { name: 'Select "Still here"' }).click();
    await page.getByRole("checkbox", { name: 'Select "Deleted elsewhere"' }).click();
    await expect(page.getByText("2 selected")).toBeVisible();

    // The todo disappears behind the UI's back, as if deleted in another tab.
    // The request then names one id that no longer exists.
    await api.deleteTodo(doomed.id);
    await page.getByRole("button", { name: "Mark completed" }).click();

    await expect(page.getByText(/Some selected todos no longer exist/)).toBeVisible();
    await expect(page.getByText("2 selected")).toBeVisible();

    // All or nothing: the todo that does exist was not completed either.
    const response = await api.get(`/todos/${kept.id}`);
    expect(response.status()).toBe(200);
    expect((await response.json()).completed).toBe(false);
  });
});

test.describe("regressions", () => {
  test("SEC-05: a todo can be completed and then made active again", async ({
    page,
  }) => {
    await registerThroughUI(page, "sec05");
    await (await apiAs(page)).createTodo("Round trip");
    await page.reload();

    const box = completionBox(page, "Round trip");
    await expect(box).not.toBeChecked();
    await box.click();
    await expect(box).toBeChecked();
    await page.reload();
    await expect(box).toBeChecked();

    // The step SEC-05 broke: false was ignored and the todo stayed completed.
    await box.click();
    await expect(box).not.toBeChecked();
    await page.reload();
    await expect(box).not.toBeChecked();
  });

  test("SEC-16: a failed toggle is rolled back, not left as the optimistic guess", async ({
    page,
  }) => {
    await registerThroughUI(page, "sec16");
    await (await apiAs(page)).createTodo("Will fail");
    await page.reload();
    const box = completionBox(page, "Will fail");
    await expect(box).not.toBeChecked();

    // The update fails. The list refetch that follows is held back, so the
    // box can only return to unchecked through the rollback — not through
    // fresh data from the server, which would hide a missing rollback.
    await page.route(/\/api\/v1\/todos\/[^/?]+$/, (route) =>
      route.request().method() === "PUT"
        ? route.fulfill({ status: 500, json: { detail: "forced failure" } })
        : route.fallback()
    );
    let releaseList: () => void = () => {};
    const listHeld = new Promise<void>((resolve) => (releaseList = resolve));
    await page.route(/\/api\/v1\/todos\?/, async (route) => {
      await listHeld;
      await route.fallback();
    });

    await box.click();
    await expect(page.getByText("Failed to update todo")).toBeVisible();
    await expect(box).not.toBeChecked();

    releaseList();
    await page.unrouteAll({ behavior: "wait" });
  });
});

test.describe("isolation", () => {
  test("a user cannot see, filter by, or attach another user's tag", async ({
    browser,
    baseURL,
  }) => {
    const contextA = await browser.newContext({ baseURL });
    const contextB = await browser.newContext({ baseURL });
    try {
      const pageA = await contextA.newPage();
      const pageB = await contextB.newPage();
      const secretName = `secret-${randomUUID().slice(0, 8)}`;

      await registerThroughUI(pageA, "iso-a");
      const apiA = await apiAs(pageA);
      const aTodo = await apiA.createTodo("A's tagged todo");
      const aTag = await apiA.createTag(secretName);
      await apiA.attachTag(aTodo.id, aTag.id);

      await registerThroughUI(pageB, "iso-b");
      const apiB = await apiAs(pageB);
      const bTodo = await apiB.createTodo("B's todo");
      // B has a tag of their own, so both tag pickers are rendered and
      // populated; the absence of A's tag below is then meaningful.
      await apiB.createTag("b-own-tag");
      await pageB.reload();
      await expect(completionBox(pageB, "B's todo")).toBeVisible();

      // Not offered in B's UI, neither as a filter nor for attaching.
      const filterSelect = pageB.getByLabel("Tag", { exact: true });
      const attachSelect = pageB.getByRole("combobox", {
        name: `Add tag to "B's todo"`,
      });
      await expect(filterSelect.locator("option", { hasText: "b-own-tag" })).toHaveCount(1);
      await expect(attachSelect.locator("option", { hasText: "b-own-tag" })).toHaveCount(1);
      await expect(filterSelect.locator("option", { hasText: secretName })).toHaveCount(0);
      await expect(attachSelect.locator("option", { hasText: secretName })).toHaveCount(0);

      // And refused by the API when B asks anyway: the same 404 as for a tag
      // that does not exist, with none of A's todos in the answer.
      const filtered = await apiB.get(`/todos?tag_id=${aTag.id}`);
      expect(filtered.status()).toBe(404);
      expect(await filtered.json()).toEqual({ detail: "Tag not found" });
      const attached = await apiB.post(`/todos/${bTodo.id}/tags`, { tag_id: aTag.id });
      expect(attached.status()).toBe(404);

      // A still has the tag on the todo, untouched.
      const aList = await (await apiA.get(`/todos?tag_id=${aTag.id}`)).json();
      expect(aList.items.map((t: { title: string }) => t.title)).toEqual([
        "A's tagged todo",
      ]);
    } finally {
      await contextA.close();
      await contextB.close();
    }
  });

  test("after logout, the next user in the same tab sees none of the first user's data", async ({
    page,
  }) => {
    await registerThroughUI(page, "logout-a");
    const apiA = await apiAs(page);
    await apiA.createTodo("A's private todo");
    await apiA.createTag("a-private-tag");
    await page.reload();
    // Loaded into the client cache: this is what must not leak.
    await expect(completionBox(page, "A's private todo")).toBeVisible();
    await expect(
      page.getByLabel("Tag", { exact: true }).locator("option", { hasText: "a-private-tag" })
    ).toHaveCount(1);

    await page.getByRole("button", { name: "Logout" }).click();
    await expect(page).toHaveURL("/login");

    await registerThroughUI(page, "logout-b");
    await expect(page.getByText("No todos yet")).toBeVisible();
    await expect(page.getByText("A's private todo", { exact: true })).toHaveCount(0);
    await expect(
      page.getByLabel("Tag", { exact: true }).locator("option", { hasText: "a-private-tag" })
    ).toHaveCount(0);
  });
});
