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
    * { box-sizing: border-box; } html,body { overflow-x:hidden; }
    body { margin:0; min-height:100vh; font-family:"Spoqa Han Sans Neo","Pretendard","Noto Sans KR",Arial,sans-serif; background:radial-gradient(circle at 12% 15%,#1d5d9b 0,transparent 32%),radial-gradient(circle at 88% 18%,#6b2d9c 0,transparent 30%),linear-gradient(135deg,#07152f,#102c58 48%,#160f37); color:#f8fbff; }
    .app { width:min(1240px,calc(100% - 48px)); height:min(820px,calc(100vh - 48px)); min-height:560px; margin:24px auto; display:grid; grid-template-rows:auto 1fr; background:linear-gradient(145deg,rgba(255,255,255,.18),rgba(255,255,255,.06)); border:1px solid rgba(255,255,255,.34); border-radius:22px; overflow:hidden; box-shadow:0 24px 80px rgba(0,0,0,.35); backdrop-filter:blur(22px); }
    header { display:block; padding:10px 22px; border-bottom:1px solid rgba(255,255,255,.2); background:linear-gradient(90deg,rgba(30,91,145,.55),rgba(88,42,137,.5)); }
    header .brand { display:flex; } header .topbar { justify-content:space-between; } header p { display:none; }
    .topbar { display:flex; align-items:center; justify-content:space-between; gap:16px; }
    .brand { display:flex; align-items:center; gap:10px; } .brand-mark { content:url('/assets/aurora-logo.png'); width:68px; height:68px; object-fit:contain; filter:drop-shadow(0 0 10px rgba(0,224,255,.7)); } .brand h1 { display:block; }
    .slogan-wrap { width:min(300px,34vw); padding:7px 12px; border:1px solid rgba(255,255,255,.28); border-radius:13px; background:rgba(255,255,255,.12); backdrop-filter:blur(12px); }
    .slogan-image { width:100%; height:auto; display:block; object-fit:contain; }
    .workspace { min-height:0; display:grid; grid-template-columns:210px minmax(0,1fr); }
    .sidebar { min-width:0; padding:22px 16px; background:rgba(5,16,38,.22); border-right:1px solid rgba(255,255,255,.14); }
    .mascot { display:block; width:130px; height:150px; object-fit:contain; margin:4px auto 16px; filter:drop-shadow(0 0 14px rgba(0,224,255,.55)); }
    .wordmark { display:none; }
    .wordmark img { content:url('/assets/aurora-wordmark.png'); width:150px; height:auto; object-fit:contain; } .nav-item { display:block; width:100%; margin:5px 0; padding:9px 10px; border:1px solid transparent; border-radius:9px; background:transparent; color:#eefaff; font-size:12px; text-align:left; cursor:pointer; } .nav-item:hover,.nav-item:focus-visible,.nav-item.active { background:rgba(0,224,255,.16); border-color:rgba(127,238,255,.42); outline:none; }
    .wordmark span { display:none; }
    .wordmark small { font-size:8px; letter-spacing:.14em; opacity:.75; } .side-copy { margin:-10px 0 16px; color:rgba(241,248,255,.7); font-size:11px; line-height:1.45; }
    .mascot-card { position:relative; display:flex; align-items:center; min-height:78px; margin:20px 0 10px; padding:10px 8px 10px 72px; border:1px solid rgba(127,238,255,.3); border-radius:13px; background:linear-gradient(135deg,rgba(4,22,58,.88),rgba(19,55,104,.68)); color:#eefaff; font-size:11px; line-height:1.4; box-shadow:0 8px 20px rgba(0,0,0,.18); overflow:visible; }
    .mascot-card .mascot { position:absolute; left:-8px; bottom:-7px; width:82px; height:90px; margin:0; filter:drop-shadow(0 0 10px rgba(0,224,255,.42)); }
    .side-footer { width:170px; min-height:42px; margin-top:22px; padding:5px 0 5px 34px; background:url('/assets/aurora-logo.png') left center/26px no-repeat; color:rgba(241,248,255,.78); font-size:9px; line-height:1.25; letter-spacing:.04em; } .side-footer small { display:block; font-size:8px; opacity:.72; letter-spacing:0; }
    .eyebrow { margin:0 0 10px; color:#7feeff; font-size:11px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
    .eyebrow small { display:block; margin-top:4px; color:rgba(241,248,255,.68); font-size:9px; font-weight:500; letter-spacing:.02em; text-transform:none; }
    .side-title { margin:0 0 18px; font-size:14px; line-height:1.45; } .hint { margin:0 0 10px; color:rgba(241,248,255,.65); font-size:11px; }
    .suggestion { width:100%; margin:6px 0; padding:8px 9px; border:1px solid rgba(255,255,255,.18); border-radius:9px; background:rgba(255,255,255,.08); color:#eefaff; font-size:11px; text-align:left; cursor:pointer; transition:.2s ease; }
    .suggestion:hover,.suggestion:focus-visible { background:rgba(0,224,255,.2); border-color:#55e9ff; outline:none; transform:translateY(-1px); }
    .insight-card { margin-bottom:12px; padding:13px; border:1px solid rgba(255,255,255,.38); border-radius:13px; background:rgba(255,255,255,.16); box-shadow:0 12px 24px rgba(0,0,0,.12); }
    .insight-card h2 { margin:0 0 7px; font-size:14px; } .insight-card p,.insight-card div { margin:0; color:rgba(241,248,255,.78); font-size:11px; line-height:1.55; }
    .conversation { min-width:0; min-height:0; display:flex; flex-direction:column; }
    .main-banner { display:none; }
    .main-banner img { width:min(300px,60%); height:auto; display:inline-block; }
    h1 { margin:0 0 6px; font-size:clamp(22px,2.5vw,30px); letter-spacing:-.03em; } header p { margin:0; color:rgba(241,248,255,.76); font-size:15px; }
    #chat { flex:1; min-height:0; overflow-y:auto; padding:28px clamp(20px,5vw,64px); background:rgba(4,14,35,.22); }
    .message { max-width:min(720px,82%); margin:12px 0; padding:12px 15px; border-radius:14px; white-space:pre-wrap; line-height:1.6; overflow-wrap:anywhere; }
    .message.loading,.message.bot { min-width:320px; color:#10213e; background:linear-gradient(145deg,rgba(177,247,255,.82),rgba(147,211,255,.52) 55%,rgba(204,171,255,.48)) !important; background-repeat:no-repeat; background-size:cover; background-position:center; padding-left:50px; border:1px solid rgba(151,249,255,.8) !important; box-shadow:0 14px 34px rgba(0,0,0,.2); backdrop-filter:blur(16px); }
    .message.loading { background-image:url('/assets/aurora-logo.png'),linear-gradient(145deg,rgba(177,247,255,.82),rgba(147,211,255,.52) 55%,rgba(204,171,255,.48)) !important; background-size:28px,cover; background-position:12px 13px,center; padding-left:50px; }
    .message.bot { background-image:linear-gradient(145deg,rgba(177,247,255,.82),rgba(147,211,255,.52) 55%,rgba(204,171,255,.48)) !important; padding-left:15px; }
    .loading-copy { line-height:1.55; }
    .loading-sources { margin-top:12px; padding:10px 11px; border:1px solid rgba(255,255,255,.58); border-radius:12px; background:rgba(255,255,255,.28); }
    .loading-sources strong { display:block; margin-bottom:7px; font-size:13px; }
    .loading-sources div { margin:4px 0; font-size:11px; }
    .message.loading::after { content:""; display:inline-block; width:1.1em; animation:dots 1.2s steps(4,end) infinite; }
    @keyframes dots { 0% { content:""; } 25% { content:"."; } 50% { content:".."; } 75%,100% { content:"..."; } }
    .user { display:block; width:fit-content; max-width:min(720px,82%); margin:12px 0 12px auto; background:linear-gradient(135deg,rgba(0,224,255,.75),rgba(76,112,255,.65)); border:1px solid rgba(255,255,255,.35); }
    .bot { display:block; width:fit-content; max-width:min(720px,82%); margin:12px auto 12px 54px; position:relative; }
    .bot::before { content:""; position:absolute; left:-50px; top:5px; width:38px; height:38px; border-radius:50%; background:rgba(30,89,190,.85) url('/assets/aurora-logo.png') center/30px no-repeat; border:1px solid rgba(127,238,255,.55); box-shadow:0 0 18px rgba(0,224,255,.35); }
    .source-box { margin-top:12px; padding:10px 11px; border:1px solid rgba(255,255,255,.62); border-radius:12px; background:rgba(255,255,255,.3); color:#173b5b; font-size:12px; }
    .source-box strong { display:block; margin-bottom:7px; color:#10213e; font-size:13px; }
    .source-item { display:flex; justify-content:space-between; gap:12px; margin:7px 0; font-size:11px; } .source-item::after { content:"↗"; color:#1b71d1; font-size:15px; }
    .feedback { display:flex; align-items:center; gap:7px; margin-top:13px; color:#173b5b; font-size:10px; } .feedback button { display:inline-flex; align-items:center; gap:5px; border:1px solid rgba(23,59,91,.25); border-radius:8px; background:rgba(255,255,255,.22); color:#173b5b; padding:5px 8px; font-size:10px; cursor:pointer; } .feedback button svg { width:13px; height:13px; fill:none; stroke:currentColor; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round; } .feedback button:hover { background:rgba(0,224,255,.2); border-color:#075fc2; } .feedback span:last-child { margin-left:auto; font-size:10px; }
    .answer-label { margin-bottom:8px; color:#173b5b; font-size:13px; font-weight:800; letter-spacing:.02em; }
    #error { display:none; margin:12px 18px 0; padding:10px 12px; border-radius:10px; background:rgba(255,108,140,.2); color:#ffe8ee; border:1px solid rgba(255,170,190,.45); font-size:14px; }
    .composer { display:flex; gap:10px; padding:18px clamp(18px,4vw,42px) 22px; background:rgba(5,16,38,.42); border-top:1px solid rgba(255,255,255,.18); }
    #question { flex:1; min-width:0; padding:13px 14px; border:1px solid rgba(255,255,255,.38); border-radius:12px; font-size:16px; outline:none; color:#f8fbff; background:rgba(255,255,255,.13); }
    #question::placeholder { color:rgba(241,248,255,.7); } #question:focus { border-color:#55e9ff; box-shadow:0 0 0 3px rgba(0,224,255,.18); }
    #sendButton { min-width:100px; padding:13px 18px; border:1px solid rgba(255,255,255,.35); border-radius:12px; background:linear-gradient(135deg,#00d9ff,#4d70ff); color:white; font-weight:700; cursor:pointer; box-shadow:0 8px 22px rgba(0,213,255,.24); }
    #question:disabled,#sendButton:disabled { opacity:.6; cursor:not-allowed; }
    @media (max-width:900px) { .app { width:min(900px,calc(100% - 32px)); height:calc(100vh - 32px); min-height:0; margin:16px auto; } .workspace { grid-template-columns:150px minmax(0,1fr); } .sidebar { padding:16px 10px; } .mascot-card { min-height:64px; padding-left:58px; font-size:10px; } .mascot-card .mascot { width:66px; height:72px; } #chat { padding-inline:22px; } }
    @media (max-width:600px) { body { background:linear-gradient(145deg,#07152f,#102c58 55%,#160f37); } .app { width:100%; height:100dvh; min-height:0; margin:0; border:0; border-radius:0; box-shadow:none; display:flex; flex-direction:column; } header { display:block; flex:none; padding:8px 14px; } .brand-mark { width:48px; height:48px; } .brand h1 { font-size:18px; } .slogan-wrap { display:none; } .workspace { display:flex; flex:1; min-height:0; flex-direction:column; } .sidebar { display:block; flex:none; width:100%; height:auto; padding:9px 12px 8px; border-right:0; border-bottom:1px solid rgba(255,255,255,.16); white-space:normal; overflow:visible; } .sidebar .wordmark,.sidebar .side-title,.sidebar .side-copy,.sidebar .nav-item,.sidebar .side-footer { display:none; } .sidebar .mascot-card { display:flex; margin:0 0 8px; min-height:62px; } .sidebar .hint { display:block; margin:0 0 5px; } .sidebar .suggestion { display:block; width:100%; margin:5px 0; padding:7px 9px; white-space:normal; } .conversation { flex:1; min-height:0; height:auto; } #chat { padding:18px 14px; } .message { max-width:90%; font-size:15px; } .message.loading,.message.bot { min-width:0; } .bot { margin-left:44px; max-width:calc(100% - 44px); } .composer { flex:none; padding:12px 12px max(14px,env(safe-area-inset-bottom)); gap:8px; } #question { min-width:0; font-size:15px; padding:12px; } #sendButton { flex:none; min-width:76px; padding:12px 10px; } }
    @media (max-width:600px) { .sidebar { padding:3px 0 4px; } .sidebar .mascot-card { position:relative; width:100%; min-height:88px; height:88px; margin:0 0 4px; padding:0; overflow:hidden; } .sidebar .mascot-card .mascot { left:8px; bottom:-3px; width:72px; height:82px; } .sidebar .mascot-card span { position:absolute; left:82px; top:25px; width:calc(50% - 86px); white-space:normal; font-size:11px; font-weight:700; line-height:1.3; } .sidebar .mascot-card::after { content:'▱  답변 준비 완료\\A     사내 위키 5개 문서 검색 가능'; position:absolute; left:50%; right:6px; top:5px; bottom:5px; width:auto; padding:21px 6px 5px 9px; border:1px solid rgba(127,238,255,.22); border-radius:12px; background:linear-gradient(145deg,rgba(15,70,126,.66),rgba(18,47,98,.78)); color:#eafaff; white-space:pre-line; font-size:8px; line-height:1.4; } .sidebar .hint { margin:0 12px 2px; } .sidebar .suggestion { margin:2px 12px; width:calc(100% - 24px); padding:6px 8px; } .feedback button { font-size:0; min-width:34px; padding:6px; text-align:center; } .feedback button:nth-child(1)::after { content:'♡'; font-size:16px; } .feedback button:nth-child(2)::after { content:'×'; font-size:18px; } .feedback button:nth-child(3)::after { content:'⧉'; font-size:15px; } .feedback span:last-child { font-size:9px; } }
    @media (max-width:600px) { .feedback button::after { content:none !important; } .feedback-label { display:none; } .feedback button svg { width:16px; height:16px; } .sidebar { padding-top:0; padding-bottom:0; } .sidebar .mascot-card { height:120px; min-height:120px; margin-top:0; margin-bottom:0; aspect-ratio:auto; padding:0; border:1px solid rgba(127,238,255,.5); border-radius:14px; background:linear-gradient(145deg,rgba(4,27,67,.96),rgba(15,59,111,.88)); box-shadow:0 0 14px rgba(0,224,255,.25); } .sidebar .mascot-card > * { visibility:visible; } .sidebar .mascot-card .mascot { left:8px; bottom:-4px; width:88px; height:100px; } .sidebar .mascot-card span { position:absolute; left:96px; top:37px; width:calc(50% - 101px); font-size:12px; font-weight:700; line-height:1.35; } .sidebar .mascot-card::after { content:'▱  답변 준비 완료\\A     사내 위키 5개 문서 검색 가능'; position:absolute; left:50%; right:7px; top:8px; bottom:8px; padding:31px 7px 6px 12px; border:1px solid rgba(127,238,255,.25); border-radius:12px; background:rgba(28,84,145,.55); color:#eafaff; white-space:pre-line; font-size:9px; line-height:1.45; } .sidebar .hint { margin-top:2px; margin-bottom:1px; } .sidebar .suggestion { margin-top:1px; margin-bottom:1px; } }
    @media (max-width:600px) { .sidebar .mascot-card::after { content:'▤\\A답변 준비 완료\\A사내 위키 5개 문서가\\A연결되어 있어요.'; padding-top:10px; padding-left:10px; font-size:9px; } }
    @media (max-width:600px) { header { padding:10px 14px; } .brand-mark { width:48px; height:48px; } .brand h1 { font-size:18px; letter-spacing:-.04em; } .sidebar .mascot-card { height:120px !important; min-height:120px !important; aspect-ratio:auto !important; background:url('/assets/mobile-mascot-status.png') center/100% 100% no-repeat !important; border:0 !important; border-radius:0 !important; } .sidebar .hint { margin:6px 12px 3px; font-size:12px; } .sidebar .suggestion { min-height:44px; margin:4px 12px; width:calc(100% - 24px); padding:8px 10px; border-radius:10px; font-size:12px; } .conversation { min-height:300px; } }
    @media (max-width:600px) { .sidebar .mascot-card { height:auto !important; min-height:0 !important; aspect-ratio:705 / 174 !important; background:url('/assets/mobile-mascot-status.png') center/100% 100% no-repeat !important; border:0 !important; box-shadow:none !important; } .sidebar .mascot-card > *, .sidebar .mascot-card::after { visibility:hidden !important; display:none !important; } }
  </style>
</head>
<body>
  <main class="app">
    <header><div class="topbar"><div class="brand"><img class="brand-mark" src="/assets/aurora-logo.png" alt="오로라 로고"><h1>오로라 모빌리티 사내 위키 QA</h1></div><div class="slogan-wrap"><img class="slogan-image" src="/assets/aurora-slogan.png" alt="이동의 미래를 만드는 지식 파트너 Knowledge Partner for the Future of Mobility"></div></div><p>사내 규정과 업무 안내를 질문해 보세요.</p></header>
    <div class="workspace">
      <aside class="sidebar"><div class="wordmark"><img src="/assets/aurora-logo.png" alt="오로라 로고"><span>AURORA<br><small>MOBILITY</small></span></div><h2 class="side-title">Wiki QA</h2><p class="side-copy">사내 지식을 더 빠르게,<br>더 스마트하게</p><button class="nav-item active" data-action="home">⌂　홈</button><button class="nav-item" data-action="search">⌕　문서 검색</button><button class="nav-item" data-action="favorites">☆　즐겨찾기</button><button class="nav-item" data-action="recent">◷　최근 대화</button><button class="nav-item" data-action="help">?　서비스 안내</button><div class="mascot-card"><img class="mascot" src="/assets/aurora-mascot.png" alt="오로라 안내 캐릭터"><span>궁금한 내용을<br>물어보세요!</span></div><p class="hint">예시 질문</p><button class="suggestion">연차는 매년 며칠 부여되나요?</button><button class="suggestion">사용하지 않은 연차는 며칠까지 이월할 수 있나요?</button><button class="suggestion">국내 출장 교통비와 숙박비 정산 기준은 무엇인가요?</button><div class="side-footer">AURORA MOBILITY<br><small>Better Movement<br>for a Brighter Tomorrow</small></div></aside>
      <section class="conversation"><div class="main-banner"><img src="/assets/aurora-slogan.png" alt="이동의 미래를 만드는 지식 파트너"></div><section id="chat" aria-live="polite"></section><div id="error" role="alert"></div><div class="composer"><input id="question" type="text" placeholder="질문을 입력하세요..." autocomplete="off"><button id="sendButton" type="button">전송</button></div></section>
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
      const textBox=document.createElement('div'); if(role==='bot')textBox.className='answer-body'; textBox.textContent=text;
      box.appendChild(textBox); chat.appendChild(box); scrollToBottom(); return {box,textBox};
    }
    function appendSources(container,sources,questionText,answerText){
      if(!Array.isArray(sources)||sources.length===0)return;
      const sourceBox=document.createElement('div'); sourceBox.className='source-box';
      const title=document.createElement('strong'); title.textContent='출처'; sourceBox.appendChild(title);
      const labels={'company-overview':'회사소개','hr-policy':'인사부','it-guide':'IT지원','security-policy':'보안팀','travel-policy':'출장관리'};
      [...new Set(sources)].forEach((source)=>{const match=String(source).match(/^kb:([^#]+)#(.+)$/); const label=match?`${labels[match[1]]||match[1]}-${match[2]}`:String(source); const item=document.createElement('div');item.className='source-item';item.textContent=label;sourceBox.appendChild(item);});
      const feedback=document.createElement('div'); feedback.className='feedback'; feedback.innerHTML='<button type="button" data-rating="like"><span class="feedback-label">좋아요</span></button><button type="button" data-rating="dislike"><span class="feedback-label">싫어요</span></button><button type="button" data-copy="1"><span class="feedback-label">복사</span></button><span>이 답변이 도움이 되었나요?</span>'; container.appendChild(feedback);
      const buttons=feedback.querySelectorAll('button'); buttons[0].addEventListener('click',()=>saveFeedback('good')); buttons[1].addEventListener('click',()=>saveFeedback('bad')); buttons[2].addEventListener('click',async()=>{try{await navigator.clipboard.writeText(container.querySelector('.answer-body')?.textContent.trim()||''); }finally{feedback.remove();}});
      function saveFeedback(rating){const payload={question:questionText,answer:answerText,source:[...container.querySelectorAll('.source-item')].map((item)=>item.textContent).join(', '),rating}; feedback.remove(); fetch(BASE_PATH+'feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).catch(()=>{});}
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
      bot.textBox.className='loading-copy'; bot.textBox.textContent='오로라 모빌리티 사내 위키 QA입니다.\n답변을 생성하고 있습니다.\n잠시만 기다려주세요.';
      bot.loadingSources=document.createElement('div'); bot.loadingSources.className='loading-sources'; bot.loadingSources.innerHTML='<strong>출처</strong><div>◉ 오로라 모빌리티 사내 위키 QA</div>'; bot.box.appendChild(bot.loadingSources);
      activeStream=new EventSource(BASE_PATH+'stream?q='+encodeURIComponent(question));
      activeStream.addEventListener('chunk',(event)=>{
        const data=JSON.parse(event.data); if(bot.box.classList.contains('loading')){bot.box.classList.remove('loading'); bot.textBox.className=''; bot.textBox.textContent=''; if(bot.label)bot.label.textContent='답변 요약'; if(bot.loadingSources){bot.loadingSources.remove(); bot.loadingSources=null;}} bot.textBox.textContent+=data.text||''; scrollToBottom();
      });
      activeStream.addEventListener('sources',(event)=>{
        const data=JSON.parse(event.data); appendSources(bot.box,data.sources,question,bot.textBox.textContent);
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
    const navMessages={favorites:'즐겨찾기 기능을 준비 중입니다.',recent:'최근 대화 기능을 준비 중입니다.',help:'이 서비스는 사내 위키 문서를 바탕으로 답변합니다.'};
    document.querySelectorAll('.nav-item').forEach((button)=>button.addEventListener('click',()=>{document.querySelectorAll('.nav-item').forEach((item)=>item.classList.remove('active'));button.classList.add('active'); const action=button.dataset.action; if(action==='home'){showError(''); chat.scrollTop=0;} else if(action==='search'){questionInput.focus(); questionInput.placeholder='문서 내용을 질문해 보세요...';} else {showError(navMessages[action]||'');}}));
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
