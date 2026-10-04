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
  town?: string;
  phone?: string;
  exact_location?: string;
  seller_id?: string;
  is_verified: boolean;
  is_featured: boolean;
  rating_avg: string;
  rating_count: number;
  total_sales: string;
  lat?: number;
  lng?: number;
  distance_km?: number;
}

export type SubscriptionStatus = "pending_payment" | "active" | "cancelled" | "past_due" | "trialing";
export type BillingInterval = "monthly" | "annual";

export interface SubscriptionPlan {
  code: string;
  name: string;
  price_monthly: string;
  price_yearly: string | null;
  max_products: number | null;
  commission_rate: string;
  trial_days: number;
}

export interface Subscription {
  status: SubscriptionStatus;
  plan: SubscriptionPlan;
  billing_interval: BillingInterval;
  current_period_start: string | null;
  current_period_end: string | null;
  // True while `status` is "active" only because of the one-time backfill
  // grace window, not because the seller has ever actually paid.
  awaiting_first_payment: boolean;
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
  buyer_id?: string;
  buyer_name?: string;
  delivery_address?: {
    first_name: string;
    last_name: string;
    phone: string;
    county: string;
    town: string;
    exact_location?: string;
    apartment?: string;
    lat?: number;
    lng?: number;
    sublocation?: string;
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
  distance_km?: number;
  duration_min?: number;
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
  current_lat?: number;
  current_lng?: number;
  last_location_update?: string;
  created_at: string;
}

export interface KYCAgent {
  id: string;
  name: string;
  email: string;
  phone: string;
  kyc_status: string;
  vehicle_type?: string;
  equipment_verified: boolean;
  wallet_balance: string;
}

export interface KYCAgentList {
  total: number;
  pending: number;
  results: KYCAgent[];
}

export interface LedgerEntry {
  id: string;
  delivery_id?: string;
  entry_type: string;
  amount: string;
  balance_after: string;
  reference?: string;
  status: string;
  failure_reason?: string;
  created_at: string;
}

export interface LedgerList {
  agent_id: string;
  wallet_balance: string;
  entries: LedgerEntry[];
}

export interface DeliveryPricingRule {
  id: string;
  vehicle_type: string;
  base_fare: string;
  per_km_rate: string;
  per_minute_rate: string;
  rain_multiplier: string;
  peak_hours_multiplier: string;
  supply_demand_multiplier: string;
  max_surge_cap: string;
  currency: string;
  is_active: boolean;
}

export interface PingDispatchResponse {
  delivery_id: string;
  offers_created: number;
  offers: PingOffer[];
}

export interface PingOffer {
  id: string;
  delivery_id: string;
  status: string;
  queue_position: number;
  expires_at?: string;
  created_at: string;
}

export interface RouteStop {
  delivery_id: string;
  tracking_number: string;
  buyer_name: string;
  address: string;
  lat?: number;
  lng?: number;
  distance_from_previous_km?: number;
  duration_from_previous_min?: number;
}

export interface RouteOptimizationResponse {
  origin_lat?: number;
  origin_lng?: number;
  total_distance_km?: number;
  total_duration_min?: number;
  stops: RouteStop[];
}

// ── Fulfillment (one per order; many delivery jobs beneath it) ────────────────
// Mirrors app/schemas/fulfillment.py and app/schemas/pricing_admin.py. Field
// names are the backend's snake_case and money is a string, matching the rest of
// this file.

export type FulfillmentMode = "ekshop" | "self" | "pickup" | "partner";

/**
 * Derived on the backend from the current job, never stored. The server is the
 * only authority on this -- recomputing it here is how a client and the database
 * end up disagreeing about whether a parcel is delivered.
 */
export type FulfillmentStatus =
  | "pending"
  | "assigned"
  | "picked_up"
  | "in_transit"
  | "delivered"
  | "collected"
  | "cancelled"
  | "returned"
  | "failed";

export type DeliveryJobType = "forward" | "retry" | "return";

export type DeliveryJobStatus =
  | "created"
  | "dispatch_requested"
  | "offered"
  | "accepted"
  | "at_pickup"
  | "picked_up"
  | "in_transit"
  | "delivered"
  | "failed"
  | "cancelled"
  | "settled"
  | "returned";

export type AssignmentStatus = "queued" | "offered" | "accepted" | "declined" | "expired" | "cancelled";

export interface JobEventRead {
  id: string;
  event_type: string;
  to_status?: string | null;
  actor_user_id?: string | null;
  actor_agent_id?: string | null;
  actor_role?: string | null;
  payload?: Record<string, unknown> | null;
  notes?: string | null;
  created_at: string;
}

export interface AssignmentRead {
  id: string;
  job_id: string;
  agent_id: string;
  wave: number;
  status: AssignmentStatus;
  payout_estimate?: string | null;
  distance_km?: string | null;
  offered_at?: string | null;
  expires_at?: string | null;
  responded_at?: string | null;
  decline_reason?: string | null;
}

export interface DeliveryJobRead {
  id: string;
  fulfillment_id: string;
  /** Safe to hand to a third-party courier; carries no internal identifiers. */
  external_reference: string;
  /** 1, 2, 3... A retry or return is a new job, never a reused one. */
  attempt: number;
  job_type: DeliveryJobType;
  status: DeliveryJobStatus;
  agent_id?: string | null;
  distance_km?: string | null;
  merchant_to_customer_km?: string | null;
  rider_to_merchant_km?: string | null;
  distance_source?: string | null;
  distance_is_approximate?: boolean;
  quoted_fee?: string | null;
  failure_code?: string | null;
  failure_reason?: string | null;
  otp_expires_at?: string | null;
  otp_verified_at?: string | null;
  override_reason?: string | null;
  created_at: string;
  dispatch_requested_at?: string | null;
  accepted_at?: string | null;
  at_pickup_at?: string | null;
  picked_up_at?: string | null;
  in_transit_at?: string | null;
  delivered_at?: string | null;
  settled_at?: string | null;
  failed_at?: string | null;
  closed_at?: string | null;
}

export interface DeliveryJobDetail extends DeliveryJobRead {
  events: JobEventRead[];
  assignments: AssignmentRead[];
}

export interface FulfillmentRead {
  id: string;
  order_id: string;
  mode: FulfillmentMode;
  status: FulfillmentStatus;
  /**
   * Subsidy split. `delivery_price_gross` is what the delivery is worth;
   * `customer_payment` is what the buyer hands over. They differ whenever a
   * merchant or Ekshop subsidy applies, and showing only the latter makes a
   * fully-subsidised delivery look like revenue of zero.
   */
  merchant_subsidy: string;
  ekshop_subsidy: string;
  delivery_price_gross?: string | null;
  customer_payment?: string | null;
  self_rider_name?: string | null;
  self_rider_phone?: string | null;
  quoted_fee?: string | null;
  close_reason?: string | null;
  created_at: string;
  confirmed_at?: string | null;
  closed_at?: string | null;
  settled_at?: string | null;
}

export interface FulfillmentSettlementRead {
  id: string;
  fulfillment_id: string;
  job_id?: string | null;
  fee_collected: string;
  rider_payout: string;
  incentive_paid: string;
  payment_fee: string;
  partner_cost: string;
  waiting_fee: string;
  contribution: string;
  margin_pct?: string | null;
  currency: string;
  settled_at?: string | null;
}

export interface FulfillmentDetail extends FulfillmentRead {
  jobs: DeliveryJobDetail[];
  settlement?: FulfillmentSettlementRead | null;
}

export interface FulfillmentListResponse {
  items: FulfillmentRead[];
  total: number;
  page: number;
  page_size: number;
}

export interface IssueOtpResponse {
  otp: string;
  expires_at: string;
}

// ── Pricing (§16 response shape) ──────────────────────────────────────────────

/**
 * HEALTHY / POSITIVE_LOW_MARGIN / LOSS_MAKING.
 * LOSS_MAKING is a recommendation, never an automatic rejection: the backend
 * deliberately does not refuse an order, it returns a decision for a person.
 */
export type PricingStatus = "HEALTHY" | "POSITIVE_LOW_MARGIN" | "LOSS_MAKING";

export type PricingAction =
  | "NORMAL"
  | "OPTIONAL_INCENTIVE"
  | "MERCHANT_SUBSIDY"
  | "BASKET_BUILDING"
  | "BATCHING"
  | "ALTERNATIVE_FULFILMENT"
  | "CUSTOMER_PAYS_ACTUAL"
  | "EKS_HOP_LOGISTICS_UNAVAILABLE"
  | "MANUAL_QUOTE";

export interface PricingDistance {
  rider_to_merchant_km: string;
  merchant_to_customer_km: string;
  total_km: string;
}

export interface PricingCustomer {
  base_price: string;
  weight_multiplier: string;
  surge_multiplier: string;
  service_multiplier: string;
  delivery_price: string;
  merchant_subsidy: string;
  ekshop_subsidy: string;
  amount_to_pay: string;
}

export interface PricingRider {
  base_fare: string;
  distance_payout: string;
  waiting_payout: string;
  chargeable_wait_minutes: string;
  total_payout: string;
}

export interface PricingProfitability {
  payment_cost: string;
  expected_exception_cost: string;
  expected_delivery_cost: string;
  delivery_contribution: string;
  contribution_pct?: string | null;
  delivery_basket_ratio: string;
  minimum_economic_price: string;
  status: PricingStatus;
}

export interface PricingResponse {
  order_id: string;
  pricing_version: string;
  /**
   * True when the distance was not a real road distance. §3.2 forbids pricing on
   * straight-line, so a quote with this set must not be presented to a customer
   * as firm.
   */
  distance_is_approximate: boolean;
  /** Over the weight where §7 defines no formula, so no price exists. */
  requires_manual_quote: boolean;
  distance: PricingDistance;
  customer: PricingCustomer;
  rider: PricingRider;
  profitability: PricingProfitability;
  recommendation: { action: PricingAction; reason: string };
  calculated_at: string;
}

export interface PricingParameterRead {
  key: string;
  value: string;
  value_type: "money" | "rate" | "integer" | "boolean" | "json";
  description?: string | null;
  spec_reference?: string | null;
  /** A commercial decision rather than a rate: these need a human, not a tweak. */
  is_commercial_decision: boolean;
  updated_at: string;
}

export interface PricingParameterListResponse {
  items: PricingParameterRead[];
  placeholder_count: number;
  pricing_version: string;
}

export interface PricingCalculationRead {
  id: string;
  order_id: string;
  fulfillment_id?: string | null;
  pricing_version: string;
  reason: string;
  customer_delivery_price: string;
  customer_amount_paid: string;
  rider_total_payout: string;
  expected_contribution: string;
  contribution_pct?: string | null;
  pricing_status: string;
  pricing_decision: string;
  distance_source?: string | null;
  distance_is_approximate: boolean;
  requires_manual_quote: boolean;
  created_at: string;
}

// Messaging
export interface Conversation {
  id: string;
  order_id: string;
  created_at: string;
  messages: Message[];
}

export interface Message {
  id: string;
  conversation_id: string;
  sender_id?: string;
  sender_type: string;
  body: string;
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
  mtd: PeriodToDateMetrics;
  ytd: PeriodToDateMetrics;
}

export interface PeriodFigures {
  revenue: string;
  orders: number;
  average_order_value: string;
  new_users: number;
  new_shops: number;
}

export interface PeriodToDateMetrics {
  start: string;
  current: PeriodFigures;
  previous: PeriodFigures;
}

export interface AdminTrendPoint {
  label: string;
  revenue: number;
  orders: number;
}

export interface CartAbandonedProduct {
  product_id: string | null;
  name: string;
  slug: string | null;
  units: number;
  at_risk_revenue: string;
}

export interface TopPurchasedProduct {
  product_id: string | null;
  name: string;
  slug: string | null;
  units: number;
  revenue: string;
}

export interface CartAbandonmentMetrics {
  carts_touched: number;
  converted_carts: number;
  abandoned_carts: number;
  cart_abandonment_rate: number;
  abandoned_units: number;
  at_risk_revenue: string;
  abandoned_products: CartAbandonedProduct[];
  top_products: TopPurchasedProduct[];
}

export interface MerchantMasterHealth {
  merchant: string;
  location: string;
  category: string;
  stage: string;
  activity: number;
  catalogue: number;
  demand: number;
  reliability: number;
  growth: number;
  health: number;
  health_tier: string;
  last_login: string | null;
  orders_30d: number;
  dispatch_hrs: number;
  cancel_pct: number;
  response_min: number;
  next_action: string;
  owner: string;
}

export interface OrderControlTowerRow {
  order_id: string;
  received: string;
  merchant: string;
  customer: string;
  ack_time: string | null;
  accepted: boolean;
  ready_time: string | null;
  rider_assigned: string | null;
  pickup_time: string | null;
  delivered_time: string | null;
  dispatch_hrs: number;
  delivery_hrs: number;
  status: string;
  exception_owner: string;
}

export interface CustomerRecoveryRow {
  customer: string;
  segment: string;
  last_activity: string | null;
  cart_value: string;
  issue_trigger: string;
  contact_date: string | null;
  channel: string;
  response: string;
  recovered_order: boolean;
  next_action: string;
}

export interface SupplyDemandRow {
  category_area: string;
  searches_views: number;
  cart_adds: number;
  orders: number;
  active_shops: number;
  products_live: number;
  demand_score: number;
  supply_score: number;
  gap: number;
  action: string;
}

export interface PriorityAcquisitionRow {
  prospect: string;
  category: string;
  area: string;
  demand_evidence: string;
  reliability_potential: string;
  strategic_value: string;
  priority_score: number;
  reason: string;
}

export interface AdminOverviewPeriodMetrics {
  revenue: string;
  orders: number;
  average_order_value: string;
  new_users: number;
  new_buyers: number;
  new_sellers: number;
  new_shops: number;
  new_products: number;
  cart_abandonment_rate: number;
}

export interface AdminOverviewTotals {
  total_users: number;
  total_buyers: number;
  total_sellers: number;
  total_shops: number;
  shops_pending_verification: number;
  total_products: number;
  total_orders: number;
  revenue_total: string;
}

export interface AdminOverview {
  period: string;
  start: string;
  metrics: AdminOverviewPeriodMetrics;
  previous: AdminOverviewPeriodMetrics;
  totals: AdminOverviewTotals;
  trend: AdminTrendPoint[];
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

export interface MarginLeakageTrendPoint {
  label: string;
  gmv: number;
  platform_commission: number;
  mpesa_fees: number;
  net_profit: number;
  gross_margin_pct: number;
  aov: number;
}

export interface MarginLeakageMetrics {
  period: string;
  start: string;
  end: string;
  gmv: string;
  orders: number;
  average_order_value: string;
  platform_commission: string;
  mpesa_fees: string;
  server_cost: string;
  net_profit: string;
  gross_margin_pct: number;
  commission_rate_pct: number;
  mpesa_rate_pct: number;
  trend: MarginLeakageTrendPoint[];
}

export interface RealTimeMetrics {
  active_sessions: number;
  active_users: number;
  recent_purchases: number;
  active_carts: number;
}

export interface AcquisitionMetrics {
  new_users: number;
  returning_buyers: number;
  new_user_rate: number;
  returning_user_rate: number;
  total_users_in_period: number;
}

export interface BehaviorMetrics {
  views: number;
  clicks: number;
  add_to_carts: number;
  purchases: number;
  view_to_click_rate: number;
  click_to_cart_rate: number;
  cart_to_purchase_rate: number;
  overall_conversion_rate: number;
}

export interface EcommerceMetrics {
  transactions: number;
  revenue: string;
  average_order_value: string;
  conversion_rate: number;
  revenue_per_session: string;
  top_products: TopPurchasedProduct[];
}

export interface TopMerchantInsight {
  name: string;
  orders: number;
  revenue: string;
}

export interface ChurnRiskInsight {
  first_name: string;
  last_name: string;
  email: string;
  last_order_at: string | null;
}

export interface OrderNotificationRecipient {
  id: string;
  email: string;
  label?: string;
  is_active: boolean;
  created_at: string;
}

export interface AdminEmailStatus {
  resend_configured: boolean;
  from_address: string;
  from_domain: string;
  verified_domains: string[];
  from_domain_verified: boolean;
  domains_error?: string | null;
  active_recipient_count: number;
}

export interface AdminEmailTestResult {
  success: boolean;
  detail: string;
}

export interface RecentOrderRow {
  id: string;
  short_id: string;
  created_at: string;
  buyer_name: string;
  total: string;
  item_count: number;
  shop_count: number;
}

export interface RecentOrderListResponse {
  total: number;
  page: number;
  limit: number;
  results: RecentOrderRow[];
}

export interface AdminProductRow {
  id: string;
  name: string;
  price: string;
  status: string;
  shop_name?: string | null;
  created_at: string;
}

export interface AdminProductListResponse {
  total: number;
  page: number;
  limit: number;
  results: AdminProductRow[];
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
  lat?: number;
  lng?: number;
  sublocation?: string;
}

export interface ReverseGeocodeResult {
  lat: number;
  lng: number;
  county: string;
  subcounty: string;
  ward: string;
  location?: string | null;
  sublocation?: string | null;
  address_hint: string;
  county_id?: string | null;
  subcounty_id?: string | null;
  ward_id?: string | null;
}

export interface GeoSearchResult {
  type: "ward" | "location" | "subcounty" | "sublocation";
  name: string;
  subtitle: string;
  lat: number;
  lng: number;
  county?: string | null;
  subcounty?: string | null;
  ward?: string | null;
  location?: string | null;
  sublocation?: string | null;
}

export interface GeoSelection {
  lat: number;
  lng: number;
  county: string;
  subcounty: string;
  ward: string;
  location?: string | null;
  sublocation?: string | null;
  addressHint: string;
  countyId?: string | null;
  subcountyId?: string | null;
  wardId?: string | null;
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
