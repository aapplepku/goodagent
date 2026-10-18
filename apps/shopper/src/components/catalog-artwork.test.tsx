import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CatalogArtwork } from "./catalog-artwork";

describe("catalog artwork", () => {
  it("labels the three sample photographs and credits their source and license", () => {
    render(<CatalogArtwork />);
    expect(screen.getAllByRole("img")).toHaveLength(3);
    for (const image of screen.getAllByRole("img")) {
      expect(image.getAttribute("alt")).toMatch(/^Sample catalog:/);
      expect(image.getAttribute("src")).not.toContain("shopper-grocery-spread");
    }
    expect(screen.getByRole("link", { name: "Amazon.com / ABO" })).toHaveAttribute(
      "href", "https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/index.html",
    );
    expect(screen.getByRole("link", { name: "CC BY 4.0" })).toHaveAttribute(
      "href", "https://creativecommons.org/licenses/by/4.0/",
    );
  });
});
