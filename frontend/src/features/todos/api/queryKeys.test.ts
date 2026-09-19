import { hashKey } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import {
  DEFAULT_TODO_FILTERS,
  normalizeTodoListQuery,
  todoKeys,
  todoListQueryKey,
  toTodoListParams,
  type TodoListInput,
} from "./queryKeys";

// hashKey is how TanStack Query decides whether two keys are the same query,
// so comparing hashes tests exactly the property that matters.
const hashOf = (input: TodoListInput) => hashKey(todoListQueryKey(input));

const base: TodoListInput = {
  page: 1,
  pageSize: 20,
  filters: {
    status: "active",
    tagId: "11111111-1111-1111-1111-111111111111",
    keyword: "report",
    dateFrom: "2026-01-01",
    dateTo: "2026-01-31",
  },
};

describe("todoListQueryKey", () => {
  it("is under the ['todos'] prefix, so prefix invalidation reaches it", () => {
    const key = todoListQueryKey(base);
    expect(key.slice(0, todoKeys.all.length)).toEqual([...todoKeys.all]);
  });

  it("gives the same key for the same normalized filters", () => {
    expect(hashOf(base)).toBe(hashOf({ ...base, filters: { ...base.filters } }));
  });

  it("does not depend on property order", () => {
    const f = base.filters!;
    const reordered: TodoListInput = {
      filters: {
        dateTo: f.dateTo,
        keyword: f.keyword,
        dateFrom: f.dateFrom,
        tagId: f.tagId,
        status: f.status,
      },
      pageSize: base.pageSize,
      page: base.page,
    };
    expect(hashOf(reordered)).toBe(hashOf(base));
  });

  it("normalizes keyword whitespace and case", () => {
    const variants = ["report", "  report ", "REPORT", " RePoRt\t"];
    const hashes = variants.map((keyword) =>
      hashOf({ ...base, filters: { ...base.filters, keyword } })
    );
    expect(new Set(hashes).size).toBe(1);
  });

  it("treats defaults and omitted values alike", () => {
    const explicit = hashOf({ page: 1, pageSize: 20, filters: DEFAULT_TODO_FILTERS });
    expect(hashOf({})).toBe(explicit);
    expect(hashOf({ filters: { keyword: "   ", tagId: "", dateFrom: "" } })).toBe(
      explicit
    );
  });

  it.each<[string, TodoListInput]>([
    ["page", { ...base, page: 2 }],
    ["page_size", { ...base, pageSize: 50 }],
    ["status", { ...base, filters: { ...base.filters, status: "completed" } }],
    ["status (all)", { ...base, filters: { ...base.filters, status: "all" } }],
    [
      "tag_id",
      {
        ...base,
        filters: { ...base.filters, tagId: "22222222-2222-2222-2222-222222222222" },
      },
    ],
    ["tag_id (none)", { ...base, filters: { ...base.filters, tagId: null } }],
    ["keyword", { ...base, filters: { ...base.filters, keyword: "invoice" } }],
    ["date_from", { ...base, filters: { ...base.filters, dateFrom: "2026-01-02" } }],
    ["date_to", { ...base, filters: { ...base.filters, dateTo: "2026-01-30" } }],
  ])("changes when %s changes", (_name, changed) => {
    expect(hashOf(changed)).not.toBe(hashOf(base));
  });
});

describe("normalizeTodoListQuery", () => {
  it("defaults to page 1 and page_size 20", () => {
    expect(normalizeTodoListQuery({})).toEqual({
      page: 1,
      page_size: 20,
      status: null,
      tag_id: null,
      keyword: null,
      date_from: null,
      date_to: null,
    });
  });

  it("never asks for more than the API's 100 per page", () => {
    expect(normalizeTodoListQuery({ pageSize: 10000 }).page_size).toBe(100);
    expect(normalizeTodoListQuery({ pageSize: 0 }).page_size).toBe(20);
    expect(normalizeTodoListQuery({ page: 0 }).page).toBe(1);
  });

  it("keeps a picked date exactly as YYYY-MM-DD and drops anything else", () => {
    const query = normalizeTodoListQuery({
      filters: { dateFrom: "2026-03-01", dateTo: "03/31/2026" },
    });
    expect(query.date_from).toBe("2026-03-01");
    expect(query.date_to).toBeNull();
  });
});

describe("toTodoListParams", () => {
  it("sends page and page_size, and only the filters that are set", () => {
    expect(
      toTodoListParams(
        normalizeTodoListQuery({ filters: { status: "completed", keyword: " A " } })
      )
    ).toEqual({ page: 1, page_size: 20, status: "completed", keyword: "a" });
  });
});
