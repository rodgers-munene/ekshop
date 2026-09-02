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
  is_featured: boolean;
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
  order?: Order;
}

export interface DeliveryAgent {
  id: string;
  name: string;
  email: string;
  phone: string;
  status: string;
  total_deliveries: number;
  rating_avg: string;
  created_at: string;
}

// Notifications
export interface Notification {
  id: string;
  type: string;
  title: string;
  body?: string;
  data?: Record<string, unknown>;
  is_read: boolean;
  created_at: string;
}

// Messaging
export interface Message {
  id: string;
  sender_id?: string;
  body: string;
  is_read: boolean;
  created_at: string;
}

export interface Conversation {
  id: string;
  buyer_id: string;
  shop_id: string;
  last_message_at: string;
  messages: Message[];
}

export interface ConversationSummary {
  id: string;
  buyer_id: string;
  shop_id: string;
  shop_name?: string;
  buyer_name?: string;
  last_message_at: string;
  last_message_body?: string;
  unread_count: number;
}

// Admin
export interface AdminStats {
  total_users: number;
  total_buyers: number;
  total_sellers: number;
  new_users_7d: number;
  total_shops: number;
  shops_pending_verification: number;
  total_products: number;
  total_orders: number;
  orders_7d: number;
  revenue_total: string;
  revenue_7d: string;
}

export interface AdminTrendPoint {
  label: string;
  revenue: number;
  orders: number;
}

// Investor
export interface TopSeller {
  shop_name: string;
  revenue: string;
  orders: number;
}

export interface TopBuyer {
  name: string;
  revenue: string;
  orders: number;
}

export interface InvestorOverview {
  revenue_total: string;
  revenue_30d: string;
  revenue_7d: string;
  total_orders: number;
  orders_30d: number;
  orders_7d: number;
  total_buyers: number;
  total_sellers: number;
  total_shops: number;
  total_products: number;
  losses_total: string;
  losses_count: number;
  order_status_counts: Record<string, number>;
  top_sellers: TopSeller[];
  top_buyers: TopBuyer[];
  available_years: number[];
}

export interface InvestorTrendPoint {
  label: string;
  revenue: number;
  orders: number;
}

export interface InvestorDailyRevenuePoint {
  date: string;
  revenue: string;
  orders: number;
}

export interface InvestorDailyRevenueResponse {
  total: number;
  page: number;
  limit: number;
  results: InvestorDailyRevenuePoint[];
}

export interface DeliveryRates {
  id: string;
  same_county_fee: string;
  same_region_fee: string;
  different_region_fee: string;
  unknown_origin_fee: string;
  use_geo_pricing: boolean;
  updated_at: string;
}

export interface DeliverySimulationRow {
  shop_id: string;
  shop_name: string;
  shop_county: string | null;
  region: string | null;
  geo_fees: Record<string, string>;
  cart_total_fee: string;
}

export interface DeliverySimulationResponse {
  buyer_counties: string[];
  buyer_regions: Record<string, string | null>;
  sample_cart_total: string;
  live_model: "geo" | "cart_total";
  rows: DeliverySimulationRow[];
}

export interface HeroSlide {
  id: string;
  image_url: string;
  title?: string;
  link_url?: string;
  sort_order: number;
  is_active: boolean;
  created_at: string;
}

export interface Promotion {
  id: string;
  product_id: string;
  label?: string;
  starts_at?: string;
  ends_at?: string;
  sort_order: number;
  is_active: boolean;
  created_at: string;
  product?: Product;
}

export interface MerchantActivityMetrics {
  active_merchants_7d: number;
  active_merchants_30d: number;
  merchants_receiving_orders: number;
  merchants_processing_orders: number;
  merchants_zero_activity: number;
  sellers_logged_in: number;
  products_updated: number;
  avg_transactions_per_merchant: number;
}

export interface SalesDemandMetrics {
  total_orders: number;
  gmv: string;
  average_order_value: string;
  new_customers: number;
  repeat_customers: number;
  customer_acquisition_rate: number;
  cart_abandonment_rate: number;
  order_cancellation_rate: number;
}

export interface CustomerRetentionMetrics {
  new_customers: number;
  returning_customers: number;
  repeat_purchase_rate: number;
  churn_rate: number;
  retention_30d: number;
  orders_per_customer: number;
  avg_days_between_purchases: number;
  customer_complaints: number;
}

export interface OperationsDeliveryMetrics {
  orders_received: number;
  orders_accepted: number;
  orders_fulfilled: number;
  orders_cancelled: number;
  avg_dispatch_time_hours: number;
  avg_delivery_time_hours: number;
  on_time_delivery_rate: number | null;
  failed_deliveries: number;
  rider_utilization: number;
  delivery_revenue: string;
}

export interface OrderNotificationRecipient {
  id: string;
  email: string;
  label?: string;
  is_active: boolean;
  created_at: string;
}

// Geography (Kenya county → subcounty → ward)
export interface County {
  id: string;
  name: string;
}

export interface SubCounty {
  id: string;
  name: string;
}

export interface Ward {
  id: string;
  name: string;
}

export interface WardWithLocation extends Ward {
  subcounty_name: string;
  county_name: string;
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
  ward_id?: string;
  ward?: WardWithLocation;
  exact_location?: string;
  apartment?: string;
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
