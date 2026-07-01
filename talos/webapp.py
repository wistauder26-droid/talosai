"""Lokales Dashboard: Chat mit Talos + Live-Blick in Memory, Lektionen, Skills.

Start: `talos-web`, dann http://localhost:7777
Single-User, nur für localhost gedacht. Features: Verlauf (Sessions),
Chat-/Coding-Modus, Live-Aktivitätsgraph, Token/Kosten-Anzeige,
Voice-Ein-/Ausgabe, Markdown, Dark Mode.
"""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from .agent import Agent
from .config import Config
from .learning import reflect

MODES = {
    "chat": "",
    "coden": (
        "CODING-MODUS: Du arbeitest als Programmier-Agent. Liefere lauffähigen, "
        "getesteten Code. Nutze das shell-Tool, um Code auszuführen und zu prüfen, "
        "bevor du Erfolg meldest. Lege Projekte unter ~/TalosProjekte/ an. "
        "Erkläre knapp, Code spricht für sich."
    ),
}

app = FastAPI(title="TalosAI")
_cfg = Config()
_sessions_dir = _cfg.data_dir / "sessions"
_sessions_dir.mkdir(exist_ok=True)
_lock = threading.Lock()  # ein Agent, eine Anfrage zur Zeit


def _new_agent(mode: str = "chat") -> Agent:
    agent = Agent(_cfg, session_id=uuid.uuid4().hex[:12])
    agent.mode_prompt = MODES.get(mode, "")
    agent.mode = mode
    agent.title = ""
    return agent


_agent = _new_agent()


def _save_session() -> None:
    if not _agent.messages:
        return
    path = _sessions_dir / f"{_agent.session_id}.json"
    path.write_text(json.dumps({
        "id": _agent.session_id,
        "title": _agent.title,
        "mode": getattr(_agent, "mode", "chat"),
        "updated": time.time(),
        "messages": _agent.messages,
    }, ensure_ascii=False))


def _usage() -> dict:
    return {
        "input": _agent.llm.total_input_tokens,
        "output": _agent.llm.total_output_tokens,
        "cost": round(_agent.llm.total_cost_usd, 4),
        "context": _agent.llm.last_input_tokens,
        "window": 200_000,
    }


class ChatIn(BaseModel):
    message: str


class SessionIn(BaseModel):
    id: str = ""
    mode: str = "chat"


@app.post("/api/chat/stream")
def chat_stream(body: ChatIn):
    """Streamt Tool-Events live, dann die finale Antwort (SSE-Format)."""
    q: queue.Queue = queue.Queue()

    def worker() -> None:
        with _lock:
            if not _agent.title:
                _agent.title = body.message[:60]
            _agent.on_tool = lambda name, args: q.put({
                "type": "tool",
                "name": name,
                "detail": str(
                    args.get("command") or args.get("query") or args.get("url")
                    or args.get("task") or args.get("name") or ""
                )[:120],
            })
            try:
                reply = _agent.run(body.message)
            except Exception as e:
                reply = f"Fehler: {type(e).__name__}: {e}"
            _save_session()
            q.put({"type": "reply", "text": reply, "usage": _usage()})
        q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def gen():
        while True:
            item = q.get()
            if item is None:
                break
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/sessions")
def sessions():
    out = []
    for path in _sessions_dir.glob("*.json"):
        try:
            d = json.loads(path.read_text())
            out.append({"id": d["id"], "title": d.get("title") or "(ohne Titel)",
                        "mode": d.get("mode", "chat"), "updated": d.get("updated", 0)})
        except (json.JSONDecodeError, KeyError):
            continue
    out.sort(key=lambda s: -s["updated"])
    return {"sessions": out[:50], "current": _agent.session_id}


@app.post("/api/session/new")
def session_new(body: SessionIn):
    global _agent
    with _lock:
        if _agent.messages:
            reflect(_agent)
            _save_session()
        _agent = _new_agent(body.mode)
    return {"id": _agent.session_id}


