export type StaffRole = "admin" | "packer" | "support";

export type Staff = {
  id: number;
  email: string;
  full_name: string;
  role: StaffRole;
  is_active: boolean;
  two_factor_enabled: boolean;
};

export type OrderStatus = "pending" | "paid" | "packing" | "shipped" | "delivered" | "cancelled" | "refunded";

export type OrderSummary = {
  order_number: string;
  status: OrderStatus;
  customer_name: string;
  email: string;
  district: string;
  total: string;
  item_count: number;
  gift_wrap: boolean;
  needs_attention: string | null;
  created_at: string;
  paid_at: string | null;
};

export type OrderList = { orders: OrderSummary[]; total: number };

type StaffBrief = { id: number; full_name: string };

export type OrderAction = "pack" | "ship" | "deliver" | "resend_tracking" | "cancel" | "refund" | "resolve_attention";

export type Order = {
  order_number: string;
  status: OrderStatus;
  email: string;
  customer_name: string;
  phone: string;
  items: { product_id: number; product_name: string; unit_price: string; quantity: number; line_total: string }[];
  subtotal: string;
  gift_wrap: boolean;
  gift_wrap_fee: string;
  gift_message: string;
  delivery_fee: string;
  total: string;
  shipping_address: {
    line1: string;
    line2?: string | null;
    city: string;
    district: string;
    postal_code?: string | null;
  };
  notes: string | null;
  customer_id: number | null;
  needs_attention: string | null;
  payment_reference: string | null;
  paid_at: string | null;
  created_at: string;
  confirmation_sent_at: string | null;
  access_key: string | null;
  events: { from_status: OrderStatus | null; to_status: OrderStatus; note: string; staff: StaffBrief | null; created_at: string }[];
  shipment: {
    courier: string;
    tracking_number: string;
    tracking_url: string | null;
    shipped_at: string;
    delivered_at: string | null;
    notified_at: string | null;
    staff: StaffBrief | null;
  } | null;
  refunds: { id: number; amount: string; reason: string; reference: string | null; restocked: boolean; staff: StaffBrief | null; created_at: string }[];
  payment_events: { provider: string; provider_payment_id: string | null; status_code: string; signature_valid: boolean; outcome: string; received_at: string }[];
  refunded_total: string;
  refundable: string;
  actions: OrderAction[];
};

export type PickList = {
  order_numbers: string[];
  items: {
    product_id: number;
    sku: string;
    name: string;
    bin_location: string | null;
    quantity: number;
    orders: { order_number: string; quantity: number }[];
  }[];
};

export type Tag = { id: number; kind: "occasion" | "recipient"; slug: string; name: string };

export type Inventory = {
  product_id: number;
  on_hand: number;
  reserved: number;
  reorder_point: number;
  bin_location: string | null;
};

export type Product = {
  id: number;
  sku: string;
  slug: string;
  name: string;
  description: string;
  price: string;
  is_active: boolean;
  tags: Tag[];
  images: { id: number; url: string; alt_text: string; position: number }[];
  inventory: Inventory | null;
  available: number;
};

export type StockReason = "received" | "count" | "damaged" | "returned" | "correction" | "import" | "sale" | "order_cancelled";

export type StockAdjustment = {
  id: number;
  reason: StockReason;
  quantity_change: number;
  on_hand_before: number;
  on_hand_after: number;
  note: string;
  staff_id: number | null;
  created_at: string;
};

export type LowStock = {
  product_id: number;
  sku: string;
  name: string;
  on_hand: number;
  reserved: number;
  available: number;
  reorder_point: number;
  bin_location: string | null;
  on_order: number;
};

export type Supplier = {
  id: number;
  name: string;
  email: string | null;
  phone: string | null;
  notes: string | null;
  is_active: boolean;
};

export type PurchaseOrderStatus = "draft" | "sent" | "received" | "cancelled";

export type PurchaseOrder = {
  id: number;
  supplier: Supplier;
  status: PurchaseOrderStatus;
  expected_at: string | null;
  notes: string | null;
  items: { product_id: number; quantity: number; unit_cost: string; line_total: string; product: { sku: string; name: string } }[];
  total: string;
  created_at: string;
  sent_at: string | null;
  received_at: string | null;
};

export type DailyReport = {
  day: string;
  orders: number;
  revenue: string;
  items_sold: number;
  average_order: string;
  refunds: string;
  top_products: { product_id: number; name: string; quantity: number; revenue: string }[];
  waiting_to_ship: number;
  needs_attention: number;
  low_stock: number;
  last_14_days: { day: string; orders: number; revenue: string }[];
  currency: string;
};

export type AgentRun = {
  id: number;
  agent: string;
  conversation_id: string;
  actor_kind: "staff" | "customer";
  customer_id: number | null;
  staff_id: number | null;
  status: "running" | "waiting" | "finished" | "stopped" | "failed";
  input: string;
  output: string | null;
  error: string | null;
  steps: number;
  input_tokens: number;
  output_tokens: number;
  cost: string;
  started_at: string;
  finished_at: string | null;
};

export type AgentTotals = { runs: number; failed: number; tokens: number; cost: string };

export type AgentRunList = {
  runs: AgentRun[];
  today: AgentTotals;
  last_7_days: AgentTotals;
  by_agent: Record<string, AgentTotals>;
};

export type ContentBlock = { type: string; id?: string; text?: string; name?: string; input?: unknown };

export type AgentMessage = {
  id: number;
  run_id: number;
  role: "user" | "assistant";
  content: ContentBlock[];
  model: string | null;
  stop_reason: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  cache_read_tokens: number | null;
  cache_write_tokens: number | null;
  cost: string | null;
  duration_ms: number | null;
  created_at: string;
};

export type AgentToolCall = {
  id: number;
  run_id: number;
  tool_use_id: string;
  tool: string;
  risk: string | null;
  input: Record<string, unknown>;
  output: unknown;
  error: string | null;
  duration_ms: number;
  created_at: string;
};

export type AgentConversation = {
  conversation_id: string;
  runs: AgentRun[];
  messages: AgentMessage[];
  tool_calls: AgentToolCall[];
  cost: string;
};
