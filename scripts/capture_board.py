#!/usr/bin/env python3
"""Painel visual (estilo board) das capturas de chamadas LLM.

Serve uma página única + API JSON sobre o diretório de captura:

    python scripts/capture_board.py --dir data/llm-capture --port 8011

Rotas:
    /                     board (HTML/JS/CSS inline)
    /api/index            metadados de todas as chamadas (leve)
    /api/call/<arquivo>   JSON completo daquela chamada
"""

from __future__ import annotations

import argparse
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Capturas LLM · Deep Research</title>
<style>
:root{
  --bg:#0b0e14; --panel:#11161f; --card:#151b26; --card-hi:#1a2230;
  --line:#2a3342; --text:#e6edf7; --muted:#8b98ab; --faint:#5c6879;
  --accent:#7c9cff;
  --planner:#7c9cff; --historiador:#f2b04a; --visionario:#b98cff;
  --cetico:#57c78a; --futurista:#4ec9d9; --auditor:#ff7a6b; --writer:#ffd166;
  --ok:#57c78a; --err:#ff6b6b;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,monospace;
  --sans:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
}
*{box-sizing:border-box}
html,body{height:100%;margin:0;background:var(--bg);color:var(--text);font-family:var(--sans)}
body{overflow:hidden}
header{height:64px;display:flex;align-items:center;gap:18px;padding:0 22px;
  border-bottom:1px solid var(--line);background:linear-gradient(180deg,#0d121b,#0b0e14)}
.brand{display:flex;align-items:baseline;gap:10px;font-weight:650;letter-spacing:-.01em}
.brand small{color:var(--muted);font-weight:500;font-size:12px}
.stats{display:flex;gap:20px;margin-left:8px}
.stat{display:flex;flex-direction:column;line-height:1.15}
.stat b{font-size:15px;font-variant-numeric:tabular-nums}
.stat span{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--faint)}
.spacer{flex:1}
.controls{display:flex;gap:8px;align-items:center}
input[type=search]{width:250px;background:var(--panel);border:1px solid var(--line);
  color:var(--text);border-radius:9px;padding:8px 11px;font-size:12.5px;outline:none}
input[type=search]:focus{border-color:var(--accent)}
.chip{border:1px solid var(--line);background:var(--panel);color:var(--muted);
  padding:6px 10px;border-radius:999px;font-size:11.5px;cursor:pointer;user-select:none;
  display:inline-flex;gap:6px;align-items:center}
.chip .dot{width:7px;height:7px;border-radius:50%;background:currentColor;opacity:.9}
.chip.on{color:var(--text);border-color:#3b4759;background:#1a2230}
.chip.off{opacity:.45}
main{position:relative;height:calc(100% - 64px);overflow:hidden}
#viewport{position:absolute;inset:0;cursor:grab;
  background-image:radial-gradient(#232c3a 1px,transparent 1px);
  background-size:26px 26px}
#viewport.dragging{cursor:grabbing}
#board{position:absolute;left:0;top:0;transform-origin:0 0;will-change:transform}
#edges{position:absolute;left:0;top:0;overflow:visible;pointer-events:none}
.lane-label{position:absolute;font-size:11px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--faint);font-weight:600;white-space:nowrap}
.node{position:absolute;width:260px;background:var(--card);border:1px solid var(--line);
  border-radius:14px;padding:12px 13px 11px;cursor:pointer;
  transition:border-color .15s,transform .15s,background .15s;
  box-shadow:0 8px 22px rgba(0,0,0,.32)}
.node:hover{border-color:#3d4a5e;background:var(--card-hi);transform:translateY(-1px)}
.node.sel{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent),0 10px 26px rgba(0,0,0,.4)}
.node::before{content:"";position:absolute;left:0;top:16px;bottom:16px;width:3px;
  border-radius:3px;background:var(--k,var(--accent))}
.node .row1{display:flex;justify-content:space-between;align-items:center;gap:8px}
.node .kind{font-size:11.5px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--k,var(--accent))}
.node .time{font-size:10.5px;color:var(--faint);font-variant-numeric:tabular-nums}
.node .meta{display:flex;gap:5px;margin-top:8px;flex-wrap:wrap}
.pill{font-size:10px;padding:2px 7px;border-radius:999px;border:1px solid var(--line);
  color:var(--muted);background:#0e131b;font-variant-numeric:tabular-nums}
.pill.ok{color:var(--ok);border-color:#1f4634;background:#0f1f18}
.pill.err{color:var(--err);border-color:#4a2020;background:#1d1010}
.node .preview{margin-top:9px;font-size:11.5px;line-height:1.5;color:#a9b6c8;
  display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
.node .foot{margin-top:9px;display:flex;justify-content:space-between;font-size:10px;color:var(--faint)}
.lane-band{position:absolute;left:0;height:200px;width:100%;background:#0f131c;
  border-top:1px solid #171e29;border-bottom:1px solid #171e29}
aside{position:absolute;top:0;right:0;bottom:0;width:min(560px,46vw);background:#0d121a;
  border-left:1px solid var(--line);transform:translateX(102%);transition:transform .22s ease;
  display:flex;flex-direction:column;z-index:5}
aside.open{transform:none}
aside header{height:auto;padding:16px 18px 12px;background:none;border-bottom:1px solid var(--line);
  display:block}
aside .t{font-size:13px;font-weight:650;display:flex;gap:8px;align-items:center}
aside .sub{font-size:11px;color:var(--muted);margin-top:5px;font-family:var(--mono)}
.tabs{display:flex;gap:6px;padding:10px 18px 0}
.tab{font-size:11.5px;padding:6px 11px;border-radius:8px 8px 0 0;border:1px solid transparent;
  color:var(--muted);cursor:pointer}
.tab.on{color:var(--text);background:var(--panel);border-color:var(--line);border-bottom-color:var(--panel)}
pre{flex:1;margin:0;padding:14px 18px 24px;overflow:auto;font-family:var(--mono);font-size:11.5px;
  line-height:1.6;background:var(--panel);border-top:1px solid var(--line);tab-size:2}
.j-key{color:#8fb6ff}.j-str{color:#a8d8a0}.j-num{color:#f0b37e}.j-bool{color:#d6a2ff}.j-null{color:#7b8798}
.legend{display:flex;gap:14px;flex-wrap:wrap;padding:10px 18px;border-top:1px solid var(--line);
  background:#0b0e14;font-size:11px;color:var(--muted)}
.legend i{display:inline-block;width:8px;height:8px;border-radius:3px;margin-right:6px}
.hint{position:absolute;left:18px;bottom:16px;font-size:11px;color:var(--faint)}
@media (max-width:900px){.stats{display:none}input[type=search]{width:160px}}
</style>
</head>
<body>
<header>
  <div class="brand">Deep Research <small>captura de chamadas LLM</small></div>
  <div class="stats" id="stats"></div>
  <div class="spacer"></div>
  <div class="controls">
    <input type="search" id="q" placeholder="filtrar por texto, modelo, prompt…">
    <span class="chip" id="fit">encaixar</span>
    <span class="chip on" data-filter="ok"><span class="dot" style="color:var(--ok)"></span>ok</span>
    <span class="chip on" data-filter="error"><span class="dot" style="color:var(--err)"></span>erros</span>
  </div>
</header>
<main>
  <div id="viewport"><div id="board"><svg id="edges"></svg></div></div>
  <aside id="drawer">
    <header>
      <div class="t" id="d-title">Chamada</div>
      <div class="sub" id="d-sub"></div>
    </header>
    <div class="tabs">
      <div class="tab on" data-tab="request">request</div>
      <div class="tab" data-tab="response">response</div>
      <div class="tab" data-tab="meta">meta</div>
    </div>
    <pre id="d-json"></pre>
  </aside>
  <div class="hint">arraste para navegar · scroll para zoom · clique num cartão para ver o JSON</div>
  <div class="legend" id="legend"></div>
</main>
<script>
const KIND = {
  planner:["Planejamento","--planner"], historiador:["Historiador","--historiador"],
  visionario:["Visionário","--visionario"], cetico:["Cético","--cetico"],
  futurista:["Futurista","--futurista"], auditor:["Auditoria","--auditor"],
  writer:["Redação","--writer"], outro:["Outro","--accent"]
};
const LANES = ["planner","historiador","visionario","cetico","futurista","auditor","writer","outro"];
const LANE_H = 232, CARD_GAP = 268, PAD_X = 190, PAD_Y = 84;
let DATA=[], SEL=null, view={x:40,y:20,k:0.85};
const board=document.getElementById('board'), edges=document.getElementById('edges'),
      vp=document.getElementById('viewport'), q=document.getElementById('q'),
      drawer=document.getElementById('drawer'), djson=document.getElementById('d-json'),
      dtitle=document.getElementById('d-title'), dsub=document.getElementById('d-sub');
let filters=new Set(['ok','error']);

function kindOf(c){
  const p=(c.prompt_id||'').toLowerCase();
  for(const k of Object.keys(KIND)) if(p.includes(k)) return k;
  const s=(c.system||'').toLowerCase();
  if(s.includes('redator')) return 'writer';
  if(s.includes('auditor')) return 'auditor';
  if(s.includes('historiador')) return 'historiador';
  if(s.includes('visionario')||s.includes('visionário')) return 'visionario';
  if(s.includes('cetico')||s.includes('cético')) return 'cetico';
  if(s.includes('futurista')) return 'futurista';
  if(s.includes('planejador')||s.includes('planner')) return 'planner';
  return 'outro';
}
function visible(c){
  if(!filters.has(c.status)) return false;
  const t=q.value.trim().toLowerCase();
  if(!t) return true;
  return [c.file,c.kind,c.model,c.prompt_id,c.preview,c.error].join(' ').toLowerCase().includes(t);
}
function fmtTokens(n){ if(n==null) return '—'; return n>=1000?(n/1000).toFixed(1)+'k':String(n); }
function hhmmss(iso){ try{return new Date(iso).toLocaleTimeString('pt-BR',{hour12:false});}catch(e){return '';} }

function layout(){
  const vis=DATA.filter(visible);
  const lanes={}; LANES.forEach(l=>lanes[l]=[]);
  for(const c of vis){ (lanes[c.kind]||lanes.outro).push(c); }
  let maxX=0;
  for(const l of LANES){
    lanes[l].sort((a,b)=>a.ts-b.ts);
    lanes[l].forEach((c,i)=>{ c._x=PAD_X+i*CARD_GAP; c._y=PAD_Y+LANES.indexOf(l)*LANE_H; maxX=Math.max(maxX,c._x); });
  }
  return {vis,lanes,maxX};
}

function render(){
  board.querySelectorAll('.node,.lane-label,.lane-band').forEach(n=>n.remove());
  const {vis,lanes,maxX}=layout();
  // faixas de lane (ritmo visual do board)
  LANES.forEach((l,i)=>{
    const band=document.createElement('div');
    band.className='lane-band';
    if(i%2===0) band.style.background='transparent',band.style.borderColor='transparent';
    band.style.top=(PAD_Y+i*LANE_H-46)+'px';
    band.style.height=(LANE_H-10)+'px';
    band.style.width=(maxX+340)+'px';
    board.appendChild(band);
  });
  // labels
  LANES.forEach((l,i)=>{
    const el=document.createElement('div');
    el.className='lane-label';
    el.style.left='24px'; el.style.top=(PAD_Y+i*LANE_H+6)+'px';
    el.style.color=`var(${KIND[l][1]})`;
    el.textContent=KIND[l][0];
    board.appendChild(el);
  });
  // nodes
  for(const c of vis){
    const K=KIND[c.kind]||KIND.outro;
    const n=document.createElement('div');
    n.className='node'+(SEL===c.file?' sel':'');
    n.style.left=c._x+'px'; n.style.top=c._y+'px';
    n.style.setProperty('--k',`var(${K[1]})`);
    n.innerHTML=`<div class="row1"><span class="kind">${K[0]}</span>
      <span class="time">${hhmmss(c.captured_at)}</span></div>
      <div class="meta"><span class="pill ${c.status==='ok'?'ok':'err'}">${escapeHtml(c.status||'')}</span>
      <span class="pill">${escapeHtml((c.model||'').split('/').pop())}</span>
      <span class="pill">${fmtTokens(c.prompt_tokens)}↑ ${fmtTokens(c.completion_tokens)}↓</span></div>
      <div class="preview">${escapeHtml(c.preview||c.error||'—')}</div>
      <div class="foot"><span>${escapeHtml(c.prompt_id||'—')}</span><span>${escapeHtml((c.file||'').match(/_(\d{5})_/)?.[1]||'')}</span></div>`;
    n.onclick=()=>openCall(c.file);
    board.appendChild(n);
  }
  // edges: sequential within lane + lane hand-offs
  const parts=[];
  const seq=(list)=>list.slice(1).forEach((c,i)=>parts.push([list[i],c]));
  LANES.forEach(l=>seq(lanes[l]));
  const lastOf=(list)=>list[list.length-1];
  const firstOf=(list)=>list[0];
  // searchers -> auditor (primeira chamada da lane de auditoria)
  ['historiador','visionario','cetico','futurista'].forEach(l=>{
    if(lanes[l].length&&lanes.auditor.length) parts.push([lastOf(lanes[l]),firstOf(lanes.auditor)]);
  });
  if(lanes.auditor.length&&lanes.writer.length) parts.push([lastOf(lanes.auditor),firstOf(lanes.writer)]);
  if(lanes.planner.length) ['historiador','visionario','cetico','futurista'].forEach(l=>{
    if(lanes[l].length) parts.push([lastOf(lanes.planner),firstOf(lanes[l])]);
  });
  const W=maxX+320,H=PAD_Y+LANES.length*LANE_H;
  edges.setAttribute('width',W); edges.setAttribute('height',H);
  edges.innerHTML=`<defs><marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto">
    <path d="M0,0 L8,4 L0,8 z" fill="#33405a"/></marker></defs>`+
    parts.map(([a,b])=>{
      const same=a.kind===b.kind;
      const x1=a._x+260,y1=a._y+56,x2=b._x,y2=b._y+56,dx=Math.max(46,(x2-x1)/2);
      const d=same?`M${x1},${y1} C${x1+dx},${y1} ${x2-dx},${y2} ${x2},${y2}`
                  :`M${x1},${y1} C${x1+72},${y1} ${x1+72},${y2} ${x2-16},${y2}`;
      return `<path d="${d}" fill="none" stroke="${same?'#2b3546':'#3a4a66'}" stroke-width="${same?1.4:1.1}"
        ${same?'':'stroke-dasharray="4 5" opacity="0.5"'} marker-end="url(#arrow)"/>`;
    }).join('');
  applyView();
}

function applyView(){
  board.style.transform=`translate(${view.x}px,${view.y}px) scale(${view.k})`;
}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}

function stats(){
  const total=DATA.length, errs=DATA.filter(c=>c.status==='error').length;
  const pt=DATA.reduce((a,c)=>a+(c.prompt_tokens||0),0), ct=DATA.reduce((a,c)=>a+(c.completion_tokens||0),0);
  const models=[...new Set(DATA.map(c=>c.model))].length;
  document.getElementById('stats').innerHTML=[
    [total,'chamadas'],[errs,'erros'],[fmtTokens(pt)+' / '+fmtTokens(ct),'tokens in/out'],[models,'modelos']
  ].map(([v,l])=>`<div class="stat"><b>${v}</b><span>${l}</span></div>`).join('');
  const used=[...new Set(DATA.map(c=>c.kind))].filter(k=>KIND[k]);
  document.getElementById('legend').innerHTML=used.map(k=>
    `<span><i style="background:var(${KIND[k][1]})"></i>${KIND[k][0]}</span>`).join('');
}

let current=null, tab='request';
async function openCall(file){
  SEL=file; render();
  current=await (await fetch('/api/call/'+encodeURIComponent(file))).json();
  const c=DATA.find(x=>x.file===file)||{};
  drawer.classList.add('open');
  dtitle.innerHTML=`<span style="color:var(${KIND[c.kind]?.[1]||'--accent'})">${KIND[c.kind]?.[0]||c.kind}</span>
    <span style="color:var(--muted);font-weight:500">${c.model||''}</span>`;
  dsub.textContent=`${c.prompt_id||'sem prompt_id'} · ${hhmmss(c.captured_at)} · ${c.status}`;
  paint();
}
function paint(){
  if(!current) return;
  const src=current[tab]??current;
  djson.innerHTML=syntax(src);
}
function syntax(v){
  // Escapa &, < e > antes do highlight: o JSON vem do provedor/LLM e não é confiável.
  // Aspas ficam intactas porque o regex de tokenização depende delas; todo o resto é texto.
  const j=JSON.stringify(v===undefined?null:v,null,2)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  return j.replace(/("(\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false)\b|\bnull\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
    m=>{
      if(/^"/.test(m)) return /:$/.test(m)?`<span class="j-key">${m}</span>`:`<span class="j-str">${m}</span>`;
      if(/true|false/.test(m)) return `<span class="j-bool">${m}</span>`;
      if(/null/.test(m)) return `<span class="j-null">${m}</span>`;
      return `<span class="j-num">${m}</span>`;
    });
}

// pan / zoom
let drag=null;
vp.addEventListener('mousedown',e=>{ if(e.target.closest('.node'))return; drag={x:e.clientX,y:e.clientY,vx:view.x,vy:view.y}; vp.classList.add('dragging');});
window.addEventListener('mousemove',e=>{ if(!drag)return; view.x=drag.vx+e.clientX-drag.x; view.y=drag.vy+e.clientY-drag.y; applyView();});
window.addEventListener('mouseup',()=>{drag=null;vp.classList.remove('dragging');});
vp.addEventListener('wheel',e=>{ e.preventDefault(); const k=Math.min(1.6,Math.max(0.35,view.k*(e.deltaY<0?1.08:0.93))); view.k=k; applyView();},{passive:false});
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));t.classList.add('on');tab=t.dataset.tab;paint();});
document.querySelectorAll('.chip[data-filter]').forEach(ch=>ch.onclick=()=>{
  const f=ch.dataset.filter; if(filters.has(f)){filters.delete(f);ch.classList.add('off');ch.classList.remove('on');}
  else{filters.add(f);ch.classList.add('on');ch.classList.remove('off');}
  render();
});
document.getElementById('fit').onclick=()=>{
  const xs=DATA.filter(visible).map(c=>c._x||0);
  const maxX=xs.length?Math.max(...xs):800;
  view.k=Math.max(0.12,Math.min(1,(vp.clientWidth-90)/(maxX+340)));
  view.x=28; view.y=14; applyView();
};
q.addEventListener('input',()=>render());
window.addEventListener('keydown',e=>{ if(e.key==='Escape'){drawer.classList.remove('open');SEL=null;render();} });

(async()=>{
  DATA=(await (await fetch('/api/index')).json()).map(c=>({...c,kind:kindOf(c),ts:Date.parse(c.captured_at)||0}));
  stats(); render();
})();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    capture_dir = "."

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = unquote(self.path.split("?")[0])
        if path == "/":
            self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/api/index":
            self._send(200, json.dumps(self._index()).encode("utf-8"), "application/json")
            return
        if path.startswith("/api/call/"):
            name = os.path.basename(path[len("/api/call/"):])
            full = os.path.join(self.capture_dir, name)
            if not name or not os.path.isfile(full):
                self._send(404, b'{"error":"not found"}', "application/json")
                return
            with open(full, "rb") as fh:
                self._send(200, fh.read(), "application/json")
            return
        self._send(404, b'{"error":"not found"}', "application/json")

    def _index(self):
        out = []
        for name in sorted(os.listdir(self.capture_dir)):
            if not name.endswith(".json") or name.startswith("."):
                continue
            try:
                with open(os.path.join(self.capture_dir, name), encoding="utf-8") as fh:
                    data = json.load(fh)
            except Exception:
                continue
            req = data.get("request") or {}
            resp = data.get("response") or {}
            usage = resp.get("usage") or {}
            msgs = req.get("messages") or []
            system = " ".join(
                str(m.get("content")) for m in msgs if isinstance(m, dict) and m.get("role") == "system"
            )
            out.append(
                {
                    "file": name,
                    "captured_at": data.get("captured_at"),
                    "status": data.get("status"),
                    "model": req.get("model"),
                    "prompt_id": req.get("prompt_id"),
                    "system": system[:400],
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "preview": (resp.get("content_final") or "")[:700],
                    "error": data.get("error"),
                }
            )
        return out

    def log_message(self, fmt, *args):  # silencia log por request
        return


def main() -> int:
    ap = argparse.ArgumentParser(description="Board visual das capturas LLM.")
    ap.add_argument("--dir", default=os.environ.get("DR_LLM_CAPTURE_DIR") or "data/llm-capture")
    ap.add_argument("--port", type=int, default=8011)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    Handler.capture_dir = os.path.abspath(args.dir)
    if not os.path.isdir(Handler.capture_dir):
        raise SystemExit(f"diretório inexistente: {Handler.capture_dir}")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"board em http://{args.host}:{args.port}  (dir={Handler.capture_dir})")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
