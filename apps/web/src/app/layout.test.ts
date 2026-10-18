import { describe, expect, it } from "vitest";
import { metadata } from "./layout";

describe("manager page metadata", () => {
  it("uses the public GoodAgent name", () => {
    expect(metadata.title).toBe("GoodAgent Manager");
    expect(metadata.description).toBe("Conversational search and recommendation management workspace");
  });
});
