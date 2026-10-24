// End-to-end check of the storefront on a phone-sized screen, against the running stack
// (API with the sample products imported, fake payment gateway, storefront on :3000).
//
//   node e2e/shop.mjs
//
// A guest finds a gift, adds gift wrap, checks out and pays; then a new customer saves an
// address, checks out with it prefilled, and sees the order in their account.

import { chromium, devices } from "playwright";

const SITE = process.env.SITE_URL ?? "http://localhost:3000";
const API = process.env.API_URL ?? "http://localhost:8000";

function check(condition, message) {
  if (!condition) throw new Error(message);
  console.log(`ok: ${message}`);
}

// Waits for content that streams in, then reports it.
async function see(locator, message) {
  await locator.first().waitFor({ timeout: 20000 });
  console.log(`ok: ${message}`);
}

async function payWithFakeGateway(page) {
  await page.getByRole("button", { name: "Continue to payment" }).click();
  await page.waitForURL(/\/payments\/fake\/checkout/);
  await page.getByRole("button", { name: "Pay" }).click();
  await page.waitForURL(/\/order\/DT-/);
  await page.getByText("Thank you!").waitFor({ timeout: 20000 });
}

const browser = await chromium.launch();
try {
  const context = await browser.newContext({ ...devices["iPhone 13"] });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));

  // Browse and search
  await page.goto(SITE);
  await page.getByRole("link", { name: "Birthday" }).first().click();
  await page.waitForURL(/\/occasions\/birthday/);
  await see(page.getByRole("heading", { name: "Birthday gifts" }), "occasion page");
  await page.goto(`${SITE}/shop?q=mug`);
  await see(page.getByText(/gifts? matching "mug"/), "search results");

  const products = await (await fetch(`${API}/products`)).json();
  const product = products.find((p) => p.available > 2);
  await page.goto(`${SITE}/products/${product.slug}`);
  await see(page.getByRole("heading", { name: product.name }), "product page");

  // Guest checkout with gift wrap
  await page.getByRole("button", { name: "Add to cart" }).click();
  await page.getByText("Added.").waitFor();
  await page.goto(`${SITE}/cart`);
  await page.getByLabel(/Gift wrap this order/).check();
  await page.getByLabel("Gift message (optional)").fill("Happy birthday!");
  await page.getByRole("button", { name: "Save gift options" }).click();
  await page.getByText("Saved").waitFor();
  await page.getByRole("link", { name: "Check out" }).click();
  await page.getByLabel("Full name").fill("Nimali Perera");
  await page.getByLabel("Mobile number").fill("0771234567");
  await page.getByLabel("Email for your receipt").fill("nimali@example.com");
  await page.getByLabel("Address", { exact: true }).fill("12 Flower Road");
  await page.getByLabel("City or town").fill("Colombo 7");
  await page.getByLabel("District").selectOption("Colombo");
  await payWithFakeGateway(page);
  const total = Number(product.price) + 250 + (Number(product.price) >= 10000 ? 0 : 400);
  await see(page.getByText(`Rs ${total.toLocaleString("en-LK")}`), `guest order paid, total Rs ${total}`);
  await see(page.getByText("Happy birthday!"), "gift message on the order");

  // A customer account
  const email = `customer${Date.now()}@example.com`;
  await page.goto(`${SITE}/register?next=/account`);
  await page.getByLabel("Full name").fill("Kasun Silva");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("kasun-password");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForURL(/\/account$/);
  await see(page.getByText("No orders yet."), "new account has no orders");

  await page.goto(`${SITE}/account/addresses`);
  const form = page.locator("section").filter({ hasText: "Add an address" });
  await form.getByLabel("Recipient name").fill("Kasun Silva");
  await form.getByLabel("Address", { exact: true }).fill("5 Lake Road");
  await form.getByLabel("City or town").fill("Kandy");
  await form.getByLabel("District").selectOption("Kandy");
  await form.getByLabel("Phone (optional)").fill("0719876543");
  await form.getByRole("button", { name: "Add address" }).click();
  await page.getByText("Saved").waitFor();

  await page.goto(`${SITE}/products/${product.slug}`);
  await page.getByRole("button", { name: "Add to cart" }).click();
  await page.getByText("Added.").waitFor();
  await page.goto(`${SITE}/checkout`);
  await page.getByLabel("District").waitFor();
  check((await page.getByLabel("District").inputValue()) === "Kandy", "checkout prefilled from the saved address");
  await payWithFakeGateway(page);

  await page.goto(`${SITE}/account`);
  await see(page.locator('a[href^="/account/orders/DT-"]'), "order in the account");
  await page.locator('a[href^="/account/orders/DT-"]').click();
  await see(page.getByText("Being packed"), "order tracking shown");

  const sitemap = await (await fetch(`${SITE}/sitemap.xml`)).text();
  check(sitemap.includes(`/products/${product.slug}`), "sitemap lists products");
  check(errors.length === 0, `no page errors ${errors.join("; ")}`);
} finally {
  await browser.close();
}
