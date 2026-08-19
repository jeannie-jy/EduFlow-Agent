import { afterEach, describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "@/test/mocks/handlers";
import { renderPage } from "@/test/render";
import { TemplateBrowser } from "@/pages/TemplateBrowser";

describe("TemplateBrowser", () => {
  afterEach(() => server.resetHandlers());

  it("uses theme-aware text and card surfaces", async () => {
    server.use(
      http.get("http://localhost:8000/api/knowledge/templates", () => HttpResponse.json({
        templates: [{
          id: "bubble-sort",
          concept: "冒泡排序",
          subject: "algorithm",
          difficulty: 1,
          object_types: ["array"],
        }],
      })),
    );

    renderPage(<TemplateBrowser />);

    const heading = await screen.findByRole("heading", { name: "知识模板库" });
    const templateLink = await screen.findByRole("link", { name: /冒泡排序/ });

    expect(heading).toHaveClass("text-[var(--foreground)]");
    expect(templateLink).toHaveClass("bg-[var(--card)]", "border-[var(--border)]");
  });
});
