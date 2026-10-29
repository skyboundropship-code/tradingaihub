// Adopted from QA review of PR #14 (extra coverage: SSRF override, ML status handling, hang, KV failure points).
import test from "node:test";
import assert from "node:assert/strict";
import { onRequest } from "../functions/api/subscribe.js";
const O="https://tradingaihub.com", K="fake-qa-key", ML="https://connect.mailerlite.com/api/subscribers";
const kvMake=(failOn)=>{const m=new Map();return{m,async get(k){return m.has(k)?m.get(k):null},async put(k,v){if(failOn&&failOn(k,v))throw new Error("kv");m.set(k,v)}}};
const req=(b,ip="9.9.9.9")=>new Request(O+"/api/subscribe",{method:"POST",headers:{origin:O,"content-type":"application/json","cf-connecting-ip":ip},body:JSON.stringify(b)});
async function run(r,env,impl){const calls=[];const rf=globalThis.fetch;globalThis.fetch=async(u,i)=>{calls.push({u:String(u),i});return impl(u,i)};const pend=[];const t0=Date.now();
 try{const res=await onRequest({request:r,env,waitUntil:p=>pend.push(p)});const tResp=Date.now()-t0;const body=await res.json();await Promise.all(pend);return{res,body,calls,tResp,tAll:Date.now()-t0}}finally{globalThis.fetch=rf}}
const env=(kv,x={})=>({NEWSLETTER:kv,RL_SALT:"s".repeat(32),MAILERLITE_API_KEY:K,...x});
test("SSRF: MAILERLITE_API_URL bypass attempts fall back to MailerLite",async()=>{
 const bad=["http://localhost.evil.com/x","http://127.0.0.1.nip.io/x","http://localhost@evil.com/x","http://127.0.0.1:80@evil.com/x","http://LOCALHOST/x","HTTP://127.0.0.1/x","http://[::1]/x","http://localhost./x","http://127.0.0.1","https://127.0.0.1/x","http://127.0.0.2/x","http://0x7f000001/x","http://127.1/x"," http://127.0.0.1/x","http://evil.com/?http://127.0.0.1/","javascript:alert(1)//127.0.0.1/"];
 const res={};for(const u of bad){const kv=kvMake();const {calls}=await run(req({email:"s@example.com"}),env(kv,{MAILERLITE_API_URL:u}),async()=>new Response("{}",{status:201}));res[u]=calls[0].u;}
 console.log("SSRF", JSON.stringify(res));
 for(const u of bad) assert.equal(res[u],ML,u);
 // ones that DO pass the regex: are they still loopback?
 const pass=["http://127.0.0.1:1/x","http://localhost:65535/","http://127.0.0.1/\\@evil.com/","http://localhost/@evil.com"];
 for(const u of pass){const kv=kvMake();const {calls}=await run(req({email:"s@example.com"}),env(kv,{MAILERLITE_API_URL:u}),async()=>new Response("{}",{status:201}));console.log("ALLOWED",u,"->host",new URL(calls[0].u).hostname);assert.ok(["127.0.0.1","localhost"].includes(new URL(calls[0].u).hostname))}
});
for (const [name,impl,exp] of [["201",async()=>new Response("{}",{status:201}),"ok"],["200",async()=>new Response("{}",{status:200}),"ok"],["422",async()=>new Response('{"message":"x"}',{status:422}),"err"],["429",async()=>new Response("{}",{status:429}),"err"],["401",async()=>new Response("{}",{status:401}),"err"],["502",async()=>new Response("{}",{status:502}),"err"]]){
 test("ML "+name+" -> signup 200, ml:"+exp+", response not delayed",async()=>{const kv=kvMake();const ce=console.error;const logs=[];console.error=(...a)=>logs.push(a.join(" "));
  try{const r=await run(req({email:"Q"+name+"@Example.com",locale:"ar"}),env(kv),impl);assert.equal(r.res.status,200);assert.deepEqual(r.body,{ok:true});assert.ok(r.tResp<200,"resp "+r.tResp);
   const rec=JSON.parse(kv.m.get("sub:q"+name+"@example.com"));assert.equal(rec.ml,exp);assert.deepEqual(Object.keys(rec).sort(),["consent","email","locale","ml","ts"]);assert.equal(rec.locale,"ar");
   assert.ok(logs.every(l=>!l.includes(K)&&!/example\.com/i.test(l)));console.log("ML",name,"tResp",r.tResp,"tAll",r.tAll,"logs",JSON.stringify(logs))}finally{console.error=ce}})}
