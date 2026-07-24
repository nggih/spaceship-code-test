import { expect, test } from "@playwright/test";

test("loads the dashboard and applies an operational filter", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /See where orders move/i })).toBeVisible();
  await expect(page.getByText("400 source rows")).toBeVisible();
  await expect(page.getByText("Total orders")).toBeVisible();
  await expect(page.getByTestId("kpi-order_count")).toContainText("400");

  // Carrier is now a multi-select popover: open it and tick DHL.
  await page.getByRole("button", { name: /^Carrier filter/ }).click();
  await page.getByRole("option", { name: "DHL" }).click();
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

test("auto-runs a sparse SKU forecast with a visible confidence warning", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("tab", { name: "Forecast" }).click();
  await expect(page.getByText("Forecast and inventory guide")).toBeVisible();
  await page.getByLabel("Scope").selectOption("sku");
  await page.getByRole("combobox", { name: "SKU", exact: true }).fill("PAPER-0197");
  await page.getByLabel("Horizon").selectOption("2");
  // No button — the forecast recomputes automatically once a known SKU is entered.
  await expect(page.getByText(/Forecast demand for PAPER-0197/i)).toBeVisible();
  await expect(page.getByText("Forecast model selection")).toBeVisible();
  await expect(page.getByText("Auto selected")).toBeVisible();
  await expect(page.getByText(/Low-confidence SKU forecast/i)).toBeVisible();

  await page.getByLabel("Method").selectOption("linear_trend");
  await expect(page.getByText("Manually selected")).toBeVisible();
  await expect(page.getByText(/ordinary least-squares linear trend/i).first()).toBeVisible();
});

test("supports a multi-turn AI conversation and sends bounded context", async ({ page }) => {
  const requests: Array<Record<string, unknown>> = [];
  await page.route("**/api/ask", async (route) => {
    requests.push(route.request().postDataJSON());
    const firstTurn = requests.length === 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        kind: "clarification",
        message: firstTurn
          ? "Which carrier or region should I compare?"
          : "Would you like the highest or lowest delay rate?",
        suggestions: firstTurn
          ? ["Compare carrier delay rates"]
          : ["Show the highest delay rate"],
        query_plan: { intent: "clarification" },
        meta: { model: "test-model" },
      }),
    });
  });
  await page.goto("/");
  await page.getByRole("tab", { name: "Ask AI" }).click();
  await expect(page.getByText(/Ask a question, then refine it naturally/i)).toBeVisible();
  const input = page.getByLabel("Message Logistics AI");
  await input.fill("Why?");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByText("Which carrier or region should I compare?")).toBeVisible();

  await input.fill("Compare carrier delay rates");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(
    page.getByText("Would you like the highest or lowest delay rate?"),
  ).toBeVisible();
  expect(requests).toHaveLength(2);
  expect(requests[0].history).toEqual([]);
  expect(requests[1].history).toEqual([
    { role: "user", content: "Why?" },
    {
      role: "assistant",
      content: "Which carrier or region should I compare?",
    },
  ]);

  await page.getByRole("button", { name: "New conversation" }).click();
  await expect(page.getByText("Why?", { exact: true })).not.toBeVisible();
  await expect(page.getByText(/Ask a question, then refine it naturally/i)).toBeVisible();
});
