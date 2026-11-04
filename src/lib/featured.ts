// Paid placement products shown on /get-featured/ and /advertise/. Single source of truth for prices and checkout links.
// Checkout is hosted by Polar (merchant of record). Only products with a live Polar `url` are rendered.
// Copy for each product lives in src/i18n/<lang>.json under `feat.products.<id>` (name, what, bullets).
export interface FeaturedProduct {
  id: "category" | "homepage";
  /** Price in USD per billing period; Polar adds tax (VAT / sales tax) at checkout. */
  price: number;
  currency: "USD";
  interval: "month";
  /** Max concurrent buyers (per category for `category`, site-wide for `homepage`). */
  slots: number;
  url: string;
}
export const FEATURED_PRODUCTS: FeaturedProduct[] = [
  { id: "category", price: 29, currency: "USD", interval: "month", slots: 3, url: "https://buy.polar.sh/polar_cl_1eoI1ZkzYOvLpL8z5JRWY3JkhFUd3GgY2LVlO4S3mwT" },
  { id: "homepage", price: 99, currency: "USD", interval: "month", slots: 2, url: "https://buy.polar.sh/polar_cl_lD7Z9qQWMnKNWqcNu1KK62ekcsLObntdqxyHz0Ak5Oe" },
];
