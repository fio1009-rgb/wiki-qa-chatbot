# -*- coding: utf-8 -*-
'''오로라 모빌리티 사내 위키 QA 챗봇 배포 실습의 시작 코드입니다.

앞선 UI 고도화 실습에서 완성한 결과물이며, 기존 기능을 유지한 채 Vercel 배포 파일을 준비합니다.
'''
import http.server
import json
import os
import re
import socketserver
import urllib.parse
from pathlib import Path

import qa_service


EMPTY_MESSAGE = "질문을 입력해 주세요."
ERROR_MESSAGE = "답변을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."
ASSET_ROOT = Path(__file__).resolve().parent.parent / "assets"


def format_sse(event_name, data):
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event_name}\ndata: {payload}\n\n"


def stream_answer(question):
    text = str(question or "").strip()
    if not text:
        yield format_sse("app_error", {"message": EMPTY_MESSAGE})
        return
    try:
        result = qa_service.answer(text)
        if not isinstance(result, dict):
            raise ValueError("invalid result")
        answer_text = str(result.get("answer", "")).strip()
        if not answer_text:
            raise ValueError("empty answer")
        for chunk in re.findall(r"\S+\s*", answer_text):
            yield format_sse("chunk", {"text": chunk})
        yield format_sse("sources", {"sources": list(result.get("sources") or [])})
        yield format_sse("done", {"metrics": dict(result.get("metrics") or {})})
    except Exception:
        yield format_sse("app_error", {"message": ERROR_MESSAGE})


