import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { App } from "@/app/App";
import { AppShell } from "./AppShell";

it("exposes navigation and changes theme", async () => {
  renderWithProviders(
    <AppShell>
      <main>工作区</main>
    </AppShell>,
  );

  expect(screen.getByRole("navigation", { name: "主导航" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: /主题/ }));
  await userEvent.click(
    await screen.findByRole("menuitemradio", { name: "深海" }),
  );
  expect(document.documentElement.dataset.theme).toBe("deep");
});

it("uses the application shell in the live app", () => {
  renderWithProviders(<App />);

  expect(screen.getByRole("navigation", { name: "主导航" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "教学工作台" })).toBeVisible();
});
