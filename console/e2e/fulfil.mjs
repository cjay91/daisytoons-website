// End-to-end check of the staff console against the running stack (API with the sample
// products imported, fake payment gateway, Mailpit, console on :3001).
//
//   ADMIN_EMAIL=... ADMIN_PASSWORD=... node e2e/fulfil.mjs
//
// A customer pays for a gift-wrapped order. An admin logs in, packs it from the queue, reads
// the pick list and packing slip, ships it with a tracking number, and the customer gets the
// tracking email. Then the admin restocks a product through a purchase order and checks the
// sales summary.

import { chromium } from "playwright";

const CONSOLE = process.env.CONSOLE_URL ?? "http://localhost:3001";
const API = process.env.API_URL ?? "http://localhost:8000";
const MAILPIT = process.env.MAILPIT_URL ?? "http://localhost:8025";
const ADMIN_EMAIL = process.env.ADMIN_EMAIL ?? "admin@daisytoons.lk";
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD ?? "admin-password";

function check(condition, message) {
  if (!condition) throw new Error(message);
  console.log(`ok: ${message}`);
}

// Waits for content that streams in, then reports it.
async function see(locator, message) {
  await locator.first().waitFor({ timeout: 20000 });
  console.log(`ok: ${message}`);
}

async function call(path, options = {}) {
  const response = await fetch(`${API}${path}`, options);
  if (!response.ok) throw new Error(`${path}: ${response.status} ${await response.text()}`);
  return response.json();
}

/** A guest buys two of a product with gift wrap, paying through the fake gateway. */
async function paidOrder(product) {
  const { token } = await call("/cart", { method: "POST" });
  const headers = { "X-Cart-Token": token, "Content-Type": "application/json" };
  await call(`/cart/items/${product.id}`, { method: "PUT", headers, body: JSON.stringify({ quantity: 2 }) });
  await call("/cart", { method: "PATCH", headers, body: JSON.stringify({ gift_wrap: true, gift_message: "Happy birthday, Amma!" }) });
  const order = await call("/checkout", {
    method: "POST",
    headers,
    body: JSON.stringify({
      email: "e2e-customer@example.com",
      customer_name: "Console Test",
      phone: "0771234567",
      address: { line1: "5 Temple Road", city: "Kandy", district: "Kandy" },
    }),
  });
  const form = new URLSearchParams({ order_id: order.order_number, amount: order.total, currency: "LKR", status_code: "2" });
  await fetch(`${API}/payments/fake/complete`, { method: "POST", body: form, redirect: "manual" });
  return order.order_number;
}

async function trackingEmail(trackingNumber) {
  for (let i = 0; i < 20; i++) {
    const found = await (await fetch(`${MAILPIT}/api/v1/search?query=${encodeURIComponent(trackingNumber)}`)).json();
    if (found.messages?.length) {
      const message = await (await fetch(`${MAILPIT}/api/v1/message/${found.messages[0].ID}`)).json();
      return message;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return null;
}

const products = await call("/products");
const product = products.find((p) => p.available > 3);
const number = await paidOrder(product);
console.log(`Order ${number} paid`);

const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("dialog", (dialog) => dialog.accept());

  // Log in
  await page.goto(`${CONSOLE}/orders`);
  await page.waitForURL(/\/login/);
  await page.getByLabel("Email").fill(ADMIN_EMAIL);
  await page.getByLabel("Password").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Log in" }).click();
  await page.waitForURL(`${CONSOLE}/`);
  await see(page.getByText("Paid, waiting to pack"), "logged in to the dashboard");

  // The queue: pack the order
  await page.goto(`${CONSOLE}/orders`);
  await see(page.getByRole("link", { name: number }), "paid order is in the queue");
  await page.getByLabel(`Select ${number}`).check();
  await page.getByRole("button", { name: "Start packing selected" }).click();
  await page.waitForURL(/\/packing/);
  await see(page.getByRole("cell", { name: product.name }), "pick list shows the product");
  check((await page.getByText(`${number} × 2`).count()) === 1, "pick list says how many for the order");

  // Packing slip
  await page.goto(`${CONSOLE}/orders/${number}/slip`);
  await see(page.getByText("Happy birthday, Amma!"), "packing slip has the gift message");
  await see(page.getByText("5 Temple Road"), "label has the address");

  // Ship with tracking
  await page.goto(`${CONSOLE}/orders/${number}`);
  await see(page.getByRole("heading", { name: "Ship" }), "order page offers shipping");
  const trackingNumber = `DX-E2E-${Date.now()}`;
  await page.getByLabel("Courier").fill("Domex");
  await page.getByLabel("Tracking number").fill(trackingNumber);
  await page.getByRole("button", { name: "Mark shipped and email customer" }).click();
  // The ship form goes away once the order has shipped, and the shipment shows instead.
  await see(page.getByText(trackingNumber), "tracking number shows on the order");
  await see(page.getByText(/Customer emailed/), "order page says the customer was emailed");
  const order = await call(`/orders/${number}?key=${new URL(await page.getByRole("link", { name: /order page/ }).getAttribute("href")).searchParams.get("key")}`);
  check(order.status === "shipped" && order.shipment.tracking_number === trackingNumber, "customer's order page shows the tracking");

  const email = await trackingEmail(trackingNumber);
  check(email !== null, "tracking email arrived in Mailpit");
  check(email.To[0].Address === "e2e-customer@example.com", "tracking email went to the customer");
  check(email.Subject.includes("has shipped") && email.Text.includes("Domex"), "tracking email names the courier");

  // Restock through a purchase order
  await page.goto(`${CONSOLE}/suppliers`);
  const supplierName = `E2E Supplier ${Date.now()}`;
  // The add form; each existing supplier has its own edit form further up.
  await page.locator("#name").fill(supplierName);
  await page.getByRole("button", { name: "Add supplier" }).click();
  await see(page.getByText(supplierName), "supplier added");

  const before = (await call(`/products/${product.slug}`)).available;
  await page.goto(`${CONSOLE}/purchase-orders/new?product=${product.id}`);
  await see(page.getByLabel("Supplier"), "purchase order form");
  await page.getByLabel("Supplier").selectOption({ label: supplierName });
  await page.getByLabel("Quantity 1").fill("10");
  await page.getByLabel("Unit cost 1").fill("500");
  await page.getByRole("button", { name: "Save draft" }).click();
  await page.waitForURL(/\/purchase-orders\/\d+$/);
  await see(page.getByText("Rs 5,000").first(), "purchase order saved");
  await page.getByRole("button", { name: "Mark sent to supplier" }).click();
  await see(page.getByText("sent", { exact: true }), "purchase order sent");
  await page.getByRole("button", { name: "Goods received: add to stock" }).click();
  await see(page.getByText("received", { exact: true }), "purchase order received");
  const after = (await call(`/products/${product.slug}`)).available;
  check(after === before + 10, `stock went from ${before} to ${after}`);

  // Product page and sales summary
  await page.goto(`${CONSOLE}/products/${product.id}`);
  await see(page.getByRole("cell", { name: "Purchase order", exact: false }), "stock history shows the delivery");
  await page.goto(`${CONSOLE}/reports`);
  await see(page.getByRole("heading", { name: "Revenue, last 14 days" }), "sales summary");
  check(!(await page.getByText("No sales that day.").isVisible()), "today's sales are listed");

  check(errors.length === 0, `no page errors ${errors.join("; ")}`);
} finally {
  await browser.close();
}
