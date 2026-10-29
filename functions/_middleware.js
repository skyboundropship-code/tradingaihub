// Host guard for non-production hosts (e.g. v2.tradingaihub.com, *.pages.dev previews).
// On tradingaihub.com / www.tradingaihub.com this is a pure pass-through, so merging this file
// into main can never noindex production. On any other host it:
//   - serves robots.txt with "Disallow: /"
//   - adds X-Robots-Tag: noindex, nofollow to every response
//   - injects <meta name="robots" content="noindex, nofollow"> into HTML pages
// Canonical tags are already absolute (https://tradingaihub.com/...) via SITE.url, so they are untouched.
const PROD_HOSTS = new Set(["tradingaihub.com", "www.tradingaihub.com"]);

function isProdHost(host) {
  return PROD_HOSTS.has(String(host || "").toLowerCase().replace(/\.$/, "").replace(/:\d+$/, ""));
}

export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);
  if (isProdHost(url.hostname)) return context.next();

  if (url.pathname === "/robots.txt") {
    return new Response("User-agent: *\nDisallow: /\n", {
      headers: {
        "content-type": "text/plain; charset=utf-8",
        "x-robots-tag": "noindex, nofollow",
        "cache-control": "no-store",
      },
    });
  }

  const res = await context.next();
  const out = new Response(res.body, res);
  out.headers.set("X-Robots-Tag", "noindex, nofollow");
  const ct = out.headers.get("content-type") || "";
  if (!ct.includes("text/html")) return out;
  return new HTMLRewriter()
    .on('meta[name="robots"]', { element(el) { el.remove(); } })
    .on("head", {
      element(el) { el.prepend('<meta name="robots" content="noindex, nofollow">', { html: true }); },
    })
    .transform(out);
}