PAGE_HTML = r'''<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>오로라 모빌리티 사내 위키 QA</title>
  <style>
    * { box-sizing: border-box; }
    body { margin:0; min-height:100vh; font-family:"Spoqa Han Sans Neo","Pretendard","Noto Sans KR",Arial,sans-serif; background:radial-gradient(circle at 12% 15%,#1d5d9b 0,transparent 32%),radial-gradient(circle at 88% 18%,#6b2d9c 0,transparent 30%),linear-gradient(135deg,#07152f,#102c58 48%,#160f37); color:#f8fbff; }
    .app { width:min(1240px,calc(100% - 48px)); height:min(820px,calc(100vh - 48px)); min-height:560px; margin:24px auto; display:grid; grid-template-rows:auto 1fr; background:linear-gradient(145deg,rgba(255,255,255,.18),rgba(255,255,255,.06)); border:1px solid rgba(255,255,255,.34); border-radius:22px; overflow:hidden; box-shadow:0 24px 80px rgba(0,0,0,.35); backdrop-filter:blur(22px); }
    header { padding:14px 22px; border-bottom:1px solid rgba(255,255,255,.2); background:rgba(7,21,47,.34); }
    .topbar { display:flex; align-items:center; justify-content:space-between; gap:16px; }
    .brand { display:flex; align-items:center; gap:10px; } .brand-mark { width:34px; height:34px; object-fit:contain; filter:drop-shadow(0 0 8px rgba(0,224,255,.7)); }
    .workspace { min-height:0; display:grid; grid-template-columns:190px minmax(0,1fr); }
    .sidebar { min-width:0; padding:22px 16px; background:rgba(5,16,38,.22); border-right:1px solid rgba(255,255,255,.14); }
    .mascot { display:block; width:130px; height:150px; object-fit:contain; margin:4px auto 16px; filter:drop-shadow(0 0 14px rgba(0,224,255,.55)); }
    .eyebrow { margin:0 0 10px; color:#7feeff; font-size:11px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
    .side-title { margin:0 0 18px; font-size:14px; line-height:1.45; } .hint { margin:0 0 10px; color:rgba(241,248,255,.65); font-size:11px; }
    .suggestion { width:100%; margin:6px 0; padding:8px 9px; border:1px solid rgba(255,255,255,.18); border-radius:9px; background:rgba(255,255,255,.08); color:#eefaff; font-size:11px; text-align:left; cursor:pointer; transition:.2s ease; }
    .suggestion:hover,.suggestion:focus-visible { background:rgba(0,224,255,.2); border-color:#55e9ff; outline:none; transform:translateY(-1px); }
    .insight-card { margin-bottom:12px; padding:13px; border:1px solid rgba(255,255,255,.38); border-radius:13px; background:rgba(255,255,255,.16); box-shadow:0 12px 24px rgba(0,0,0,.12); }
    .insight-card h2 { margin:0 0 7px; font-size:14px; } .insight-card p,.insight-card div { margin:0; color:rgba(241,248,255,.78); font-size:11px; line-height:1.55; }
    .conversation { min-width:0; min-height:0; display:grid; grid-template-rows:1fr auto; }
    h1 { margin:0 0 6px; font-size:clamp(22px,2.5vw,30px); letter-spacing:-.03em; } header p { margin:0; color:rgba(241,248,255,.76); font-size:15px; }
    #chat { min-height:0; overflow-y:auto; padding:28px clamp(20px,5vw,64px); background:rgba(4,14,35,.22); }
    .message { max-width:min(720px,82%); margin:12px 0; padding:12px 15px; border-radius:14px; white-space:pre-wrap; line-height:1.6; overflow-wrap:anywhere; }
    .message.loading,.message.bot { min-width:320px; color:#10213e; background:linear-gradient(145deg,rgba(177,247,255,.82),rgba(147,211,255,.52) 55%,rgba(204,171,255,.48)) !important; background-image:url('/assets/aurora-logo.png'),linear-gradient(145deg,rgba(177,247,255,.82),rgba(147,211,255,.52) 55%,rgba(204,171,255,.48)) !important; background-repeat:no-repeat; background-size:28px,cover; background-position:12px 13px,center; padding-left:50px; border:1px solid rgba(151,249,255,.8) !important; box-shadow:0 14px 34px rgba(0,0,0,.2); backdrop-filter:blur(16px); }
    .loading-copy { line-height:1.55; }
    .loading-sources { margin-top:12px; padding:10px 11px; border:1px solid rgba(255,255,255,.58); border-radius:12px; background:rgba(255,255,255,.28); }
    .loading-sources strong { display:block; margin-bottom:7px; font-size:13px; }
    .loading-sources div { margin:4px 0; font-size:11px; }
    .message.loading::after { content:""; display:inline-block; width:1.1em; animation:dots 1.2s steps(4,end) infinite; }
    @keyframes dots { 0% { content:""; } 25% { content:"."; } 50% { content:".."; } 75%,100% { content:"..."; } }
    .user { margin-left:auto; background:linear-gradient(135deg,rgba(0,224,255,.75),rgba(76,112,255,.65)); border:1px solid rgba(255,255,255,.35); }
    .source-box { margin-top:12px; padding:10px 11px; border:1px solid rgba(255,255,255,.62); border-radius:12px; background:rgba(255,255,255,.3); color:#173b5b; font-size:12px; }
    .source-box strong { display:block; margin-bottom:7px; color:#10213e; font-size:13px; }
    .answer-label { margin-bottom:8px; color:#173b5b; font-size:13px; font-weight:800; letter-spacing:.02em; }
    #error { display:none; margin:12px 18px 0; padding:10px 12px; border-radius:10px; background:rgba(255,108,140,.2); color:#ffe8ee; border:1px solid rgba(255,170,190,.45); font-size:14px; }
    .composer { display:flex; gap:10px; padding:18px clamp(18px,4vw,42px) 22px; background:rgba(5,16,38,.42); border-top:1px solid rgba(255,255,255,.18); }
    #question { flex:1; min-width:0; padding:13px 14px; border:1px solid rgba(255,255,255,.38); border-radius:12px; font-size:16px; outline:none; color:#f8fbff; background:rgba(255,255,255,.13); }
    #question::placeholder { color:rgba(241,248,255,.7); } #question:focus { border-color:#55e9ff; box-shadow:0 0 0 3px rgba(0,224,255,.18); }
    #sendButton { min-width:100px; padding:13px 18px; border:1px solid rgba(255,255,255,.35); border-radius:12px; background:linear-gradient(135deg,#00d9ff,#4d70ff); color:white; font-weight:700; cursor:pointer; box-shadow:0 8px 22px rgba(0,213,255,.24); }
    #question:disabled,#sendButton:disabled { opacity:.6; cursor:not-allowed; }
    @media (max-width:900px) { .app { width:min(900px,calc(100% - 32px)); height:min(800px,calc(100vh - 32px)); margin:16px auto; } .workspace { grid-template-columns:150px minmax(0,1fr); } #chat { padding-inline:28px; } }
    @media (max-width:600px) { body { background:linear-gradient(145deg,#07152f,#102c58 55%,#160f37); } .app { width:100%; height:100dvh; min-height:0; margin:0; border:0; border-radius:0; box-shadow:none; } header { padding:12px 14px; } .workspace { display:block; } .sidebar { display:none; } .conversation { height:calc(100dvh - 65px); } h1 { font-size:18px; } header p { display:none; } #chat { padding:18px 14px; } .message { max-width:90%; font-size:15px; } .composer { padding:12px 12px max(14px,env(safe-area-inset-bottom)); gap:8px; } #question { font-size:15px; padding:12px; } #sendButton { min-width:76px; padding:12px 10px; } }
  </style>
</head>
<body>
  <main class="app">
    <header><div class="topbar"><div class="brand"><img class="brand-mark" src="/assets/aurora-logo.png" alt="오로라 로고"><h1>오로라 모빌리티 사내 위키 QA</h1></div><span class="eyebrow">미래형 지식 도우미</span></div><p>사내 규정과 업무 안내를 질문해 보세요.</p></header>
    <div class="workspace">
      <aside class="sidebar"><img class="mascot" src="/assets/aurora-mascot.png" alt="오로라 안내 캐릭터"><p class="eyebrow">서비스</p><h2 class="side-title">오로라 모빌리티<br>사내 위키 QA</h2><p class="hint">예시 질문</p><button class="suggestion">연차는 매년 며칠 부여되나요?</button><button class="suggestion">VPN 연결에는 어떤 인증이 필요한가요?</button><button class="suggestion">국내 출장 교통비와 숙박비 정산 기준은 무엇인가요?</button></aside>
      <section class="conversation"><section id="chat" aria-live="polite"></section><div id="error" role="alert"></div><div class="composer"><input id="question" type="text" placeholder="질문을 입력하세요..." autocomplete="off"><button id="sendButton" type="button">전송</button></div></section>
    </div>
  </main>
  <script>
    // 엘리스 터널(/proxy/8000/)처럼 하위 경로에 마운트돼도 동작하도록 기준 경로를 계산한다.
    const BASE_PATH=window.location.pathname.replace(/[^\/]*$/,'');
    const chat=document.getElementById('chat');
    const questionInput=document.getElementById('question');
    const sendButton=document.getElementById('sendButton');
    const errorBox=document.getElementById('error');
    let isLoading=false;
    let activeStream=null;

    function scrollToBottom(){chat.scrollTop=chat.scrollHeight;}
    function appendMessage(role,text){
      const box=document.createElement('div'); box.className='message '+role;
      let label=null; if(role==='bot'){label=document.createElement('div'); label.className='answer-label'; label.textContent='답변 요약'; box.appendChild(label);}
      const textBox=document.createElement('div'); textBox.textContent=text;
      box.appendChild(textBox); chat.appendChild(box); scrollToBottom(); return {box,textBox};
    }
    function appendSources(container,sources){
      if(!Array.isArray(sources)||sources.length===0)return;
      const sourceBox=document.createElement('div'); sourceBox.className='source-box';
      const title=document.createElement('strong'); title.textContent='출처'; sourceBox.appendChild(title);
      [...new Set(sources)].forEach((source)=>{const item=document.createElement('div');item.textContent=source;sourceBox.appendChild(item);});
      container.appendChild(sourceBox); scrollToBottom();
    }
    function showError(message){
      errorBox.textContent=message||'';
      errorBox.style.display=message?'block':'none';
    }
    function setLoading(loading){
      isLoading=Boolean(loading);
      questionInput.disabled=isLoading;
      sendButton.disabled=isLoading;
      sendButton.textContent=isLoading?'답변 생성 중...':'전송';
    }
    function finishRequest(){
      if(activeStream){activeStream.close();activeStream=null;}
      setLoading(false); questionInput.focus();
    }
    function ask(){
      if(isLoading)return;
      const question=questionInput.value.trim();
      if(!question){showError('질문을 입력해 주세요.');return;}
      showError(''); appendMessage('user',question); questionInput.value=''; setLoading(true);
      const bot=appendMessage('bot',''); bot.box.classList.add('loading'); bot.label=bot.box.querySelector('.answer-label'); if(bot.label)bot.label.textContent='AI Thinking 중입니다.';
      bot.textBox.className='loading-copy'; bot.textBox.textContent='오로라 모빌리티 임직원을 위한 QA 시스템입니다.\n답변이 생성되는 중입니다...\n답변이 완료되면 이곳에 답변이 표시됩니다.\n답변이 길어질 수 있으니 잠시만 기다려주세요.';
      bot.loadingSources=document.createElement('div'); bot.loadingSources.className='loading-sources'; bot.loadingSources.innerHTML='<strong>출처</strong><div>◉ 오로라 모빌리티 사내 위키 QA</div>'; bot.box.appendChild(bot.loadingSources);
      activeStream=new EventSource(BASE_PATH+'stream?q='+encodeURIComponent(question));
      activeStream.addEventListener('chunk',(event)=>{
        const data=JSON.parse(event.data); if(bot.box.classList.contains('loading')){bot.box.classList.remove('loading'); bot.textBox.className=''; bot.textBox.textContent=''; if(bot.label)bot.label.textContent='답변 요약'; if(bot.loadingSources){bot.loadingSources.remove(); bot.loadingSources=null;}} bot.textBox.textContent+=data.text||''; scrollToBottom();
      });
      activeStream.addEventListener('sources',(event)=>{
        const data=JSON.parse(event.data); appendSources(bot.box,data.sources);
      });
      activeStream.addEventListener('done',()=>{finishRequest();});
      activeStream.addEventListener('app_error',(event)=>{
        let message='답변을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.';
        try{const data=JSON.parse(event.data);message=data.message||message;}catch(error){}
        if(!bot.textBox.textContent)bot.box.remove();
        showError(message);finishRequest();
      });
      activeStream.onerror=()=>{
        if(isLoading)showError('서버 연결이 끊어졌습니다. 잠시 후 다시 시도해 주세요.');
        finishRequest();
      };
    }
    sendButton.addEventListener('click',ask);
    questionInput.addEventListener('keydown',(event)=>{if(event.key==='Enter')ask();});
    document.querySelectorAll('.suggestion').forEach((button)=>button.addEventListener('click',()=>{questionInput.value=button.textContent.trim(); ask();}));
  </script>
</body>
</html>'''