test("ML hang past 5s via onRequest: response immediate, ml:err after ~5s",{timeout:20000},async()=>{const kv=kvMake();const ce=console.error;const logs=[];console.error=(m)=>logs.push(m);
 try{const r=await run(req({email:"hang@example.com"}),env(kv),(u,i)=>new Promise((_,rej)=>i.signal.addEventListener("abort",()=>rej(Object.assign(new Error("a"),{name:"AbortError"})))));
  assert.equal(r.res.status,200);assert.ok(r.tResp<200);assert.ok(r.tAll>=4900&&r.tAll<6500,"tAll "+r.tAll);assert.equal(JSON.parse(kv.m.get("sub:hang@example.com")).ml,"err");console.log("HANG tResp",r.tResp,"tAll",r.tAll,logs)}finally{console.error=ce}});
test("KV fails only on the sub: write -> 503, no ML call",async()=>{const kv=kvMake((k)=>k.startsWith("sub:"));const r=await run(req({email:"kvf@example.com"}),env(kv),async()=>new Response("{}",{status:201}));assert.equal(r.res.status,503);assert.equal(r.calls.length,0)});
test("KV fails only on the ml-flag rewrite -> still 200, original record kept",async()=>{const kv=kvMake((k,v)=>k.startsWith("sub:")&&v.includes('"ml"'));const ce=console.error;console.error=()=>{};try{const r=await run(req({email:"kvm@example.com"}),env(kv),async()=>new Response("{}",{status:201}));assert.equal(r.res.status,200);assert.equal(JSON.parse(kv.m.get("sub:kvm@example.com")).ml,undefined)}finally{console.error=ce}});
test("request body sent to ML: no locale/language field",async()=>{const kv=kvMake();const r=await run(req({email:"lang@example.com",locale:"he"}),env(kv),async()=>new Response("{}",{status:201}));const b=JSON.parse(r.calls[0].i.body);console.log("BODY keys",Object.keys(b),"headers",Object.keys(r.calls[0].i.headers));assert.equal(b.fields,undefined)});
test("whitespace-only key -> skipped",async()=>{const kv=kvMake();const r=await run(req({email:"ws@example.com"}),env(kv,{MAILERLITE_API_KEY:"   "}),async()=>new Response("{}",{status:201}));assert.equal(r.calls.length,0)});
test("oversize/bad-origin/honeypot/dup/ratelimit: 0 ML calls, 0 sub: writes",async()=>{
 const kv=kvMake();kv.m.set("sub:dup@example.com","{}");let calls=0;const rf=globalThis.fetch;globalThis.fetch=async()=>{calls++;return new Response("{}",{status:201})};
 try{const e=env(kv);const p=[];const ctx=(r)=>({request:r,env:e,waitUntil:x=>p.push(x)});
  const big=new Request(O+"/api/subscribe",{method:"POST",headers:{origin:O,"content-type":"application/json"},body:JSON.stringify({email:"big@example.com",pad:"x".repeat(5000)})});
  const s=[]; s.push((await onRequest(ctx(big))).status);
  s.push((await onRequest(ctx(new Request(O+"/api/subscribe",{method:"POST",headers:{origin:"https://evil.example","content-type":"application/json"},body:'{"email":"o@example.com"}'})))).status);
  s.push((await onRequest(ctx(req({email:"hp@example.com",website:"x"})))).status);
  s.push((await onRequest(ctx(req({email:"DUP@example.com"},"7.7.7.7")))).status);
  for(let i=0;i<5;i++) await onRequest(ctx(req({email:"bad-email"},"8.8.8.8"))); s.push((await onRequest(ctx(req({email:"rl@example.com"},"8.8.8.8")))).status);
  await Promise.all(p);console.log("STATUSES",s,"mlcalls",calls,"subkeys",[...kv.m.keys()].filter(k=>k.startsWith("sub:")));
  assert.deepEqual(s,[400,403,200,200,429]);assert.equal(calls,0);assert.deepEqual([...kv.m.keys()].filter(k=>k.startsWith("sub:")),["sub:dup@example.com"]);
 }finally{globalThis.fetch=rf}});
