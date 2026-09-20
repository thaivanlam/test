import { describe, expect, it } from "vitest";
import { tagSchema, toTagPayload } from "./tag";

describe("tagSchema", () => {
  it("accepts a valid name and trims it", () => {
    const result = tagSchema.safeParse({ name: "  Work  " });
    expect(result.success).toBe(true);
    expect(result.data?.name).toBe("Work");
  });

  it.each(["", "   ", "\t\n"])("rejects an empty or blank name %j", (name) => {
    const result = tagSchema.safeParse({ name });
    expect(result.success).toBe(false);
    expect(result.error?.issues[0].message).toBe("Name is required");
  });

  it("accepts a 50-character name and rejects 51", () => {
    expect(tagSchema.safeParse({ name: "x".repeat(50) }).success).toBe(true);
    const tooLong = tagSchema.safeParse({ name: "x".repeat(51) });
    expect(tooLong.success).toBe(false);
    expect(tooLong.error?.issues[0].message).toBe(
      "Name must be at most 50 characters"
    );
  });

  it("measures the name after trimming, as the API does", () => {
    expect(tagSchema.safeParse({ name: ` ${"x".repeat(50)} ` }).success).toBe(
      true
    );
  });

  it.each([undefined, null, "", "#ff0000", "c".repeat(20)])(
    "accepts the optional color %j",
    (color) => {
      expect(tagSchema.safeParse({ name: "ok", color }).success).toBe(true);
    }
  );

  it("rejects a color over 20 characters", () => {
    const result = tagSchema.safeParse({ name: "ok", color: "c".repeat(21) });
    expect(result.success).toBe(false);
    expect(result.error?.issues[0].message).toBe(
      "Color must be at most 20 characters"
    );
  });
});

describe("toTagPayload", () => {
  it("sends an empty or missing color as null", () => {
    expect(toTagPayload({ name: "a", color: "" })).toEqual({
      name: "a",
      color: null,
    });
    expect(toTagPayload({ name: "a" })).toEqual({ name: "a", color: null });
    expect(toTagPayload({ name: "a", color: "red" })).toEqual({
      name: "a",
      color: "red",
    });
  });
});
