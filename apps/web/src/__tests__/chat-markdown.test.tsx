import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { ChatMarkdown } from "../components/chat-markdown";

it("renders agent Markdown safely, with lists and emphasis", () => {
  const { container } = render(<ChatMarkdown>{"**Ready**\n\n- Catalog checked\n- Search tested\n\n[bad](javascript:alert)\n\n<script>alert(1)</script>\n\n![track](https://example.com/pixel)"}</ChatMarkdown>);
  expect(screen.getByText("Ready").tagName).toBe("STRONG");
  expect(screen.getAllByRole("listitem")).toHaveLength(2);
  expect(container.querySelector("script, img, a")).toBeNull();
  expect(container.textContent).not.toContain("**");
});
