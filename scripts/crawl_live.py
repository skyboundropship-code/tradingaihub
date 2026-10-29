import re, sys, urllib.request, urllib.parse, concurrent.futures as cf, threading, html
BASE="https://tradingaihub.com"
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
    if pu.netloc not in('tradingaihub.com','www.tradingaihub.com'): return None
    return urllib.parse.urlunparse((pu.scheme,pu.netloc,pu.path,'',pu.query,''))
def fetch(u):
    req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0 (QA crawler; Googlebot-compatible) TradingAIHubQA"})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            ct=r.headers.get('content-type',''); body=r.read() if 'html' in ct or u.endswith(('.xml','.txt')) else b''
            return r.status,ct,body
    except urllib.error.HTTPError as e: return e.code,'',b''
    except Exception as e: return 599,str(e),b''
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
with cf.ThreadPoolExecutor(24) as ex:
    while frontier:
        nxt=[]
        for u,st,out in ex.map(work,frontier):
            res[u]=st
            for n in out:
                refs.setdefault(n,u)
                if n not in seen: seen.add(n); nxt.append(n)
        frontier=nxt; print("level done, total",len(seen),file=sys.stderr)
bad={u:s for u,s in res.items() if s>=400 and not u.endswith('/404.html')}
print("URLs checked:",len(res)); print("broken:",len(bad))
for u,s in list(bad.items())[:50]: print(s,u,"<-",refs.get(u))
print("pages containing /categories/:",len(cats_bad), cats_bad[:5])
print("404.html status:",res.get(BASE+"/404.html"))
