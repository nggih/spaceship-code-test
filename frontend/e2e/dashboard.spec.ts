import { expect, test } from "@playwright/test";

test("loads the dashboard and applies an operational filter", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /See where orders move/i })).toBeVisible();
  await expect(page.getByText("400 source rows")).toBeVisible();
  await expect(page.getByText("Total orders")).toBeVisible();
  await expect(page.getByTestId("kpi-order_count")).toContainText("400");

  await page.getByRole("combobox", { name: "Carrier", exact: true }).selectOption("DHL");
  await expect(page.getByText("1 operational filters active")).toBeVisible();
  await expect(page.getByTestId("kpi-order_count")).not.toContainText("400");
});

test("runs diagnostics and exposes the calculation", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Analyze delay drivers" }).click();
  await expect(page.getByText(/strongest observed delay association/i)).toBeVisible();
  await expect(page.getByText(/do not prove causation/i)).toBeVisible();
  await expect(page.getByText("Underlying result").first()).toBeVisible();
});

test("runs a sparse SKU forecast with a visible confidence warning", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Forecast and inventory guide")).toBeVisible();
  await page.getByLabel("Scope").selectOption("sku");
  await page.getByRole("combobox", { name: "SKU", exact: true }).fill("PAPER-0197");
  await page.getByLabel("Horizon").selectOption("2");
  await page.getByRole("button", { name: "Run forecast" }).click();
  await expect(page.getByText(/Forecast demand for PAPER-0197/i)).toBeVisible();
  await expect(page.getByText(/Low-confidence SKU forecast/i)).toBeVisible();
});

test("renders an AI clarification and saves query history", async ({ page }) => {
  await page.route("**/api/ask", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        kind: "clarification",
        message: "Which carrier or region should I compare?",
        suggestions: ["Which carrier has the highest delay rate?"],
        query_plan: { intent: "clarification" },
        meta: { model: "test-model" },
      }),
    });
  });
  await page.goto("/");
  const input = page.getByLabel("Ask a logistics analytics question");
  await input.fill("Why?");
  await page.getByRole("button", { name: "Submit question" }).click();
  await expect(page.getByText("Which carrier or region should I compare?")).toBeVisible();
  await expect(page.getByText("Recent questions (1)")).toBeVisible();
});