PROXY_PREFIX=re.compile(r'^/proxy/\d+')


def normalize_path(raw_path):
    path=PROXY_PREFIX.sub('',urllib.parse.urlparse(raw_path).path)
    return path or '/'


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed=urllib.parse.urlparse(self.path)
        path=normalize_path(self.path)
        if path.startswith('/assets/'):
            asset = (ASSET_ROOT / path.removeprefix('/assets/')).resolve()
            if asset.is_file() and ASSET_ROOT in asset.parents:
                body=asset.read_bytes(); content_type='image/png' if asset.suffix.lower()=='.png' else 'application/octet-stream'
                self.send_response(200); self.send_header('Content-Type',content_type); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
            else: self._send_json(404,{'error':'not_found'})
        elif path in ('/','/index.html'): self._send_html(PAGE_HTML)
        elif path=='/stream': self._handle_stream(parsed.query)
        else: self._send_json(404,{'error':'not_found'})

    def do_POST(self):
        if normalize_path(self.path)!='/answer': self._send_json(404,{'error':'not_found'}); return
        try:
            length=int(self.headers.get('Content-Length','0'))
            payload=json.loads(self.rfile.read(length) or b'{}')
            question=payload.get('question','') if isinstance(payload,dict) else ''
            self._send_json(200,qa_service.answer(question))
        except (ValueError,json.JSONDecodeError): self._send_json(400,{'error':'invalid_json'})
        except Exception: self._send_json(500,{'error':'server_error'})

    def _handle_stream(self,query_string):
        params=urllib.parse.parse_qs(query_string)
        question=params.get('q',[''])[0]
        self.send_response(200)
        self.send_header('Content-Type','text/event-stream; charset=utf-8')
        self.send_header('Cache-Control','no-cache')
        self.send_header('Connection','close')
        self.end_headers()
        try:
            for message in stream_answer(question):
                self.wfile.write(message.encode('utf-8'))
                self.wfile.flush()
        except (BrokenPipeError,ConnectionResetError):
            pass
        finally:
            self.close_connection=True

    def _send_html(self,html):
        body=html.encode('utf-8'); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def _send_json(self,status,data):
        body=json.dumps(data,ensure_ascii=False).encode('utf-8'); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self,*args): pass


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address=True


def main():
    port=int(os.environ.get('PORT','8000'))
    public_url=os.environ.get('PUBLIC_URL','https://xtbyzccjswjtccsr.tunnel.elice.io/proxy/8000/')
    with Server(('0.0.0.0',port),Handler) as server:
        print(f'오로라 위키 QA 서버: {public_url}')
        print(f'로컬 주소: http://0.0.0.0:{port}')
        server.serve_forever()


if __name__=='__main__': main()