@app.post("/api/session/load")
def session_load(body: SessionIn):
    global _agent
    path = _sessions_dir / f"{body.id}.json"
    if not path.exists():
        return {"error": "nicht gefunden"}
    d = json.loads(path.read_text())
    with _lock:
        _agent = _new_agent(d.get("mode", "chat"))
        _agent.session_id = d["id"]
        _agent.title = d.get("title", "")
        _agent.messages = d["messages"]
    # nur User/Assistent-Textnachrichten fürs UI
    history = [
        {"role": m["role"], "text": m["content"]}
        for m in _agent.messages
        if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)
        and m.get("content")
    ]
    return {"id": d["id"], "history": history}


@app.get("/api/state")
def state():
    return {
        "memory": _agent.memory.index(),
        "lessons": _agent.memory.lessons(),
        "skills": _agent.skills.index(),
        "model": _agent.cfg.model,
        "mode": getattr(_agent, "mode", "chat"),
        "usage": _usage(),
    }


PAGE = """<!doctype html>
<html lang="de"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TalosAI</title>
<script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>
<style>
  :root{--bg:#f5f5f7;--card:#fff;--text:#1d1d1f;--muted:#86868b;--accent:#0071e3;
        --border:#e5e5ea;--chip:#f0f0f2;--nav:#ececf0;--radius:16px}
  @media(prefers-color-scheme:dark){:root{--bg:#000;--card:#1c1c1e;--text:#f5f5f7;
        --muted:#98989d;--accent:#0a84ff;--border:#2c2c2e;--chip:#2c2c2e;--nav:#141416}}
  *{box-sizing:border-box;margin:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',Helvetica,Arial,sans-serif;
       background:var(--bg);color:var(--text);height:100vh;display:flex;overflow:hidden}

  /* ===== linke Navigation ===== */
  nav{width:230px;background:var(--nav);border-right:1px solid var(--border);padding:16px 12px;
      display:flex;flex-direction:column;gap:4px;flex-shrink:0}
  nav .logo{font-size:17px;font-weight:700;letter-spacing:-.02em;padding:4px 10px 14px}
  nav button{display:flex;align-items:center;gap:9px;width:100%;text-align:left;background:none;
      border:none;color:var(--text);padding:9px 10px;border-radius:10px;font-size:14px;cursor:pointer}
  nav button:hover{background:var(--chip)}
  nav button.active{background:var(--accent);color:#fff}
  nav .sect{font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;
      letter-spacing:.05em;padding:16px 10px 6px}
  #history{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:2px}
  #history button{font-size:13px;color:var(--muted);white-space:nowrap;overflow:hidden;
      text-overflow:ellipsis;display:block}
  #history button.active{background:var(--chip);color:var(--text)}

  /* ===== Mitte: Chat ===== */
  main{flex:1;display:flex;flex-direction:column;max-width:800px;margin:0 auto;
       padding:18px 24px;height:100vh;min-width:0}
  header{display:flex;align-items:center;gap:10px;padding-bottom:6px}
  header h1{font-size:18px;font-weight:600}
  .badge{font-size:11px;color:var(--muted);background:var(--chip);padding:3px 10px;border-radius:10px}
  #chat{flex:1;overflow-y:auto;padding:12px 4px;display:flex;flex-direction:column;gap:10px}
  .msg{max-width:86%;padding:11px 15px;border-radius:var(--radius);line-height:1.55;
       font-size:15px;word-break:break-word;position:relative}
  .msg p{margin:0 0 8px}.msg p:last-child{margin:0}
  .msg pre{background:rgba(128,128,128,.12);padding:10px;border-radius:8px;overflow-x:auto;
       font-size:13px;margin:8px 0}
  .msg code{font-family:ui-monospace,Menlo,monospace;font-size:13px}
  .msg ul,.msg ol{padding-left:20px;margin:6px 0}
  .user{align-self:flex-end;background:var(--accent);color:#fff;border-bottom-right-radius:5px;
        white-space:pre-wrap}
  .bot{align-self:flex-start;background:var(--card);border-bottom-left-radius:5px;
       box-shadow:0 1px 2px rgba(0,0,0,.08)}
  .speakbtn{position:absolute;bottom:-22px;left:6px;background:none;border:none;cursor:pointer;
       font-size:13px;color:var(--muted);padding:2px}
  .tool{align-self:flex-start;font-size:12px;color:var(--muted);padding:2px 10px;
        background:var(--chip);border-radius:10px;max-width:86%;overflow:hidden;
        text-overflow:ellipsis;white-space:nowrap;animation:pop .2s ease}
  @keyframes pop{from{opacity:0;transform:translateY(4px)}to{opacity:1}}
  .typing{align-self:flex-start;color:var(--muted);font-size:14px;padding:4px 8px}
  .typing::after{content:'●●●';letter-spacing:3px;animation:blink 1.2s infinite}
  @keyframes blink{50%{opacity:.3}}
  #suggestions{display:flex;gap:8px;flex-wrap:wrap;padding:8px 0}
  #suggestions button{background:var(--chip);border:none;color:var(--text);padding:8px 14px;
        border-radius:16px;font-size:13px;cursor:pointer}
  form{display:flex;gap:8px;padding-top:10px;align-items:center}
  input[type=text]{flex:1;padding:13px 18px;border-radius:24px;border:1px solid var(--border);
        font-size:15px;background:var(--card);color:var(--text);outline:none;min-width:0}
  input[type=text]:focus{border-color:var(--accent)}
  .iconbtn{width:44px;height:44px;border:none;border-radius:50%;background:var(--chip);
        color:var(--text);font-size:18px;cursor:pointer;flex-shrink:0}
  .iconbtn.active{background:#ff3b30;color:#fff}
  .iconbtn.on{background:var(--accent);color:#fff}
  #send{width:auto;padding:0 20px;height:44px;border-radius:24px;background:var(--accent);
        color:#fff;font-size:15px;font-weight:500}
  #send:disabled{opacity:.4}

  /* ===== rechte Seite: Graph + Wissen + Verbrauch ===== */
  aside{width:340px;background:var(--card);border-left:1px solid var(--border);
        overflow-y:auto;display:flex;flex-direction:column;flex-shrink:0}
  #graphwrap{position:relative;background:#0d1526;height:240px;flex-shrink:0}
  #graph{width:100%;height:100%;display:block}
  #graphlabel{position:absolute;bottom:8px;left:12px;color:#4a5a78;font-size:11px}
  .asidebody{padding:16px 20px;display:flex;flex-direction:column;gap:6px}
  details{border-bottom:1px solid var(--border);padding:9px 0}
  summary{font-size:12px;font-weight:600;color:var(--muted);text-transform:uppercase;
        letter-spacing:.05em;cursor:pointer;list-style:none;display:flex;gap:8px}
  summary::before{content:'›';transition:transform .15s}
  details[open] summary::before{transform:rotate(90deg)}
  details pre{font:12px/1.7 ui-monospace,Menlo,monospace;white-space:pre-wrap;
        word-break:break-word;padding-top:8px;color:var(--text)}

  /* Verbrauch im Claude-Code-Stil */
  #usagebox{background:var(--chip);border-radius:12px;padding:12px 14px;margin-top:10px;
        font:12px/1.8 ui-monospace,Menlo,monospace}
  #usagebox .row{display:flex;justify-content:space-between}
  #usagebox .row span:last-child{font-weight:600}
  #ctxbar{height:6px;background:rgba(128,128,128,.25);border-radius:3px;margin-top:6px;overflow:hidden}
  #ctxfill{height:100%;width:0%;background:#30d158;border-radius:3px;transition:width .4s}
  #ctxfill.warn{background:#ffd60a}#ctxfill.crit{background:#ff453a}
  @media(max-width:1100px){aside{display:none}}
  @media(max-width:800px){nav{display:none}}
</style></head><body>

<nav>
  <div class="logo">◈ TalosAI</div>
  <button onclick="newSession()">＋ Neuer Chat</button>
  <div class="sect">Modus</div>
  <button id="mode-chat" onclick="setMode('chat')">💬 Chat</button>
  <button id="mode-coden" onclick="setMode('coden')">⌨️ Coden</button>
  <div class="sect">Verlauf</div>
  <div id="history"></div>
</nav>

<main>
  <header>
    <h1 id="modetitle">Chat</h1>
    <span class="badge" id="model"></span>
  </header>
  <div id="chat"></div>
  <div id="suggestions">
    <button>Was weißt du über mich?</button>
    <button>Recherchiere die wichtigsten KI-News von heute</button>
    <button>Welche Skills hast du schon gelernt?</button>
  </div>
  <form id="form">
    <button type="button" class="iconbtn" id="mic" title="Spracheingabe">🎤</button>
    <input type="text" id="inp" placeholder="Nachricht an Talos…" autocomplete="off" autofocus>
    <button type="button" class="iconbtn" id="tts" title="Antworten automatisch vorlesen">🔊</button>
    <button id="send" class="iconbtn">Senden</button>
  </form>
</main>

<aside>
  <div id="graphwrap"><canvas id="graph"></canvas><span id="graphlabel">Agenten-Aktivität</span></div>
  <div class="asidebody">
    <details open><summary>🧠 Gedächtnis</summary><pre id="memory">–</pre></details>
    <details><summary>📚 Lektionen</summary><pre id="lessons">–</pre></details>
    <details><summary>⚡ Skills</summary><pre id="skills">–</pre></details>
    <div id="usagebox">
      <div class="row"><span>Session-Kosten</span><span id="u-cost">$0.0000</span></div>
      <div class="row"><span>Tokens ein</span><span id="u-in">0</span></div>
      <div class="row"><span>Tokens aus</span><span id="u-out">0</span></div>
      <div class="row"><span>Kontext</span><span id="u-ctx">0%</span></div>
      <div id="ctxbar"><div id="ctxfill"></div></div>
    </div>
  </div>
</aside>

<script>
const chat=document.getElementById('chat'),inp=document.getElementById('inp'),
      send=document.getElementById('send'),sugg=document.getElementById('suggestions');
let mode='chat';

function el(cls,html){const d=document.createElement('div');d.className=cls;
  if(html!==undefined)d.innerHTML=html;chat.appendChild(d);chat.scrollTop=chat.scrollHeight;return d}
function addUser(t){const d=el('msg user');d.textContent=t}
function addBot(t){const d=el('msg bot',marked.parse(t));
  const b=document.createElement('button');b.className='speakbtn';b.textContent='🔊';
  b.title='Vorlesen';b.onclick=()=>speak(t,true);d.appendChild(b)}
function addTool(t){el('tool','⚙ '+t.name+(t.detail?': '+t.detail:''))}

// ===== Verbrauch (Claude-Code-Stil) =====
function updateUsage(u){if(!u)return;
  document.getElementById('u-cost').textContent='$'+u.cost.toFixed(4);
  document.getElementById('u-in').textContent=u.input.toLocaleString('de-DE');
  document.getElementById('u-out').textContent=u.output.toLocaleString('de-DE');
  const pct=Math.min(100,Math.round(u.context/u.window*100));
  document.getElementById('u-ctx').textContent=
    pct+'% ('+(u.context/1000).toFixed(1)+'k / '+(u.window/1000)+'k)';
  const f=document.getElementById('ctxfill');f.style.width=pct+'%';
  f.className=pct>80?'crit':pct>50?'warn':''}

// ===== Sprachausgabe (TTS) — robust gegen Browser-Eigenheiten =====
let ttsOn=false,voices=[];
function loadVoices(){voices=speechSynthesis.getVoices()}
loadVoices();speechSynthesis.onvoiceschanged=loadVoices;
const ttsBtn=document.getElementById('tts');
ttsBtn.onclick=()=>{ttsOn=!ttsOn;ttsBtn.classList.toggle('on',ttsOn);
  if(ttsOn){speak('Sprachausgabe aktiviert.',true)}else{speechSynthesis.cancel()}};
function speak(text,force){
  if(!ttsOn&&!force)return;
  speechSynthesis.cancel();
  const plain=text.replace(/```[\\s\\S]*?```/g,' Codeblock. ').replace(/`[^`]*`/g,'')
    .replace(/\\[(.*?)\\]\\([^)]*\\)/g,'$1').replace(/[*_#>|]/g,'').replace(/\\s+/g,' ').trim();
  if(!plain)return;
  const voice=voices.find(v=>v.lang==='de-DE')||voices.find(v=>v.lang.startsWith('de'));
  // In Sätze aufteilen — lange Utterances brechen in Chrome/Safari ab
  const parts=plain.match(/[^.!?]+[.!?]*/g)||[plain];
  for(const p of parts){const u=new SpeechSynthesisUtterance(p.trim());
    u.lang='de-DE';u.rate=1.05;if(voice)u.voice=voice;speechSynthesis.speak(u)}
  // Chrome-Bug: Ausgabe stoppt nach ~15s — regelmäßig anstoßen
  clearInterval(window._ttsKick);
  window._ttsKick=setInterval(()=>{if(!speechSynthesis.speaking)clearInterval(window._ttsKick);
    else{speechSynthesis.pause();speechSynthesis.resume()}},10000)}

// ===== Spracheingabe (Mikrofon) =====
const micBtn=document.getElementById('mic');
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
if(!SR){micBtn.style.display='none'}
else{const rec=new SR();rec.lang='de-DE';rec.interimResults=true;let listening=false;
  micBtn.onclick=()=>{if(listening){rec.stop();return}
    rec.start();listening=true;micBtn.classList.add('active');micBtn.textContent='⏹'};
  rec.onresult=e=>{inp.value=Array.from(e.results).map(r=>r[0].transcript).join('')};
  rec.onend=()=>{listening=false;micBtn.classList.remove('active');micBtn.textContent='🎤';
    if(inp.value.trim())document.getElementById('form').requestSubmit()};
  rec.onerror=()=>{listening=false;micBtn.classList.remove('active');micBtn.textContent='🎤'}}

// ===== Live-Aktivitätsgraph (rechte Seite) =====
const cv=document.getElementById('graph'),gctx=cv.getContext('2d');
function gsize(){cv.width=cv.clientWidth*devicePixelRatio;cv.height=cv.clientHeight*devicePixelRatio;
  gctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0)}
addEventListener('resize',gsize);
const COLORS={talos:'#ffffff',delegate:'#7aa2ff',web_search:'#5ac8fa',web_fetch:'#5ac8fa',
  shell:'#ffd60a',memory_save:'#bf5af2',memory_read:'#bf5af2',skill_save:'#30d158',
  skill_read:'#30d158',default:'#98989d'};
let gnodes=[],gedges=[],ambient=[],hub=null,busy=false;
function initGraph(){const W=cv.clientWidth,H=cv.clientHeight;
  ambient=Array.from({length:50},()=>({x:Math.random()*W,y:Math.random()*H,
    r:.8+Math.random()*1.3,tw:Math.random()*6.28}));
  gnodes=[{id:'talos',label:'Talos',x:W/2,y:H/2,tx:W/2,ty:H/2,r:7,color:COLORS.talos,
    born:0,perm:true}];gedges=[];hub=gnodes[0]}
function addGraphNode(name){const W=cv.clientWidth,H=cv.clientHeight,now=performance.now();
  const parent=(name==='delegate')?gnodes[0]:hub;
  const ang=Math.random()*6.28,dist=38+Math.random()*36;
  const n={id:name+now,label:name,x:parent.x,y:parent.y,
    tx:Math.min(W-16,Math.max(16,parent.x+Math.cos(ang)*dist)),
    ty:Math.min(H-14,Math.max(14,parent.y+Math.sin(ang)*dist)),
    r:name==='delegate'?5.5:3.5,color:COLORS[name]||COLORS.default,born:now,perm:false};
  gnodes.push(n);gedges.push({a:parent,b:n,born:now});
  if(name==='delegate')hub=n;
  if(gnodes.length>50){gnodes.splice(1,1);gedges.splice(0,1)}}
function drawGraph(t){const W=cv.clientWidth,H=cv.clientHeight;
  gctx.clearRect(0,0,W,H);
  for(const a of ambient){const tw=.25+.2*Math.sin(t/900+a.tw);
    gctx.fillStyle='rgba(180,195,225,'+tw+')';
    gctx.beginPath();gctx.arc(a.x,a.y,a.r,0,6.28);gctx.fill()}
  for(const e of gedges){const age=(t-e.born)/1000,alpha=Math.min(.5,age*2)*(busy?1:.55);
    gctx.strokeStyle='rgba(120,150,210,'+alpha+')';gctx.lineWidth=.7;
    gctx.beginPath();gctx.moveTo(e.a.x,e.a.y);gctx.lineTo(e.b.x,e.b.y);gctx.stroke()}
  for(const n of gnodes){n.x+=(n.tx-n.x)*.08;n.y+=(n.ty-n.y)*.08;
    const age=(t-n.born)/1000;let r=n.r;
    if(n.perm&&busy)r=n.r+1.6*Math.sin(t/280);else if(age<.5)r=n.r*(age*2);
    gctx.fillStyle=n.color;gctx.shadowColor=n.color;gctx.shadowBlur=n.perm||age<2?10:4;
    gctx.beginPath();gctx.arc(n.x,n.y,Math.max(r,0),0,6.28);gctx.fill();gctx.shadowBlur=0;
    if(n.perm||age<6){gctx.fillStyle='rgba(160,180,215,'+(n.perm?.9:Math.max(0,1-age/6))+')';
      gctx.font='10px -apple-system';gctx.fillText(n.label,n.x+8,n.y+3)}}
  requestAnimationFrame(drawGraph)}
gsize();initGraph();requestAnimationFrame(drawGraph);

// ===== Sessions / Verlauf / Modus =====
async function refreshSessions(){const s=await (await fetch('/api/sessions')).json();
  const h=document.getElementById('history');h.innerHTML='';
  for(const sess of s.sessions){const b=document.createElement('button');
    b.textContent=(sess.mode==='coden'?'⌨️ ':'')+sess.title;
    if(sess.id===s.current)b.className='active';
    b.onclick=()=>loadSession(sess.id);h.appendChild(b)}}
function setModeUI(){document.getElementById('mode-chat').classList.toggle('active',mode==='chat');
  document.getElementById('mode-coden').classList.toggle('active',mode==='coden');
  document.getElementById('modetitle').textContent=mode==='coden'?'Coden':'Chat';
  inp.placeholder=mode==='coden'?'Was soll ich bauen?':'Nachricht an Talos…'}
async function setMode(m){mode=m;await newSession()}
async function newSession(){await fetch('/api/session/new',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({mode})});
  chat.innerHTML='';sugg.style.display='flex';initGraph();setModeUI();
  refreshSessions();refreshState()}
async function loadSession(id){const r=await (await fetch('/api/session/load',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({id,mode})})).json();
  if(r.error)return;chat.innerHTML='';sugg.style.display='none';initGraph();
  for(const m of r.history){m.role==='user'?addUser(m.text):addBot(m.text)}
  refreshSessions();refreshState()}

async function refreshState(){const s=await (await fetch('/api/state')).json();
  document.getElementById('memory').textContent=s.memory||'(leer)';
  document.getElementById('lessons').textContent=s.lessons||'(keine)';
  document.getElementById('skills').textContent=s.skills||'(keine)';
  document.getElementById('model').textContent=s.model;
  mode=s.mode||'chat';setModeUI();updateUsage(s.usage)}

// ===== Chat mit Live-Streaming =====
async function sendMessage(text){
  addUser(text);sugg.style.display='none';send.disabled=true;
  busy=true;hub=gnodes[0];
  const typing=el('typing');
  try{
    const resp=await fetch('/api/chat/stream',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});
    const reader=resp.body.getReader(),dec=new TextDecoder();let buf='';
    while(true){const {done,value}=await reader.read();if(done)break;
      buf+=dec.decode(value,{stream:true});
      let idx;while((idx=buf.indexOf('\\n\\n'))>=0){
        const line=buf.slice(0,idx).trim();buf=buf.slice(idx+2);
        if(!line.startsWith('data: '))continue;
        const ev=JSON.parse(line.slice(6));
        if(ev.type==='tool'){addTool(ev);addGraphNode(ev.name)}
        else if(ev.type==='reply'){typing.remove();addBot(ev.text);speak(ev.text);
          updateUsage(ev.usage)}}}
  }catch(err){typing.remove();addBot('**Fehler:** '+err)}
  busy=false;hub=gnodes[0];
  send.disabled=false;inp.focus();refreshSessions()}

document.getElementById('form').onsubmit=e=>{e.preventDefault();
  const t=inp.value.trim();if(t){inp.value='';sendMessage(t)}};
sugg.querySelectorAll('button').forEach(b=>b.onclick=()=>sendMessage(b.textContent));
refreshState();refreshSessions();
</script></body></html>"""


@app.get("/")
def index() -> HTMLResponse:
    return HTMLResponse(PAGE)


def main() -> None:
    import uvicorn

    print("TalosAI Dashboard: http://localhost:7777")
    uvicorn.run(app, host="127.0.0.1", port=7777, log_level="warning")


if __name__ == "__main__":
    main()
