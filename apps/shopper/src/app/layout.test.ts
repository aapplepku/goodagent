import { describe, expect, it } from "vitest";
import { metadata } from "./layout";

describe("shopper page metadata", () => {
  it("uses the public GoodAgent name", () => {
    expect(metadata.title).toBe("GoodAgent Shop");
    expect(metadata.description).toBe("Conversational catalog discovery");
  });
});
