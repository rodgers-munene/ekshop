// Users
export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: "buyer" | "seller" | "admin";
  phone?: string;
  avatar_url?: string;
  county?: string;
  status: string;
  created_at: string;
}

// Categories
export interface Category {
  id: string;
  name: string;
  slug: string;
  parent_id?: string;
  icon_url?: string;
  is_active: boolean;
  children?: Category[];
}

// Shops
export interface Shop {
  id: string;
  name: string;
  slug: string;
  description?: string;
  logo_url?: string;
  banner_url?: string;
  county?: string;
  is_verified: boolean;
  rating_avg: string;
  rating_count: number;
  total_sales: string;
}

// Products
export interface ProductImage {
  id: string;
  url: string;
  is_primary: boolean;
  sort_order: number;
}

export interface ShopSummary {
  id: string;
  name: string;
  slug: string;
  is_verified: boolean;
  rating_avg: string;
  rating_count: number;
}

export interface ProductVariant {
  id: string;
  name: string;
  value: string;
  price_delta: string;
  stock_qty: number;
  sku?: string;
}

export interface Product {
  id: string;
  shop_id: string;
  category_id?: string;
  name: string;
  slug: string;
  description?: string;
  price: string;
  compare_price?: string;
  sku?: string;
  stock_qty: number;
  status: string;
  condition?: string;
  tags?: string[];
  shop?: ShopSummary;
  images: ProductImage[];
  variants?: ProductVariant[];
  rating_avg?: string;
  rating_count?: number;
  created_at: string;
}

export interface ProductListResponse {
  total: number;
  page: number;
  limit: number;
  results: Product[];
}

// Orders
export interface OrderItem {
  id: string;
  product_id?: string;
  product_snapshot: { name: string; price: string };
  unit_price: string;
  quantity: number;
  line_total: string;
}

export interface Order {
  id: string;
  shop: Shop;
  status: string;
  subtotal: string;
  delivery_fee: string;
  total: string;
  items: OrderItem[];
  created_at: string;
  buyer_name?: string;
  delivery_address?: {
    first_name: string;
    last_name: string;
    phone: string;
    county: string;
    town: string;
    exact_location?: string;
    apartment?: string;
  };
}

export interface OrderGroup {
  id: string;
  status: string;
  subtotal: string;
  delivery_fee: string;
  total: string;
  orders: Order[];
  created_at: string;
}

// Delivery
export interface DeliveryEvent {
  id: string;
  status: string;
  actor_role: string;
  notes?: string;
  created_at: string;
}

export interface Delivery {
  id: string;
  order_id: string;
  status: string;
  tracking_number?: string;
  estimated_at?: string;
  delivered_at?: string;
  events: DeliveryEvent[];
}

// Addresses
export interface UserAddress {
  id: string;
  label?: string;
  first_name: string;
  last_name: string;
  phone: string;
  county: string;
  town: string;
  street?: string;
  building?: string;
  is_default: boolean;
}

// Seller dashboard
export interface ShopDashboardStats {
  total_sales: number;
  rating_avg: string;
  rating_count: number;
  total_products: number;
  total_orders: number;
}

// Pagination helper
export interface PaginatedResponse<T> {
  total: number;
  page: number;
  limit: number;
  results: T[];
}
