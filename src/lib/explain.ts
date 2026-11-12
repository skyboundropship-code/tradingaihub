// Badge explanations: one short, factual sentence per badge, built from the tool's data (src/components/Xp*.astro).
// Values (dates, day counts, commit dates, prices) are HTML-escaped and wrapped in <bdi dir="ltr"> so they stay intact in
// RTL locales; the locale strings (i18n "xp.*") may contain <bdi dir="ltr"> around Latin terms in he/ar only.
import { useT } from "../i18n";
import { useProvT } from "../i18n/prov";
import { securityOf, starsOf, fmtStars, lastCommit } from "./data";
import { REGISTRY_LABEL } from "./provenance";

export const XP_KEYS = ["type", "official", "status", "checked", "scan", "secnote", "prov", "pricing", "stars"] as const;
export type XpKey = (typeof XP_KEYS)[number];
const esc = (s: any) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const v = (s: any) => `<bdi dir="ltr">${esc(s)}</bdi>`;

/** Explanation HTML for one badge of a tool, or null when the badge is not shown. */
export function explain(tool: any, k: XpKey, lang = "en"): string | null {
  const { t } = useT(lang);
  const ver = tool.verification || {};
  const checked = v(ver.checked_at);
  switch (k) {
    case "type": return t(`xp.type_${tool.type}`);
    case "official": return tool.official ? t("xp.official") : null;
    case "status": {
      const st = ver.status; const commit = lastCommit(tool);
      let s: string;
      if (st === "verified") s = commit ? t("xp.verified", { checked, commit: v(commit) }) : t("xp.verifiedNoRepo", { checked });
      else if (st === "aging" || st === "stale") s = t(`xp.${st}`, { checked, days: v(ver.last_commit_days ?? "?"), commit: v(commit ?? "?") });
      else s = t(`xp.${st}`, { checked });
      if (ver.manual_override && ver.manual_check?.date) s += " " + t("xp.manual", { date: v(ver.manual_check.date) });
      return s;
    }
    case "checked": return t("xp.checked");
    case "scan": { const sc = securityOf(tool); return sc ? t("xp.scan", { date: v(sc.date), commit: v(sc.scanner_commit.slice(0, 7)), rules: v(sc.rules_version) }) : null; }
    case "secnote": return tool.security_note ? `<strong>${esc(t("secnote.label"))}.</strong> ${t("secnote.text")}` : null;
    case "prov": {
      const pv = ver.provenance;
      if (!tool.repo || !pv) return null;
      const pt = useProvT(lang);
      const reg = pv.registry ? (REGISTRY_LABEL[pv.registry] ?? pv.registry) : "npm/PyPI";
      return `<strong>${esc(pt(`label.${pv.state}`))}.</strong> ${esc(pt(`tip.${pv.state}`, { registry: reg, name: pv.package ?? "", repo: pv.declared_repo ?? "", date: pv.checked_at ?? "" }))}`;
    }
    case "pricing": {
      const p = tool.pricing || {};
      if (!p.free_tier || p.free_tier === "unknown") return t("xp.pricingUnknown");
      const vars = { free: v(p.free_tier), paid: v(p.paid_from ?? "—"), date: v(p.checked) };
      return p.checked ? t("xp.pricing", vars) : t("xp.pricingNoDate", vars);
    }
    case "stars": { const s = starsOf(tool); return s == null ? null : t("xp.stars", { stars: v(fmtStars(s)), checked }); }
  }
  return null;
}
