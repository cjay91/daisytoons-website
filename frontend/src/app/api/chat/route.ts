import { api, apiResponse } from "@/lib/api";
import { getTokens, liveToken, setCartToken } from "@/lib/session";
import type { Cart } from "@/lib/types";

// The chat widget's way to the API's streaming chat. Like the Server Actions, it adds the
// visitor's login and cart from their httpOnly cookies, which the browser can't read.

const AGENTS = new Set(["gift_concierge", "support"]);

export async function POST(request: Request) {
  const body = await request.json().catch(() => null);
  if (!body || !AGENTS.has(body.agent) || typeof body.message !== "string") {
    return Response.json({ error: { message: "Bad request." } }, { status: 400 });
  }
  const token = await liveToken();
  let { cartToken } = await getTokens();
  // The concierge can add to the cart, so a guest needs one before the chat starts. Cookies
  // can only be set before the reply starts streaming.
  if (body.agent === "gift_concierge" && !token) {
    const cart = await api<Cart>("/cart", { method: "POST", cartToken });
    if (cart.token && cart.token !== cartToken) {
      cartToken = cart.token;
      await setCartToken(cartToken);
    }
  }

  const upstream = await apiResponse("/agents/chat", {
    method: "POST",
    forwardIp: true,
    token,
    cartToken,
    body: { agent: body.agent, message: body.message, conversation_id: body.conversation_id ?? null },
  });
  if (!upstream.ok || !upstream.body) {
    const data = await upstream.json().catch(() => null);
    const message = data?.error?.message ?? "The assistant isn't available right now.";
    return Response.json({ error: { message } }, { status: upstream.status });
  }
  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
    },
  });
}
