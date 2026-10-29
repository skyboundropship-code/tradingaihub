import re, sys, os, time, urllib.request, urllib.parse, concurrent.futures as cf, threading, html
# CRAWL_BASE overrides the target (e.g. a local preview server for testing); only that host is then crawled.
BASE=os.environ.get("CRAWL_BASE","https://tradingaihub.com").rstrip("/")
HOSTS={"tradingaihub.com","www.tradingaihub.com"} if "CRAWL_BASE" not in os.environ else {urllib.parse.urlparse(BASE).netloc}
def env_num(name, default):
    raw=os.environ.get(name, default)
    try: v=float(raw)
    except ValueError: v=None
    if v is None or not (v>=0) or v==float("inf"):  # rejects non-numeric, NaN, negative and inf
        print(f"FATAL: {name} must be a non-negative number of seconds, got {raw!r}",file=sys.stderr); sys.exit(2)
    return v
RETRY_DELAY=env_num("CRAWL_RETRY_DELAY","2")  # one retry for timeouts/network errors/5xx before counting as broken
TIMEOUT=env_num("CRAWL_TIMEOUT","30")
if TIMEOUT==0: print("FATAL: CRAWL_TIMEOUT must be greater than 0",file=sys.stderr); sys.exit(2)
seen=set(); res={}; lock=threading.Lock(); refs={}
ATTR=re.compile(r'''(?:href|src)\s*=\s*["']([^"']+)["']''',re.I)
META=re.compile(r'''<meta[^>]+(?:property|name)="(?:og:image|twitter:image|og:url)"[^>]+content="([^"]+)"''',re.I)
SRCSET=re.compile(r'''srcset\s*=\s*["']([^"']+)["']''',re.I)
cats_bad=[]
def norm(u, page):
    u=html.unescape(u).strip()
    if u.startswith(('mailto:','tel:','javascript:','data:','#')): return None
    full=urllib.parse.urljoin(page,u)
    pu=urllib.parse.urlparse(full)
    if pu.scheme not in('http','https'): return None
    if pu.netloc not in HOSTS: return None
    return urllib.parse.urlunparse((pu.scheme,pu.netloc,pu.path,'',pu.query,''))
def fetch_once(u):
    req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0 (QA crawler; Googlebot-compatible) TradingAIHubQA"})
    try:
        with urllib.request.urlopen(req,timeout=TIMEOUT) as r:
            ct=r.headers.get('content-type',''); body=r.read() if 'html' in ct or u.endswith(('.xml','.txt')) else b''
            return r.status,ct,body
    except urllib.error.HTTPError as e: return e.code,'',b''
    except Exception as e: return 599,str(e),b''
retried=[]
def fetch(u):
    st,ct,body=fetch_once(u)
    if st>=500:  # 5xx, or 599 = timeout/connection error: retry once after a short pause
        time.sleep(RETRY_DELAY); first=st
        st,ct,body=fetch_once(u)
        with lock: retried.append((u,first,st))
    return st,ct,body
def work(u):
    st,ct,body=fetch(u); out=[]
    if body:
        t=body.decode('utf8','replace')
        if re.search(r'/categories/[a-z0-9]',t): cats_bad.append(u)
        cands=ATTR.findall(t)+META.findall(t)
        for s in SRCSET.findall(t): cands+= [x.strip().split(' ')[0] for x in s.split(',')]
        if u.endswith('.xml'): cands+=re.findall(r'<loc>([^<]+)</loc>',t)+re.findall(r'href="([^"]+)"',t)
        for c in cands:
            n=norm(c,u)
            if n: out.append(n)
    return u,st,out
start=[BASE+"/",BASE+"/sitemap.xml",BASE+"/sitemap-index.xml",BASE+"/robots.txt",BASE+"/404.html"]
frontier=start[:]; seen.update(frontier)
try:
    with cf.ThreadPoolExecutor(24) as ex:
        while frontier:
            nxt=[]
            for u,st,out in ex.map(work,frontier):
                res[u]=st
                for n in out:
                    refs.setdefault(n,u)
                    if n not in seen: seen.add(n); nxt.append(n)
            frontier=nxt; print("level done, total",len(seen),file=sys.stderr)
except Exception as e:
    # Crawl aborted: results are incomplete, so never report success.
    print("FATAL: crawl aborted:",repr(e),file=sys.stderr); sys.exit(2)
if not res or res.get(BASE+"/")!=200:
    print("FATAL: home page not reachable (status",res.get(BASE+"/"),")",file=sys.stderr); sys.exit(2)
bad={u:s for u,s in res.items() if s>=400 and not u.endswith('/404.html')}
print("URLs checked:",len(res)); print("broken:",len(bad))
for u,s in list(bad.items())[:50]: print(s,u,"<-",refs.get(u))
print("pages containing /categories/:",len(cats_bad), cats_bad[:5])
print("404.html status:",res.get(BASE+"/404.html"))
print("retried (timeout/5xx):",len(retried),"recovered:",sum(1 for _,_,s in retried if s<400))
for u,a,b in retried[:20]: print("  retry",a,"->",b,u)
# Exit status for CI: 0 = clean, 1 = broken links found, 2 = fatal (crawl aborted / home unreachable).
sys.exit(1 if bad else 0)
