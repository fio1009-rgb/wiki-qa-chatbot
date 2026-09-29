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

import qa_service


EMPTY_MESSAGE = "질문을 입력해 주세요."
ERROR_MESSAGE = "답변을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."


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
    body { margin:0; min-height:100vh; font-family:Arial,sans-serif; background:#f4f6f8; color:#1f2937; }
    .app { width:min(760px,calc(100% - 32px)); margin:32px auto; background:white; border:1px solid #d9dee5; border-radius:14px; overflow:hidden; }
    header { padding:20px 22px; border-bottom:1px solid #e5e7eb; }
    h1 { margin:0 0 6px; font-size:22px; } header p { margin:0; color:#6b7280; font-size:14px; }
    #chat { height:460px; overflow-y:auto; padding:20px; background:#fafafa; }
    .message { max-width:82%; margin:10px 0; padding:11px 13px; border-radius:12px; white-space:pre-wrap; line-height:1.5; }
    .user { margin-left:auto; background:#dbeafe; } .bot { margin-right:auto; background:white; border:1px solid #e5e7eb; }
    .source-box { margin-top:9px; padding-top:8px; border-top:1px solid #e5e7eb; color:#4b5563; font-size:12px; }
    #error { display:none; margin:12px 18px 0; padding:10px 12px; border-radius:8px; background:#fef2f2; color:#b91c1c; font-size:14px; }
    .composer { display:flex; gap:8px; padding:16px 18px 18px; }
    #question { flex:1; min-width:0; padding:11px 12px; border:1px solid #cbd5e1; border-radius:8px; font-size:15px; }
    #sendButton { min-width:92px; padding:11px 16px; border:0; border-radius:8px; background:#2563eb; color:white; font-weight:700; cursor:pointer; }
    #question:disabled,#sendButton:disabled { opacity:.6; cursor:not-allowed; }
    @media (max-width:560px) { .app{width:100%;min-height:100vh;margin:0;border:0;border-radius:0} #chat{height:calc(100vh - 190px)} .message{max-width:90%} }
  </style>
</head>
<body>
  <main class="app">
    <header><h1>오로라 모빌리티 사내 위키 QA</h1><p>사내 규정과 업무 안내를 질문해 보세요.</p></header>
    <section id="chat" aria-live="polite"></section>
    <div id="error" role="alert"></div>
    <div class="composer"><input id="question" type="text" placeholder="질문을 입력하세요" autocomplete="off"><button id="sendButton" type="button">전송</button></div>
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
      const textBox=document.createElement('div'); textBox.textContent=text;
      box.appendChild(textBox); chat.appendChild(box); scrollToBottom(); return {box,textBox};
    }
    function appendSources(container,sources){
      if(!Array.isArray(sources)||sources.length===0)return;
      const sourceBox=document.createElement('div'); sourceBox.className='source-box';
      const title=document.createElement('strong'); title.textContent='출처'; sourceBox.appendChild(title);
      sources.forEach((source)=>{const item=document.createElement('div');item.textContent=source;sourceBox.appendChild(item);});
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
      const bot=appendMessage('bot','');
      activeStream=new EventSource(BASE_PATH+'stream?q='+encodeURIComponent(question));
      activeStream.addEventListener('chunk',(event)=>{
        const data=JSON.parse(event.data); bot.textBox.textContent+=data.text||''; scrollToBottom();
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
        if path in ('/','/index.html'): self._send_html(PAGE_HTML)
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
