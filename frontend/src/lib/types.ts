// Shapes of the API's responses (see backend/app/schemas.py).

export type Tag = { id: number; kind: "occasion" | "recipient"; slug: string; name: string };

export type ProductImage = { id: number; alt_text: string; position: number; url: string };

export type Product = {
  id: number;
  sku: string;
  slug: string;
  name: string;
  description: string;
  price: string;
  is_active: boolean;
  tags: Tag[];
  images: ProductImage[];
  currency: string;
  available: number;
};

export type CartItem = {
  product_id: number;
  slug: string;
  name: string;
  image_url: string | null;
  unit_price: string;
  quantity: number;
  line_total: string;
  available: number;
};

export type Cart = {
  token: string | null;
  items: CartItem[];
  item_count: number;
  subtotal: string;
  gift_wrap: boolean;
  gift_message: string;
  gift_wrap_fee: string;
  gift_wrap_price: string;
  delivery_fee_colombo: string;
  delivery_fee_other: string;
  free_delivery_over: string;
  currency: string;
};

export type Customer = {
  id: number;
  email: string;
  full_name: string;
  phone: string | null;
};

export type Address = {
  id: number;
  label: string | null;
  recipient_name: string;
  phone: string | null;
  line1: string;
  line2: string | null;
  city: string;
  district: string | null;
  postal_code: string | null;
  is_default: boolean;
};

export type OrderStatus =
  | "pending"
  | "paid"
  | "packing"
  | "shipped"
  | "delivered"
  | "cancelled"
  | "refunded";

export type OrderSummary = {
  order_number: string;
  status: OrderStatus;
  total: string;
  item_count: number;
  created_at: string;
};

export type Order = {
  order_number: string;
  status: OrderStatus;
  email: string;
  customer_name: string;
  phone: string;
  items: {
    product_id: number;
    product_name: string;
    unit_price: string;
    quantity: number;
    line_total: string;
  }[];
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
  expires_at: string | null;
  paid_at: string | null;
  created_at: string;
  events: { to_status: OrderStatus; note: string; created_at: string }[];
  access_key: string | null;
  currency: string;
};

export type PaymentForm = { action_url: string; fields: Record<string, string> };

export type CheckoutResult = {
  order_number: string;
  order_key: string;
  total: string;
  currency: string;
  expires_at: string;
  payment: PaymentForm;
};
