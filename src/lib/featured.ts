// Paid placement products shown on /get-featured/. Single source of truth for prices and checkout links.
// Checkout is hosted by Polar (merchant of record). Going live / pausing a product is a one-line change:
// set `url` to the Polar checkout link and `pending: false`; with `url: null` (pending) the card falls back
// to a mailto: to SITE.contactEmail with a subject naming the product.
// Copy for each product lives in src/i18n/<lang>.json under `feat.products.<id>` (name, what, bullets).
export interface FeaturedProduct {
  id: "category" | "homepage";
  /** Price in USD per billing period; Polar adds tax (VAT / sales tax) at checkout. */
  price: number;
  currency: "USD";
  interval: "month";
  /** Max concurrent buyers (per category for `category`, site-wide for `homepage`). */
  slots: number;
  url: string | null;
  pending: boolean;
}
export const FEATURED_PRODUCTS: FeaturedProduct[] = [
  { id: "category", price: 29, currency: "USD", interval: "month", slots: 3, url: "https://buy.polar.sh/polar_cl_1eoI1ZkzYOvLpL8z5JRWY3JkhFUd3GgY2LVlO4S3mwT", pending: false },
  { id: "homepage", price: 99, currency: "USD", interval: "month", slots: 2, url: "https://buy.polar.sh/polar_cl_lD7Z9qQWMnKNWqcNu1KK62ekcsLObntdqxyHz0Ak5Oe", pending: false },
];
/** Checkout href for a product: the Polar link when live, otherwise a mailto fallback naming the product. */
export const checkoutHref = (prod: FeaturedProduct, email: string, productName: string) =>
  !prod.pending && prod.url ? prod.url : `mailto:${email}?subject=${encodeURIComponent(`Get featured: ${productName}`)}`;
