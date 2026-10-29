import requests, sys, json, subprocess, concurrent.futures as cf
names = sys.argv[1:]
def rdap(d):
    tld = d.rsplit('.',1)[1]
    url = {"com":f"https://rdap.verisign.com/com/v1/domain/{d}"}.get(tld, f"https://rdap.org/domain/{d}")
    try:
        r = requests.get(url, timeout=20, allow_redirects=True, headers={"Accept":"application/rdap+json"})
        if r.status_code == 404: return d, "AVAILABLE (RDAP 404)"
        if r.status_code == 200: return d, "taken"
        res = f"rdap {r.status_code}"
    except Exception as e: res = f"rdap err {type(e).__name__}"
    try:
        w = subprocess.run(["whois", d], capture_output=True, text=True, timeout=25).stdout
        if any(s in w.lower() for s in ["no match", "not found", "no data found", "no object found", "domain not found", "available"]): return d, "AVAILABLE (whois)"
        if "creation date" in w.lower() or "registrar:" in w.lower(): return d, "taken (whois)"
        return d, res + " / whois unclear"
    except Exception as e: return d, res + " / no whois"
with cf.ThreadPoolExecutor(8) as ex:
    for d, s in ex.map(rdap, names): print(f"{d:28} {s}")
