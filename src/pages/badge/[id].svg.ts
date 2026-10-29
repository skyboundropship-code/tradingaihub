import { SITE } from "../../config";
import { tools, STATUS } from "../../lib/data";
export function getStaticPaths() { return tools.map((t) => ({ params: { id: t.id }, props: { t } })); }
// White text on these is >= 4.5:1 (WCAG AA): green-700 5.02, amber-700 5.02, red-700 6.47.
const COL: Record<string, string> = { good: "#15803d", warn: "#b45309", bad: "#b91c1c" };
export function GET({ props }: any) {
  const st = STATUS[props.t.verification.status]; const left = SITE.name; const right = `${st.tone === "good" ? "✓ " : ""}${st.label} ${props.t.verification.checked_at}`;
  const w = (s: string) => Math.round(s.length * 6.6 + 16); const lw = w(left), rw = w(right);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${lw + rw}" height="22" role="img" aria-label="${left}: ${right}"><title>${left}: ${right}</title><rect width="${lw}" height="22" rx="4" fill="#0b0f17"/><rect x="${lw}" width="${rw}" height="22" rx="4" fill="${COL[st.tone]}"/><rect x="${lw - 4}" width="8" height="22" fill="${COL[st.tone]}"/><g fill="#fff" font-family="Verdana,DejaVu Sans,sans-serif" font-size="11"><text x="8" y="15">${left}</text><text x="${lw + 8}" y="15">${right}</text></g></svg>`;
  return new Response(svg, { headers: { "content-type": "image/svg+xml" } });
}
