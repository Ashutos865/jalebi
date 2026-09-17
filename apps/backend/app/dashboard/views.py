"""Founder/editor dashboard + admin panel.

Served as one self-contained HTML page (inline CSS/JS, no build step, no external
requests) so it runs anywhere the backend runs. It authenticates via the API (dev
login or a pasted token) and calls the JSON endpoints — the same auth as everything
else, no server-side session.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_PAGE = r"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Jalebi — Editorial Dashboard</title>
<style>
:root{--jalebi:#ff9933;--jalebi600:#e67e00;--ink:#18181b;--soft:#6b7280;--line:#e5e7eb;--bg:#faf9f7;--card:#fff}
@media(prefers-color-scheme:dark){:root{--ink:#f4f4f5;--soft:#a1a1aa;--line:#27272a;--bg:#0f1015;--card:#17181d}}
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,system-ui,sans-serif;color:var(--ink);background:var(--bg)}
header{display:flex;align-items:center;gap:12px;padding:14px 22px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:5}
.logo{width:34px;height:34px;border-radius:10px;background:#fff;display:grid;place-items:center;box-shadow:0 1px 5px rgba(0,0,0,.15)}
h1{font-size:16px;margin:0}.sub{color:var(--soft);font-size:11px}
main{max-width:1100px;margin:0 auto;padding:22px}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:18px}
.tab{padding:7px 14px;border-radius:9px;border:1px solid var(--line);background:var(--card);cursor:pointer;font-size:13px;font-weight:600}
.tab.active{background:var(--jalebi);color:#fff;border-color:var(--jalebi)}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(200px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}
.kpi{font-size:30px;font-weight:800;color:var(--jalebi600)}
.klabel{color:var(--soft);font-size:11px;text-transform:uppercase;letter-spacing:.05em}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line)}
th{color:var(--soft);font-size:11px;text-transform:uppercase}
.bar{height:8px;border-radius:5px;background:var(--jalebi)}
.barbg{background:var(--line);border-radius:5px;overflow:hidden;flex:1}
.row{display:flex;align-items:center;gap:10px}
input,select,textarea,button{font:inherit;padding:8px 10px;border-radius:9px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
button{background:var(--jalebi);color:#fff;border:0;font-weight:700;cursor:pointer}
button.ghost{background:transparent;color:var(--ink);border:1px solid var(--line)}
.pill{padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700;background:rgba(255,153,51,.15);color:var(--jalebi600)}
.hidden{display:none}.muted{color:var(--soft)}h2{font-size:14px;margin:0 0 12px}
.loginwrap{max-width:420px;margin:60px auto;text-align:center}
.stack{display:flex;flex-direction:column;gap:10px}
small.err{color:#e11d48}
</style></head><body>
<header><div class=logo id=slogo></div><div><h1>Jalebi</h1><div class=sub>Editorial Dashboard · TIES</div></div>
<div style=margin-left:auto class=row><span id=whoami class=muted></span><button class=ghost id=logout>Sign out</button></div></header>
<main>
<div id=login class=loginwrap>
  <div class=card>
    <h2>Sign in</h2>
    <div class=stack>
      <input id=email placeholder="you@ties.org" value="">
      <input id=secret type=password placeholder="shared secret (if required)">
      <button id=devbtn>Sign in</button>
      <div class=muted style=font-size:12px>or paste an access token</div>
      <textarea id=token placeholder="access token" rows=3></textarea>
      <button class=ghost id=tokbtn>Use token</button>
      <small class=err id=loginerr></small>
    </div>
  </div>
</div>

<div id=app class=hidden>
  <div class=tabs id=tabs></div>
  <div id=view></div>
</div>
</main>
<script>
const SPIRAL="M 51.45 48.85 L 51.67 48.88 L 51.9 48.94 L 52.13 49.03 L 52.36 49.15 L 52.58 49.3 L 52.79 49.48 L 52.99 49.69 L 53.17 49.93 L 53.34 50.2 L 53.47 50.49 L 53.58 50.81 L 53.67 51.14 L 53.72 51.5 L 53.73 51.87 L 53.71 52.25 L 53.65 52.64 L 53.55 53.04 L 53.41 53.43 L 53.23 53.83 L 53.0 54.21 L 52.74 54.58 L 52.43 54.94 L 52.08 55.27 L 51.7 55.58 L 51.27 55.87 L 50.81 56.11 L 50.33 56.33 L 49.81 56.5 L 49.26 56.63 L 48.7 56.71 L 48.11 56.74 L 47.51 56.72 L 46.91 56.65 L 46.3 56.52 L 45.69 56.34 L 45.08 56.1 L 44.49 55.8 L 43.92 55.44 L 43.36 55.03 L 42.84 54.57 L 42.34 54.05 L 41.89 53.48 L 41.47 52.87 L 41.11 52.21 L 40.79 51.5 L 40.54 50.77 L 40.34 50.0 L 40.21 49.2 L 40.14 48.38 L 40.14 47.55 L 40.21 46.71 L 40.36 45.86 L 40.58 45.01 L 40.88 44.18 L 41.24 43.36 L 41.69 42.56 L 42.2 41.79 L 42.79 41.05 L 43.45 40.36 L 44.17 39.72 L 44.95 39.13 L 45.79 38.6 L 46.68 38.13 L 47.62 37.74 L 48.61 37.42 L 49.62 37.18 L 50.67 37.03 L 51.74 36.96 L 52.83 36.98 L 53.92 37.1 L 55.02 37.3 L 56.1 37.6 L 57.17 37.99 L 58.22 38.48 L 59.23 39.06 L 60.21 39.72 L 61.13 40.48 L 62.0 41.31 L 62.81 42.23 L 63.54 43.22 L 64.2 44.27 L 64.78 45.39 L 65.27 46.57 L 65.66 47.79 L 65.95 49.06 L 66.14 50.36 L 66.23 51.68 L 66.2 53.02 L 66.06 54.37 L 65.81 55.71 L 65.45 57.05 L 64.97 58.36 L 64.38 59.63 L 63.68 60.87 L 62.88 62.06 L 61.97 63.18 L 60.97 64.24 L 59.87 65.22 L 58.68 66.12 L 57.41 66.92 L 56.07 67.62 L 54.66 68.22 L 53.2 68.7 L 51.69 69.07 L 50.14 69.31 L 48.56 69.42 L 46.97 69.4 L 45.37 69.26 L 43.77 68.97 L 42.19 68.56 L 40.63 68.01 L 39.12 67.34 L 37.65 66.53 L 36.24 65.6 L 34.9 64.55 L 33.64 63.38 L 32.47 62.11 L 31.41 60.73 L 30.45 59.26 L 29.61 57.7 L 28.89 56.07 L 28.3 54.37 L 27.86 52.62 L 27.55 50.82 L 27.39 49.0 L 27.38 47.15 L 27.52 45.29 L 27.82 43.44 L 28.27 41.6 L 28.87 39.79 L 29.63 38.03 L 30.53 36.32 L 31.57 34.69 L 32.75 33.13 L 34.07 31.66 L 35.51 30.29 L 37.07 29.04 L 38.73 27.92 L 40.49 26.92 L 42.34 26.07 L 44.27 25.36 L 46.26 24.82 L 48.3 24.43 L 50.38 24.21 L 52.49 24.16 L 54.6 24.28 L 56.71 24.58 L 58.81 25.05 L 60.87 25.7 L 62.88 26.51 L 64.83 27.49 L 66.71 28.64 L 68.5 29.94 L 70.19 31.39 L 71.76 32.99 L 73.21 34.71 L 74.51 36.57 L 75.67 38.53 L 76.68 40.59 L 77.51 42.74 L 78.17 44.96 L 78.65 47.25 L 78.95 49.58 L 79.05 51.93 L 78.97 54.31 L 78.68 56.68 L 78.21 59.03 L 77.54 61.35 L 76.67 63.62 L 75.62 65.82 L 74.39 67.95 L 72.98 69.97 L 71.4 71.89 L 69.67 73.68 L 67.78 75.33 L 65.75 76.83 L 63.6 78.17 L 61.33 79.33 L 58.96 80.31 L 56.51 81.1 L 53.99 81.69 L 51.42 82.08 L 48.81 82.26 L 46.18 82.22 L 43.55 81.96 L 40.93 81.5 L 38.35 80.81 L 35.82 79.92 L 33.36 78.82 L 30.99 77.51 L 28.71 76.01 L 26.56 74.32 L 24.54 72.45 L 22.67 70.41 L 20.97 68.22 L 19.44 65.88 L 18.1 63.42 L 16.96 60.84 L 16.03 58.17 L 15.32 55.41 L 14.83 52.6 L 14.56 49.74 L 14.54 46.85 L 14.74 43.96 L 15.19 41.08 L 15.87 38.24 L 16.78 35.44 L 17.92 32.72 L 19.29 30.09 L 20.87 27.56 L 22.66 25.16 L 24.65 22.91 L 26.83 20.81 L 29.18 18.89 L 31.68 17.16 L 34.34 15.64 L 37.12 14.32 L 40.01 13.24 L 42.99 12.38 L 46.04 11.77 L 49.15 11.41 L 52.29 11.3 L 55.44 11.45 L 58.58 11.86 L 61.69 12.52 L 64.75 13.44 L 67.74 14.6 L 70.64 16.02 L 73.42 17.66 L 76.07 19.54 L 78.57 21.64 L 80.9 23.94 L 83.05 26.43 L 84.99 29.1 L 86.72 31.93 L 88.22 34.91 L 89.48 38.01 L 90.48 41.21 L 91.22 44.5 L 91.7 47.85 L 91.9 51.24 L 91.83 54.65 L 91.48 58.05 L 90.85 61.43 L 89.95 64.76 L 88.77 68.02 L 87.33 71.19 L 85.62 74.23 L 83.67 77.15 L 81.48 79.9 L 79.07 82.48 L 76.44 84.86 L 73.62 87.03 L 70.62 88.96 L 67.46 90.66 L 64.16 92.1 L 60.74 93.27 L 57.23 94.16 L 53.64 94.77 L 50.0 95.08";
const LOGO_SVG='<svg viewBox="0 0 100 100" width="24" height="24" fill="none"><g><animateTransform attributeName="transform" attributeType="XML" type="rotate" from="0 50 50" to="360 50 50" dur="6s" repeatCount="indefinite"/><path d="'+SPIRAL+'" stroke="#ff6a00" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/></g></svg>';
document.getElementById('slogo').innerHTML=LOGO_SVG;
(function(){const l=document.createElement('link');l.rel='icon';l.href='data:image/svg+xml,'+encodeURIComponent(LOGO_SVG.replace('width="24" height="24"','viewBox="0 0 100 100"'));document.head.appendChild(l);})();
const API='/api';
let TOKEN=localStorage.getItem('jalebi_token')||'';
let ME=null;
const $=id=>document.getElementById(id);
async function api(path,opts={}){
  const r=await fetch(API+path,{...opts,headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN,...(opts.headers||{})}});
  if(!r.ok){throw new Error((await r.json().catch(()=>({}))).detail||('HTTP '+r.status));}
  return r.json();
}
function setToken(t){TOKEN=t;localStorage.setItem('jalebi_token',t);}
async function boot(){
  if(!TOKEN){show('login');return;}
  try{ME=await api('/auth/me');$('whoami').textContent=ME.email+' · '+ME.role;show('app');renderTabs();openTab('overview');}
  catch(e){setToken('');show('login');}
}
function show(which){$('login').classList.toggle('hidden',which!=='login');$('app').classList.toggle('hidden',which!=='app');}
$('devbtn').onclick=async()=>{try{const d=await api('/auth/dev-login',{method:'POST',body:JSON.stringify({email:$('email').value,secret:$('secret').value})});setToken(d.access_token);boot();}catch(e){$('loginerr').textContent=e.message;}};
$('tokbtn').onclick=()=>{setToken($('token').value.trim());boot();};
$('logout').onclick=()=>{setToken('');ME=null;show('login');};

// Escape before interpolating into innerHTML. Document titles and URLs come
// from /api/evaluate, which is unauthenticated by default, so a writer could
// otherwise plant script that runs in an admin's browser.
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
// Only http(s) links are rendered; "javascript:" and friends are dropped.
function safeUrl(u){const s=String(u==null?'':u);return /^https?:\/\//i.test(s)?esc(s):'';}

const TABS=[['overview','Overview'],['documents','Documents'],['writers','Writers'],['issues','Issues'],['providers','AI Usage'],['knowledge','Knowledge'],['rubrics','Rubrics'],['users','Users'],['logs','Logs']];
function renderTabs(){$('tabs').innerHTML='';TABS.forEach(([id,label])=>{const b=document.createElement('div');b.className='tab';b.textContent=label;b.onclick=()=>openTab(id);b.dataset.id=id;$('tabs').appendChild(b);});}
function activeTab(id){[...document.querySelectorAll('.tab')].forEach(t=>t.classList.toggle('active',t.dataset.id===id));}
async function openTab(id){activeTab(id);const v=$('view');v.innerHTML='<p class=muted>Loading…</p>';try{await RENDER[id](v);}catch(e){v.innerHTML='<div class=card><small class=err>'+e.message+'</small></div>';}}

function bar(val,max){const pct=max?Math.round(val/max*100):0;return `<div class=barbg><div class=bar style="width:${pct}%"></div></div>`;}
function kpi(label,val){return `<div class=card><div class=klabel>${label}</div><div class=kpi>${val}</div></div>`;}

const RENDER={
 async overview(v){const d=await api('/analytics/overview');
   if(d.empty){v.innerHTML='<div class=card>No evaluations yet. Run one from the extension.</div>';return;}
   let html=`<div class=grid>${kpi('Evaluations',d.total_evaluations)}${kpi('Avg score',d.avg_score)}${kpi('Pass rate',d.pass_rate+'%')}${kpi('Docs revised',d.revision_frequency.docs_revised)}</div>`;
   html+='<div class=card style=margin-top:14px><h2>By content type</h2><table><tr><th>Type</th><th>Count</th><th>Avg</th><th>Pass %</th></tr>';
   d.by_content_type.forEach(r=>html+=`<tr><td>${r.content_type}</td><td>${r.count}</td><td>${r.avg_score}</td><td>${r.pass_rate}%</td></tr>`);
   html+='</table></div>';
   html+='<div class=card style=margin-top:14px><h2>Readiness</h2>';
   const rb=d.readiness_breakdown,tot=Object.values(rb).reduce((a,b)=>a+b,0);
   Object.entries(rb).forEach(([k,c])=>{html+=`<div class=row style=margin:6px0><div style=width:180px>${k}</div>${bar(c,tot)}<div style=width:40px;text-align:right>${c}</div></div>`;});
   html+='</div>';v.innerHTML=html;},
 async documents(v){const rows=await api('/documents');
   const ST=['draft','under_review','finalized','published'];
   const sla=d=>{const s=d.sla||{};if(!s.phase)return '<span class=muted>–</span>';
     const h=s.hours_remaining;
     if(s.overdue)return `<span style="color:#f43f5e;font-weight:700">OVERDUE ${Math.abs(Math.round(h))}h</span><div class=muted style=font-size:10px>${esc(s.phase)}</div>`;
     if(s.at_risk)return `<span style="color:#f59e0b;font-weight:700">${Math.round(h)}h left</span><div class=muted style=font-size:10px>${esc(s.phase)}</div>`;
     return `<span style="color:#10b981">${Math.round(h)}h left</span><div class=muted style=font-size:10px>${esc(s.phase)}</div>`;};
   const integ=d=>{const i=d.integrity||{};if(!i.checked)return '<span class=muted title="Not yet checked">–</span>';
     const col=i.passed?'#10b981':'#f43f5e';
     return `<span style="color:${col}">AI ${i.ai_percent}% / Plag ${i.plagiarism_percent}%</span>`;};
   const overdue=rows.filter(d=>(d.sla||{}).overdue).length;
   let html='<div class=card><h2>Content tracker ('+rows.length+')</h2><p class=muted style=font-size:12px>Jalebi\\'s living version of the TIES content sheet — the production loop, SLA against the SOP\\'s 12/18h and 10/12h windows, integrity results, and score trend.</p>';
   if(overdue)html+=`<p style="color:#f43f5e;font-weight:700">${overdue} article${overdue>1?'s':''} past the SOP window.</p>`;
   html+='<div style=overflow-x:auto><table><tr><th>Article</th><th>Status</th><th>SLA</th><th>Assigned to</th><th>Integrity</th><th>Editor</th><th>Latest</th><th>Trend</th><th>Revs</th><th></th></tr>';
   rows.forEach(d=>{const t=d.trend>0?('▲ +'+d.trend):(d.trend<0?('▼ '+d.trend):'–');const tc=d.trend>0?'#10b981':(d.trend<0?'#f43f5e':'var(--soft)');const gid=esc(d.google_doc_id);
     const opts=ST.map(s=>`<option ${s===d.status?'selected':''}>${esc(s)}</option>`).join('');
     const hint=d.suggested_status&&d.suggested_status!==d.status?`<div class=muted style=font-size:10px>suggests: ${esc(d.suggested_status)}</div>`:'';
     const u=safeUrl(d.url);
     const title=u?`<a href="${u}" target=_blank rel=noopener style=color:var(--jalebi600)>${esc(d.title)}</a>`:esc(d.title);
     const why=d.escalation_reason?`<div class=muted style=font-size:10px>${esc(d.escalation_reason)}</div>`:
               (d.override_reason?`<div style="font-size:10px;color:#f59e0b">override: ${esc(d.override_reason)}</div>`:'');
     html+=`<tr><td>${title}<div class=muted style=font-size:10px>${esc(d.content_type||'')}</div></td>`+
       `<td><select class=dstatus data-g="${gid}">${opts}</select>${hint}${why}</td>`+
       `<td>${sla(d)}</td>`+
       `<td>${esc(d.assigned_to||'')||'<span class=muted>–</span>'}</td>`+
       `<td>${integ(d)}</td>`+
       `<td><input class=deditor data-g="${gid}" value="${esc(d.editor||'')}" style=width:110px placeholder=editor></td>`+
       `<td><b>${d.latest_score==null?'-':esc(d.latest_score)}</b></td><td style="color:${tc}">${t}</td><td>${esc(d.revisions)}</td>`+
       `<td><button data-save="${gid}">Save</button></td></tr>`;});
   v.innerHTML=html+'</table></div></div>';
   v.querySelectorAll('[data-save]').forEach(b=>b.onclick=async()=>{const g=b.dataset.save;
     const status=v.querySelector(`.dstatus[data-g="${g}"]`).value;const editor=v.querySelector(`.deditor[data-g="${g}"]`).value;
     await api('/documents/'+encodeURIComponent(g),{method:'PATCH',body:JSON.stringify({status,editor})});b.textContent='Saved';setTimeout(()=>b.textContent='Save',1200);});},
 async writers(v){const d=await api('/analytics/overview');let html='<div class=card><h2>Writer performance</h2><table><tr><th>Writer</th><th>Dept</th><th>Evals</th><th>Avg</th><th>Pass %</th></tr>';
   (d.writers||[]).forEach(w=>html+=`<tr><td>${esc(w.email)}</td><td>${esc(w.department||'-')}</td><td>${esc(w.evaluations)}</td><td>${esc(w.avg_score)}</td><td>${esc(w.pass_rate)}%</td></tr>`);
   v.innerHTML=html+'</table></div>';},
 async issues(v){const d=await api('/analytics/overview');let html='<div class=card><h2>Most common issues</h2><table><tr><th>Problem</th><th>Count</th></tr>';
   (d.top_issues||[]).forEach(i=>html+=`<tr><td>${esc(i.problem)}</td><td>${esc(i.count)}</td></tr>`);
   v.innerHTML=html+'</table></div>';},
 async providers(v){const u=await api('/admin/usage').catch(()=>({by_model:[]}));const p=await api('/providers');
   let html='<div class=card><h2>Active provider</h2><p><span class=pill>'+p.active+'</span></p></div>';
   html+='<div class=card style=margin-top:14px><h2>Evaluations by model</h2><table><tr><th>Provider</th><th>Model</th><th>Count</th></tr>';
   (u.by_model||[]).forEach(r=>html+=`<tr><td>${esc(r.provider)}</td><td>${esc(r.model||'-')}</td><td>${esc(r.count)}</td></tr>`);
   html+='</table></div><div class=card style=margin-top:14px><h2>Available providers</h2><table><tr><th>Id</th><th>Label</th><th>Model</th><th>Open source</th><th>Available</th></tr>';
   p.providers.forEach(x=>html+=`<tr><td>${esc(x.id)}</td><td>${esc(x.label)}</td><td>${esc(x.model||'-')}</td><td>${x.open_source?'yes':''}</td><td>${x.available?'✅':''}</td></tr>`);
   v.innerHTML=html+'</table></div>';},
 async knowledge(v){const rows=await api('/knowledge');
   let html='<div class=card><h2>Add knowledge</h2><div class=stack style=max-width:640px>'
     +'<select id=kkind><option>handbook</option><option>approved</option><option>rejected</option><option>note</option><option>example</option><option>style</option><option>methodology</option></select>'
     +'<input id=ktitle placeholder=Title><textarea id=kcontent rows=5 placeholder="Editorial guidance / exemplar text…"></textarea>'
     +'<input id=kct placeholder="content type (optional, e.g. news_article)"><button id=kadd>Add & index</button></div></div>';
   html+='<div class=card style=margin-top:14px><h2>Knowledge base ('+rows.length+')</h2><table><tr><th>Kind</th><th>Title</th><th>Type</th><th>Chars</th></tr>';
   rows.forEach(r=>html+=`<tr><td><span class=pill>${esc(r.kind)}</span></td><td>${esc(r.title)}</td><td>${esc(r.content_type||'-')}</td><td>${esc(r.chars)}</td></tr>`);
   v.innerHTML=html+'</table></div>';
   $('kadd').onclick=async()=>{await api('/knowledge',{method:'POST',body:JSON.stringify({kind:$('kkind').value,title:$('ktitle').value,content:$('kcontent').value,content_type:$('kct').value||null})});openTab('knowledge');};},
 async rubrics(v){const rows=await api('/admin/rubrics');let html='';
   rows.forEach(r=>{html+=`<div class=card style=margin-bottom:12px><h2>${esc(r.label)} <span class=muted style=font-weight:400>(${esc(r.content_type)})</span></h2><table>`;
     r.dimensions.forEach(d=>html+=`<tr><td style=width:200px>${esc(d.name)}</td><td><input data-ct="${esc(r.content_type)}" data-key="${esc(d.key)}" value="${esc(d.weight)}" style=width:90px></td></tr>`);
     html+=`</table><button data-save=${r.content_type} style=margin-top:8px>Save weights</button></div>`;});
   v.innerHTML=html;
   v.querySelectorAll('[data-save]').forEach(b=>b.onclick=async()=>{const ct=b.dataset.save;const weights={};v.querySelectorAll(`[data-ct=${ct}]`).forEach(i=>weights[i.dataset.key]=parseFloat(i.value));
     await api('/admin/rubrics/'+ct,{method:'PUT',body:JSON.stringify({weights})});alert('Saved & renormalized');openTab('rubrics');});},
 async users(v){const rows=await api('/admin/users');let html='<div class=card><h2>Users</h2><table><tr><th>Email</th><th>Role</th><th>Dept</th><th></th></tr>';
   rows.forEach(u=>html+=`<tr><td>${esc(u.email)}</td><td><select data-uid=${esc(u.id)} class=urole>${['writer','editor','admin'].map(r=>`<option ${r===u.role?'selected':''}>${r}</option>`).join('')}</select></td><td><input data-uid=${esc(u.id)} class=udept value="${esc(u.department||'')}" style=width:120px></td><td><button data-save=${esc(u.id)}>Save</button></td></tr>`);
   v.innerHTML=html+'</table></div>';
   v.querySelectorAll('[data-save]').forEach(b=>b.onclick=async()=>{const id=b.dataset.save;const role=v.querySelector(`.urole[data-uid="${id}"]`).value;const department=v.querySelector(`.udept[data-uid="${id}"]`).value;
     await api('/admin/users/'+id,{method:'PATCH',body:JSON.stringify({role,department})});alert('Saved');});},
 async logs(v){const rows=await api('/admin/logs');let html='<div class=card><h2>Audit log</h2><table><tr><th>When</th><th>Actor</th><th>Action</th><th>Target</th></tr>';
   rows.forEach(r=>html+=`<tr><td class=muted>${esc((r.created_at||'').slice(0,19).replace('T',' '))}</td><td>${esc(r.actor||'-')}</td><td><span class=pill>${esc(r.action)}</span></td><td>${esc(r.target)}</td></tr>`);
   v.innerHTML=html+'</table></div>';},
};
window.addEventListener('message',e=>{if(e.data&&e.data.type==='jalebi-auth'){setToken(e.data.token);boot();}});
boot();
</script></body></html>"""


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(_PAGE)
