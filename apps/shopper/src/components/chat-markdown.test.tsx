import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { ChatMarkdown } from "./chat-markdown";

it("renders assistant emphasis and lists without exposing raw markers", () => {
  const { container } = render(<ChatMarkdown>{"For **$40**, consider:\n\n1. **A candle**\n2. A blanket"}</ChatMarkdown>);
  expect(screen.getByText("$40").tagName).toBe("STRONG");
  expect(screen.getAllByRole("listitem")).toHaveLength(2);
  expect(container.textContent).not.toContain("**");
});

it("does not execute HTML or render unsafe links and tracking images", () => {
  const { container } = render(<ChatMarkdown>{'<script>alert(1)</script>\n\n[bad](javascript:alert) ![track](https://example.com/track) [safe](https://example.com/item)'}</ChatMarkdown>);
  expect(container.querySelector("script, img, iframe")).toBeNull();
  expect(screen.getAllByRole("link")).toHaveLength(1);
  expect(screen.getByRole("link", { name: "safe" })).toHaveAttribute("rel", "noopener noreferrer");
});
