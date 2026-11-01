# -*- coding: utf-8 -*-
"""
arcade.py —— 真正可玩的小游戏（自包含 HTML/Canvas/JS，嵌在 Streamlit 里跑）

为什么用 HTML 组件而不是 Streamlit 原生控件：
Streamlit 每次交互都要整页重跑（几百毫秒延迟），做不了需要实时判定的游戏。
这些游戏在自己的 iframe 里用 requestAnimationFrame 跑，手感是真的。

四个游戏：
1) rhythm_html()  下落式节奏判定：4 轨 / D F J K / 判定窗口 / 连击 / 评级
2) merge_html()   maimai 2048：难度等级合并 BASIC→ADVANCED→…→Re:MASTER→宴…
3) tap_html()     打 NOTE：反应力 + 手速，30 秒限时
4) memory_html()  曲名记忆翻牌：用真实曲库曲名，记步数/用时

合规：不加载任何外部资源、不使用任何受版权保护的音频/图像，
音效全部用 Web Audio API 实时合成（正弦/方波 + 包络），离线可用。
"""
from __future__ import annotations

import json

# ---------------------------------------------------------------- 公共样式
_BASE_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d1117;color:#e6f1f0;font-family:"Segoe UI","Microsoft YaHei",sans-serif;
  padding:10px;-webkit-user-select:none;user-select:none}
.wrap{max-width:520px;margin:0 auto;text-align:center}
.hud{display:flex;justify-content:space-between;gap:8px;margin-bottom:8px;font-size:13px}
.hud div{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.09);
  border-radius:10px;padding:6px 10px;flex:1}
.hud b{display:block;font-size:17px;color:#39C5BB;line-height:1.3}
canvas{background:#080b0f;border:1px solid rgba(255,255,255,.1);border-radius:14px;display:block;margin:0 auto}
.btns{margin-top:10px;display:flex;gap:8px;justify-content:center;flex-wrap:wrap}
button{background:#39C5BB;color:#04222a;border:0;border-radius:10px;padding:8px 16px;
  font-weight:700;cursor:pointer;font-size:13px}
button.alt{background:rgba(255,255,255,.08);color:#cfe6e4}
button:hover{filter:brightness(1.12)}
.tip{font-size:12px;color:#7f8f96;margin-top:8px;line-height:1.7}
.center{position:absolute;left:0;right:0;top:44%;font-size:22px;font-weight:800;
  pointer-events:none;text-shadow:0 2px 10px rgba(0,0,0,.6)}
.stage{position:relative}
.panel{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);
  border-radius:14px;padding:14px;margin-top:10px;font-size:13px;line-height:1.8}
.big{font-size:26px;font-weight:800;color:#39C5BB;letter-spacing:2px}
"""


def _wrap(body: str, extra_css: str = "") -> str:
    return ("<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<style>" + _BASE_CSS + extra_css + "</style></head><body>" + body + "</body></html>")


def _store(key: str) -> str:
    """localStorage 在部分 iframe 沙箱里不可用，全部包 try/catch，失败退化为内存。"""
    return ("function __get(k,d){try{var v=localStorage.getItem(k);return v===null?d:v}catch(e){return (window.__m&&window.__m[k])||d}}"
            "function __set(k,v){try{localStorage.setItem(k,v)}catch(e){window.__m=window.__m||{};window.__m[k]=v}}")


# 节奏判定的两套皮肤（普通版 / 隐藏「心跳节拍」）
RHYTHM_SKINS = {
    "std":   {"lanes": ['#39C5BB', '#F5D442', '#E5484D', '#A66BFF'], "line": '#39C5BB',
              "tip": "键盘 <b>D F J K</b> 对应四条轨道，也可以直接用鼠标/触屏点对应区域。<br>"
                     "点一下游戏区让它获得焦点，键盘才生效。判定窗口："
                     "CRITICAL ±45ms / PERFECT ±90ms / GREAT ±150ms / GOOD ±220ms。"},
    "heart": {"lanes": ['#FF8FB1', '#FFD166', '#FF6B81', '#C77DFF'], "line": '#FF8FB1',
              "tip": "这一版是留给你的：判定线是暖色的，NOTE 落下来的节奏也慢一点。<br>"
                     "不用追求 SSS+，能一直连下去就行。"},
}


# ================================================================ 1) 节奏判定
def rhythm_html(height: int = 620, skin: str = "std") -> str:
    sk = RHYTHM_SKINS.get(skin, RHYTHM_SKINS["std"])
    body = """
<div class="wrap">
  <div class="hud">
    <div>连击<b id="combo">0</b></div>
    <div>准确率<b id="acc">100.00%</b></div>
    <div>得分<b id="score">0</b></div>
    <div>最佳<b id="best">—</b></div>
  </div>
  <div class="stage">
    <canvas id="cv" width="360" height="440"></canvas>
    <div class="center" id="judge"></div>
  </div>
  <div class="btns">
    <button id="go">▶ 开始</button>
    <button class="alt" id="dif">难度：NORMAL</button>
    <button class="alt" id="restart">↻ 重来</button>
  </div>
  <div class="panel" id="result" style="display:none"></div>
  <div class="tip">__TIP__</div>
</div>
<script>
__STORE__
var cv=document.getElementById('cv'),ctx=cv.getContext('2d');
var W=cv.width,H=cv.height,JY=H-64,LW=W/4,LEAD=1400;
var LANECOL=__LANES__;
var LINECOL='__LINE__';
var KEYS={d:0,f:1,j:2,k:3};
var DIFS=[{name:'EASY',bpm:88,step:2,chord:0},{name:'NORMAL',bpm:118,step:2,chord:0.08},
          {name:'HARD',bpm:150,step:1,chord:0.18}];
var di=1,notes=[],t0=0,run=false,done=0,total=0,combo=0,mx=0,score=0,accSum=0,judged=0;
var ac=null,lastBeat=-1;

function audio(){ if(!ac){try{ac=new (window.AudioContext||window.webkitAudioContext)()}catch(e){ac=null}} return ac }
function blip(f,dur,type,vol){ var a=audio(); if(!a) return;
  var o=a.createOscillator(),g=a.createGain();
  o.type=type||'sine'; o.frequency.value=f;
  g.gain.setValueAtTime(0,a.currentTime);
  g.gain.linearRampToValueAtTime(vol||0.18,a.currentTime+0.006);
  g.gain.exponentialRampToValueAtTime(0.0001,a.currentTime+dur);
  o.connect(g); g.connect(a.destination); o.start(); o.stop(a.currentTime+dur+0.02); }

function build(){ var d=DIFS[di],beat=60000/d.bpm,step=beat/ (d.step==1?1:2);
  notes=[]; var t=1800,last=-1;
  for(var i=0;i<130;i++){
    var ln=Math.floor(Math.random()*4); if(ln===last&&Math.random()<0.7) ln=(ln+1+Math.floor(Math.random()*3))%4;
    last=ln; notes.push({t:t,lane:ln,hit:false,jud:false});
    if(Math.random()<d.chord){ var l2=(ln+2+Math.floor(Math.random()*2))%4; notes.push({t:t,lane:l2,hit:false,jud:false}); }
    t+=step*(Math.random()<0.18?2:1);
  }
  total=notes.length; }

function fmt(n){ return n<10?'0'+n:''+n }
function upd(){ document.getElementById('combo').textContent=combo;
  document.getElementById('score').textContent=score;
  document.getElementById('acc').textContent=(judged?(accSum/judged*100).toFixed(2):'100.00')+'%'; }

function end(){ run=false;
  var acc=judged?(accSum/judged*100):0;
  var rank = acc>=99?'SSS+':acc>=97?'SSS':acc>=94?'SS':acc>=90?'S':acc>=80?'A':acc>=70?'B':acc>=60?'C':'D';
  var best=parseFloat(__get('mph_rhythm_'+DIFS[di].name,'0'))||0;
  var isNew=false; if(score>best){ best=score; __set('mph_rhythm_'+DIFS[di].name,String(score)); isNew=true }
  document.getElementById('best').textContent=best?String(best):'—';
  var r=document.getElementById('result'); r.style.display='block';
  r.innerHTML='<div class="big">'+rank+'</div>准确率 '+acc.toFixed(2)+'%　·　最大连击 '+mx
    +'　·　得分 '+score+(isNew?'　<span style="color:#F5D442">★ 新纪录</span>':'')
    +'<br><span style="color:#7f8f96">难度 '+DIFS[di].name+' · BPM '+DIFS[di].bpm+' · '+total+' NOTE</span>';
}

function judge(n,dt){ var a=Math.abs(dt),w,j,txt,col;
  if(a<=45){w=1.0;j='CRITICAL PERFECT';col='#39C5BB'}
  else if(a<=90){w=0.92;j='PERFECT';col='#7ee0d6'}
  else if(a<=150){w=0.72;j='GREAT';col='#F5D442'}
  else if(a<=220){w=0.5;j='GOOD';col='#E5A33D'}
  else {w=0;j='MISS';col='#E5484D'}
  combo = w>0 ? combo+1 : 0; if(combo>mx) mx=combo;
  score += Math.round(300*w) + (w>0?combo*2:0);
  accSum+=w; judged++; n.jud=true; n.hit=w>0; done++;
  blip(w>0?(660+combo%5*40):150, 0.07, 'square', w>0?0.13:0.1);
  var el=document.getElementById('judge'); el.textContent=j; el.style.color=col;
  el.style.opacity=1; clearTimeout(el._t); el._t=setTimeout(function(){el.style.opacity=0},420);
  upd(); }

function press(lane){ if(!run) return;
  var now=performance.now()-t0,best=null,bd=1e9;
  for(var i=0;i<notes.length;i++){ var n=notes[i];
    if(n.jud||n.lane!==lane) continue; var d=Math.abs(n.t-now);
    if(d<bd){bd=d;best=n} }
  if(best&&bd<=220) judge(best,best.t-now);
  flash(lane); }

function flash(l){ var x=l*LW; var g=ctx.createLinearGradient(0,JY-90,0,JY);
  g.addColorStop(0,'rgba(255,255,255,0)'); g.addColorStop(1,LANECOL[l].replace(')',',.35)').replace('rgb','rgba'));
  ctx.fillStyle=g; ctx.fillRect(x,JY-90,LW,90); }

function loop(){ requestAnimationFrame(loop);
  ctx.clearRect(0,0,W,H);
  for(var l=0;l<4;l++){ ctx.fillStyle='rgba(255,255,255,.03)'; ctx.fillRect(l*LW,0,LW-2,H); }
  ctx.fillStyle=LINECOL; ctx.fillRect(0,JY,W,3);
  ctx.fillStyle='rgba(255,255,255,.14)';
  for(var l2=0;l2<4;l2++){ ctx.fillRect(l2*LW+8,JY-34,LW-18,30); }
  ctx.font='11px sans-serif'; ctx.fillStyle='rgba(255,255,255,.35)';
  var ks=['D','F','J','K']; for(var l3=0;l3<4;l3++){ ctx.fillText(ks[l3],l3*LW+LW/2-3,JY-14) }
  if(!run){ return }
  var now=performance.now()-t0;
  var bi=Math.floor(now/(60000/DIFS[di].bpm));
  if(bi!==lastBeat){ lastBeat=bi; blip(120,0.05,'triangle',0.05) }
  for(var i=0;i<notes.length;i++){ var n=notes[i];
    var y=JY-((n.t-now)/LEAD)*(JY+40);
    if(y<-40||y>H+40) continue;
    if(!n.jud&&now-n.t>220){ judge(n,999) }
    if(n.jud&&n.hit) continue;
    ctx.fillStyle=LANECOL[n.lane];
    ctx.beginPath(); ctx.arc(n.lane*LW+LW/2,y,15,0,7); ctx.fill();
    ctx.strokeStyle='rgba(255,255,255,.5)'; ctx.lineWidth=2; ctx.stroke();
  }
  if(done>=total&&run) end();
}

document.addEventListener('keydown',function(e){ var k=(e.key||'').toLowerCase();
  if(k in KEYS){ press(KEYS[k]); e.preventDefault() } });
cv.addEventListener('pointerdown',function(e){ var r=cv.getBoundingClientRect();
  var x=(e.clientX-r.left)*(W/r.width); press(Math.max(0,Math.min(3,Math.floor(x/LW)))); });

function start(){ build(); combo=0;mx=0;score=0;accSum=0;judged=0;done=0;lastBeat=-1;
  audio(); run=true; t0=performance.now();
  document.getElementById('result').style.display='none'; upd();
  document.getElementById('best').textContent=__get('mph_rhythm_'+DIFS[di].name,'0')||'—'; }
document.getElementById('go').onclick=function(){ if(!run) start() };
document.getElementById('restart').onclick=start;
document.getElementById('dif').onclick=function(){ di=(di+1)%3;
  this.textContent='难度：'+DIFS[di].name; start(); };
document.getElementById('best').textContent=__get('mph_rhythm_'+DIFS[di].name,'0')||'—';
build(); loop();
</script>
"""
    body = (body.replace("__STORE__", _store("mph_rhythm"))
                .replace("__LANES__", json.dumps(sk["lanes"]))
                .replace("__LINE__", sk["line"])
                .replace("__TIP__", sk["tip"]))
    return _wrap(body, ".stage{width:360px;margin:0 auto}")


# ================================================================ 2) maimai 2048
def merge_html(height: int = 700) -> str:
    body = """
<div class="wrap">
  <div class="hud">
    <div>得分<b id="sc">0</b></div>
    <div>最高等级<b id="lv">—</b></div>
    <div>最佳<b id="best">0</b></div>
  </div>
  <div class="stage"><canvas id="cv" width="380" height="380"></canvas></div>
  <div class="btns">
    <button id="new">↻ 新开一局</button>
    <button class="alt" id="undo">↩ 撤销一步</button>
  </div>
  <div class="panel" id="msg" style="display:none"></div>
  <div class="tip">方向键 / WASD / 手机滑动都可以。<br>
  方块就是难度：<b>BASIC → ADVANCED → EXPERT → MASTER → Re:MASTER → 宴 → …</b>，合到「宴」就算你厉害。</div>
</div>
<script>
__STORE__
var cv=document.getElementById('cv'),ctx=cv.getContext('2d'),N=4,S=95,P=8;
var TIERS=['','BASIC','ADVANCED','EXPERT','MASTER','Re:MASTER','宴','宴+','宴++','宴+++','宴++++','真·宴','里·宴'];
var COLORS=['','#22c55e','#F5D442','#E5484D','#A66BFF','#e8eef5','#f97316','#fb923c','#fdba74','#fed7aa','#ffedd5','#39C5BB','#7dd3fc'];
var g=[],score=0,best=parseFloat(__get('mph_2048','0'))||0,prev=null,over=false;
document.getElementById('best').textContent=best;

function rnd(){ return Math.random()<0.9?1:2 }
function empty(){ var e=[]; for(var r=0;r<N;r++)for(var c=0;c<N;c++) if(!g[r][c]) e.push([r,c]); return e }
function add(){ var e=empty(); if(!e.length) return false;
  var p=e[Math.floor(Math.random()*e.length)]; g[p[0]][p[1]]=rnd(); return true }
function init(){ g=[]; for(var r=0;r<N;r++){ g.push([0,0,0,0]) } score=0; over=false; prev=null;
  add(); add(); draw(); document.getElementById('msg').style.display='none' }
function clone(a){ return a.map(function(x){return x.slice()}) }

function slide(line){ var a=line.filter(function(v){return v}),out=[],i,gained=0;
  for(i=0;i<a.length;i++){ if(i+1<a.length&&a[i]===a[i+1]&&a[i]<12){ out.push(a[i]+1); gained+=Math.pow(2,a[i]+1); i++ }
    else out.push(a[i]) }
  while(out.length<N) out.push(0); return {line:out,gained:gained} }

function move(dir){ if(over) return;
  var snap=clone(g),ss=score,moved=false,gain=0,lines=[];
  var idx=[]; for(var i=0;i<N;i++) idx.push(i);
  for(var k=0;k<N;k++){
    var line=[],cells=[];
    for(var j=0;j<N;j++){
      var r,c;
      // 取出"要压缩的那条线"：up=列从上到下 / down=列从下到上 / left=行从左到右 / right=行从右到左
      if(dir===0){r=j;c=k} else if(dir===2){r=N-1-j;c=k} else if(dir===3){r=k;c=j} else {r=k;c=N-1-j}
      line.push(g[r][c]); cells.push([r,c]);
    }
    var res=slide(line); gain+=res.gained;
    for(var j2=0;j2<N;j2++){ if(g[cells[j2][0]][cells[j2][1]]!==res.line[j2]) moved=true;
      g[cells[j2][0]][cells[j2][1]]=res.line[j2] }
  }
  if(!moved) return;
  score+=gain; prev={g:snap,score:ss}; add(); draw();
  if(score>best){ best=score; __set('mph_2048',String(score)) }
  document.getElementById('best').textContent=best;
  if(!canMove()){ over=true;
    var m=document.getElementById('msg'); m.style.display='block';
    m.innerHTML='<div class="big">GAME OVER</div>本局得分 '+score+'　·　历史最佳 '+best
      +'<br><span style="color:#7f8f96">没有可以合并的方向了，再来一局？</span>'; }
}
function canMove(){ for(var r=0;r<N;r++)for(var c=0;c<N;c++){ var v=g[r][c];
  if(!v) return true;
  if(c+1<N&&g[r][c+1]===v) return true; if(r+1<N&&g[r+1][c]===v) return true } return false }

function rr(x,y,w,h,r){ ctx.beginPath(); ctx.moveTo(x+r,y); ctx.arcTo(x+w,y,x+w,y+h,r);
  ctx.arcTo(x+w,y+h,x,y+h,r); ctx.arcTo(x,y+h,x,y,r); ctx.arcTo(x,y,x+w,y,r); ctx.closePath() }

function draw(){ ctx.clearRect(0,0,380,380);
  ctx.fillStyle='#0b1016'; rr(0,0,380,380,14); ctx.fill();
  var top=0;
  for(var r=0;r<N;r++)for(var c=0;c<N;c++){ var v=g[r][c];
    var x=P+c*(S+P),y=P+r*(S+P);
    ctx.fillStyle=v?'rgba(255,255,255,.04)':'rgba(255,255,255,.03)'; rr(x,y,S,S,10); ctx.fill();
    if(!v) continue;
    if(v>top) top=v;
    ctx.fillStyle=COLORS[v]||'#39C5BB'; rr(x,y,S,S,10); ctx.fill();
    ctx.fillStyle = (v>=5&&v<=10)?'#1a1005':'#08121a';
    var nm=TIERS[v]||('Lv'+v), fs = nm.length>7?10:(nm.length>4?13:15);
    ctx.font='700 '+fs+'px "Segoe UI",sans-serif'; ctx.textAlign='center';
    ctx.fillText(nm, x+S/2, y+S/2+fs/3);
  }
  document.getElementById('sc').textContent=score;
  document.getElementById('lv').textContent = top? (TIERS[top]||('Lv'+top)) : '—';
}

document.addEventListener('keydown',function(e){ var k=e.key;
  var d = (k==='ArrowUp'||k==='w'||k==='W')?0 : (k==='ArrowRight'||k==='d'||k==='D')?1
        : (k==='ArrowDown'||k==='s'||k==='S')?2 : (k==='ArrowLeft'||k==='a'||k==='A')?3 : -1;
  if(d>=0){ move(d); e.preventDefault() } });
var sx=0,sy=0;
cv.addEventListener('pointerdown',function(e){ sx=e.clientX; sy=e.clientY });
cv.addEventListener('pointerup',function(e){ var dx=e.clientX-sx, dy=e.clientY-sy;
  if(Math.abs(dx)<24&&Math.abs(dy)<24) return;
  move(Math.abs(dx)>Math.abs(dy)?(dx>0?1:3):(dy>0?2:0)) });
document.getElementById('new').onclick=init;
document.getElementById('undo').onclick=function(){ if(!prev) return;
  g=clone(prev.g); score=prev.score; prev=null; over=false;
  document.getElementById('msg').style.display='none'; draw() };
init();
</script>
"""
    return _wrap(body.replace("__STORE__", _store("mph_2048")), ".stage{width:380px;margin:0 auto}")


# ================================================================ 3) 打 NOTE（反应力）
def tap_html(height: int = 560) -> str:
    body = """
<div class="wrap">
  <div class="hud">
    <div>剩余<b id="time">30.0</b></div>
    <div>命中<b id="hit">0</b></div>
    <div>连击<b id="combo">0</b></div>
    <div>最佳<b id="best">0</b></div>
  </div>
  <div class="stage"><canvas id="cv" width="360" height="360"></canvas></div>
  <div class="btns"><button id="go">▶ 开始（30 秒）</button></div>
  <div class="panel" id="msg" style="display:none"></div>
  <div class="tip">NOTE 亮起来就点它，越快分越高。<b>红的是假 NOTE</b>，点中直接断连击。<br>
  手速与眼力的小训练，30 秒一局，适合等人/等车的时候消磨。</div>
</div>
<script>
__STORE__
var cv=document.getElementById('cv'),ctx=cv.getContext('2d'),N=3,S=110,P=15;
var cells=[],run=false,endAt=0,hits=0,combo=0,mx=0,best=parseInt(__get('mph_tap','0'))||0;
var cur=-1,curT=0,fake=false,nextAt=0;
document.getElementById('best').textContent=best;

function place(){ var i=Math.floor(Math.random()*N*N); if(i===cur&&N*N>1) i=(i+1)%(N*N);
  cur=i; curT=performance.now(); fake=Math.random()<0.18; nextAt=curT+(700-Math.min(400,hits*12)); }
function init(){ for(var i=0;i<N*N;i++){ var r=Math.floor(i/N),c=i%N;
  cells.push({x:P+c*(S+P),y:P+r*(S+P)}) } draw() }

function draw(){ ctx.clearRect(0,0,360,360);
  ctx.fillStyle='#0b1016'; ctx.beginPath(); ctx.moveTo(8,0);
  ctx.arcTo(360,0,360,360,14); ctx.arcTo(360,360,0,360,14); ctx.arcTo(0,360,0,0,14);
  ctx.arcTo(0,0,360,0,14); ctx.closePath(); ctx.fill();
  for(var i=0;i<cells.length;i++){ var c=cells[i], on=(i===cur&&run);
    ctx.fillStyle= on? (fake?'#E5484D':'#39C5BB') : 'rgba(255,255,255,.05)';
    ctx.beginPath(); ctx.arc(c.x+S/2,c.y+S/2,S/2,0,7); ctx.fill();
    if(!on){ ctx.strokeStyle='rgba(255,255,255,.12)'; ctx.lineWidth=2; ctx.stroke() }
    else { ctx.fillStyle= fake?'#fff':'#08222a'; ctx.font='700 13px sans-serif'; ctx.textAlign='center';
      ctx.fillText(fake?'✕':'TAP', c.x+S/2, c.y+S/2+5) }
  } }

function loop(){ requestAnimationFrame(loop);
  if(run){ var now=performance.now();
    var left=Math.max(0,(endAt-now)/1000);
    document.getElementById('time').textContent=left.toFixed(1);
    if(now>nextAt) place();
    if(now>=endAt){ end() }
  }
  draw(); }

function end(){ run=false; cur=-1;
  if(hits>best){ best=hits; __set('mph_tap',String(hits)) }
  document.getElementById('best').textContent=best;
  var m=document.getElementById('msg'); m.style.display='block';
  var rank = hits>=45?'手速怪物':hits>=35?'判定狂人':hits>=25?'稳':hits>=15?'还行':'手生了';
  m.innerHTML='<div class="big">'+hits+' 连击</div>评价：'+rank+'　·　最大连击 '+mx+'　·　历史最佳 '+best; }

cv.addEventListener('pointerdown',function(e){ if(!run||cur<0) return;
  var r=cv.getBoundingClientRect(), x=(e.clientX-r.left)*(360/r.width), y=(e.clientY-r.top)*(360/r.height);
  for(var i=0;i<cells.length;i++){ var c=cells[i];
    var dx=x-(c.x+S/2), dy=y-(c.y+S/2);
    if(dx*dx+dy*dy < (S/2)*(S/2)){
      if(i!==cur) return;
      if(fake){ combo=0; hits=Math.max(0,hits-2); }
      else { var dt=performance.now()-curT; hits++; combo++; if(combo>mx) mx=combo;
        if(dt<260) hits+=1; }
      document.getElementById('hit').textContent=hits;
      document.getElementById('combo').textContent=combo;
      place(); return; }
  } });
document.getElementById('go').onclick=function(){ hits=0;combo=0;mx=0;
  document.getElementById('hit').textContent='0'; document.getElementById('combo').textContent='0';
  document.getElementById('msg').style.display='none';
  run=true; endAt=performance.now()+30000; place(); };
init(); loop();
</script>
"""
    return _wrap(body.replace("__STORE__", _store("mph_tap")), ".stage{width:360px;margin:0 auto}")


# ================================================================ 5) 音符记忆（Simon）
def simon_html(height: int = 580) -> str:
    body = """
<div class="wrap">
  <div class="hud">
    <div>轮次<b id="rd">0</b></div>
    <div>已点<b id="pg">0 / 0</b></div>
    <div>最长纪录<b id="best">0</b></div>
  </div>
  <div id="board">
    <div class="note n0" data-i="0"></div><div class="note n1" data-i="1"></div>
    <div class="note n2" data-i="2"></div><div class="note n3" data-i="3"></div>
  </div>
  <div class="btns">
    <button id="go">▶ 开始</button>
    <button class="alt" id="sfx">🔊 音效：开</button>
  </div>
  <div class="panel" id="msg">先看灯亮的顺序，再原样点一遍。每轮多一个音。</div>
  <div class="tip">四个音对应键盘 <b>D F J K</b>（也可以直接点）。音高分别是 C-E-G-B，
    听音比看灯更容易记住。</div>
</div>
<script>
__STORE__
var TONE=[523.25,659.25,783.99,987.77];
var seq=[],pi=0,state='idle',sfxOn=true;
var best=parseInt(__get('mph_simon','0'))||0;
document.getElementById('best').textContent=best;
var ac=null;
function ctxAudio(){ if(!ac){ try{ ac=new (window.AudioContext||window.webkitAudioContext)() }catch(e){ac=null} } return ac }
function tone(f,d){ if(!sfxOn) return; var a=ctxAudio(); if(!a) return;
  var o=a.createOscillator(),g=a.createGain(); o.type='triangle'; o.frequency.value=f;
  g.gain.setValueAtTime(0,a.currentTime); g.gain.linearRampToValueAtTime(0.16,a.currentTime+0.01);
  g.gain.exponentialRampToValueAtTime(0.0001,a.currentTime+d);
  o.connect(g); g.connect(a.destination); o.start(); o.stop(a.currentTime+d+0.02) }
function el(i){ return document.querySelectorAll('#board .note')[i] }
function flash(i,ms){ var e=el(i); e.classList.add('on'); setTimeout(function(){ e.classList.remove('on') },ms) }
function upd(){ document.getElementById('rd').textContent=seq.length;
  document.getElementById('pg').textContent=pi+' / '+seq.length }
function playSeq(){ state='show'; pi=0; upd(); var k=0;
  (function step(){ if(k>=seq.length){ state='input'; upd(); return }
    flash(seq[k],360); tone(TONE[seq[k]],0.34); k++; setTimeout(step,600) })() }
function nextRound(){ seq.push(Math.floor(Math.random()*4)); ctxAudio(); playSeq() }
function over(){ state='idle'; var done=Math.max(0,seq.length-1);
  if(done>best){ best=done; __set('mph_simon',String(done)) }
  document.getElementById('best').textContent=best;
  document.getElementById('msg').innerHTML='<div class="big">记到第 '+done+' 轮</div>'
    +'这一轮是 '+seq.length+' 个音，最长纪录 '+best
    +(done>=8?'　<span style="color:#F5D442">这记忆力可以背谱了</span>':'');
  seq=[]; pi=0; document.getElementById('rd').textContent='0';
  document.getElementById('pg').textContent='0 / 0' }
function press(i){ if(state!=='input') return; flash(i,150); tone(TONE[i],0.18);
  if(seq[pi]===i){ pi++; upd(); if(pi>=seq.length){ state='wait'; setTimeout(nextRound,520) } }
  else { over() } }
document.querySelectorAll('#board .note').forEach(function(e){
  e.onclick=function(){ press(parseInt(e.dataset.i)) } });
document.addEventListener('keydown',function(e){ var k=(e.key||'').toLowerCase();
  var m={d:0,f:1,j:2,k:3}; if(k in m){ press(m[k]); e.preventDefault() } });
document.getElementById('go').onclick=function(){ seq=[]; pi=0; nextRound();
  document.getElementById('msg').textContent='看好顺序…' };
document.getElementById('sfx').onclick=function(){ sfxOn=!sfxOn;
  this.textContent='🔊 音效：'+(sfxOn?'开':'关') };
</script>
"""
    css = ("#board{display:grid;grid-template-columns:1fr 1fr;gap:14px;max-width:300px;margin:0 auto}"
           ".note{height:130px;border-radius:22px;cursor:pointer;opacity:.35;transition:opacity .12s,transform .12s;"
           "border:2px solid rgba(255,255,255,.12)}"
           ".note.n0{background:#39C5BB}.note.n1{background:#F5D442}.note.n2{background:#E5484D}.note.n3{background:#A66BFF}"
           ".note.on{opacity:1;transform:scale(1.05);box-shadow:0 0 26px rgba(255,255,255,.45)}")
    return _wrap(body.replace("__STORE__", _store("mph_simon")), css)


# ================================================================ 6) 回忆回廊（可选）
def recall_html(lines: list[dict], height: int = 620) -> str:
    """把剧情里出现过的台词打乱，让玩家按故事发生的顺序点回去。"""
    data = json.dumps([{"s": l.get("speaker", ""), "t": l.get("text", "")} for l in lines],
                      ensure_ascii=False)
    body = """
<div class="wrap">
  <div class="hud">
    <div>进度<b id="pg">0 / 0</b></div>
    <div>点错<b id="err">0</b></div>
    <div>用时<b id="tm">0.0s</b></div>
  </div>
  <div id="board"></div>
  <div class="btns"><button id="new">↻ 换一组</button></div>
  <div class="panel" id="msg">按故事发生的先后顺序，把这些话排回去。</div>
  <div class="tip">台词全部取自你走过的那条线——记得住顺序，说明这段你是真看进去了。</div>
</div>
<script>
__STORE__
var DATA=__DATA__;
var order=[],idx=0,errs=0,t0=0,timer=null;
function shuffle(a){ for(var i=a.length-1;i>0;i--){ var j=Math.floor(Math.random()*(i+1)); var t=a[i];a[i]=a[j];a[j]=t } return a }
function build(){ order=DATA.map(function(_,i){return i});
  idx=0;errs=0;document.getElementById('err').textContent='0';
  document.getElementById('msg').textContent='按故事发生的先后顺序，把这些话排回去。';
  var b=document.getElementById('board'); b.innerHTML='';
  shuffle(order.slice()).forEach(function(oi){
    var d=document.createElement('div'); d.className='ln'; d.dataset.oi=oi;
    d.innerHTML='<b>'+DATA[oi].s+'</b>：'+DATA[oi].t;
    d.onclick=function(){ pick(oi,d) }; b.appendChild(d) });
  document.getElementById('pg').textContent='0 / '+DATA.length;
  t0=performance.now(); clearInterval(timer);
  timer=setInterval(function(){ document.getElementById('tm').textContent=((performance.now()-t0)/1000).toFixed(1)+'s' },100) }
function pick(oi,el){ if(el.dataset.done==='1') return;
  if(oi===idx){ el.dataset.done='1'; el.classList.add('ok'); idx++;
    document.getElementById('pg').textContent=idx+' / '+DATA.length;
    if(idx>=DATA.length){ clearInterval(timer); win() } }
  else { errs++; document.getElementById('err').textContent=errs;
    el.classList.add('bad'); setTimeout(function(){ el.classList.remove('bad') },380) } }
function win(){ var sec=(performance.now()-t0)/1000;
  var rank = errs===0?'一字不差':errs<=2?'大致记得':errs<=5?'有点模糊':'走马观花';
  document.getElementById('msg').innerHTML='<div class="big">'+rank+'</div>'
    +'用时 '+sec.toFixed(1)+'s　·　点错 '+errs+' 次'
    +(errs===0?'　<span style="color:#F5D442">★ 全对</span>':'') }
document.getElementById('new').onclick=function(){ shuffle(DATA); build() };
build();
</script>
"""
    css = (           ".ln{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.10);"
           "border-radius:12px;padding:10px 12px;margin:7px 0;font-size:13px;line-height:1.7;"
           "text-align:left;cursor:pointer;transition:background .18s;white-space:pre-line}"
           ".ln:hover{background:rgba(57,197,187,.12)}"
           ".ln b{color:var(--miku,#39C5BB)}"
           ".ln.ok{background:rgba(34,197,94,.20);border-color:rgba(34,197,94,.5);opacity:.75}"
           ".ln.bad{background:rgba(229,72,77,.22);border-color:rgba(229,72,77,.6)}")
    return _wrap(body.replace("__DATA__", data).replace("__STORE__", _store("mph_recall")), css)


# ================================================================ 4) 曲名记忆翻牌
def memory_html(titles: list[str], height: int = 640) -> str:
    pairs = [t for t in titles if t][:8]
    data = json.dumps(pairs, ensure_ascii=False)
    body = """
<div class="wrap">
  <div class="hud">
    <div>用时<b id="tm">0.0s</b></div>
    <div>翻牌次数<b id="mv">0</b></div>
    <div>已配对<b id="pr">0/8</b></div>
    <div>最佳<b id="best">—</b></div>
  </div>
  <div id="board" style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;max-width:520px;margin:0 auto"></div>
  <div class="btns"><button id="new">↻ 换一批曲</button></div>
  <div class="panel" id="msg" style="display:none"></div>
  <div class="tip">点开两张，曲名一样就配对成功。比的是记忆力和运气，<br>
  曲名全部来自你本地那份舞萌曲库快照。</div>
</div>
<script>
__STORE__
var DATA=__DATA__;
var deck=[],open=[],matched=0,moves=0,t0=0,timer=null,lock=false;
function shuffle(a){ for(var i=a.length-1;i>0;i--){ var j=Math.floor(Math.random()*(i+1)); var t=a[i];a[i]=a[j];a[j]=t } return a }
function bestKey(){ return 'mph_mem' }
function build(){ deck=shuffle(DATA.concat(DATA)); open=[];matched=0;moves=0;lock=false;
  var b=document.getElementById('board'); b.innerHTML='';
  deck.forEach(function(t,i){ var d=document.createElement('div');
    d.textContent=''; d.dataset.i=i; d.className='card';
    d.style.cssText='height:76px;border-radius:12px;display:flex;align-items:center;justify-content:center;'
      +'font-size:11px;line-height:1.3;padding:6px;text-align:center;cursor:pointer;'
      +'background:linear-gradient(135deg,#134e4a,#0f2b2b);border:1px solid rgba(57,197,187,.35);color:#eaf6f5;'
      +'transition:transform .12s';
    d.onclick=function(){ flip(i,d) }; b.appendChild(d) });
  document.getElementById('mv').textContent='0'; document.getElementById('pr').textContent='0/'+DATA.length;
  document.getElementById('msg').style.display='none';
  t0=performance.now(); clearInterval(timer);
  timer=setInterval(function(){ document.getElementById('tm').textContent=((performance.now()-t0)/1000).toFixed(1)+'s' },100);
  var bk=__get(bestKey(),''); document.getElementById('best').textContent=bk||'—';
}
function flip(i,el){ if(lock) return;
  var c=el; if(c.dataset.done==='1'||open.indexOf(i)>=0) return;
  c.textContent=deck[i]; c.style.background='rgba(57,197,187,.9)'; c.style.color='#04222a';
  open.push(i);
  if(open.length===2){ moves++; document.getElementById('mv').textContent=moves; lock=true;
    setTimeout(function(){
      var a=open[0],b=open[1];
      var ea=document.querySelectorAll('#board .card')[a], eb=document.querySelectorAll('#board .card')[b];
      if(deck[a]===deck[b]){ matched++; ea.dataset.done='1'; eb.dataset.done='1';
        ea.style.background='rgba(34,197,94,.28)'; eb.style.background='rgba(34,197,94,.28)';
        ea.style.color='#b7f7cd'; eb.style.color='#b7f7cd';
        document.getElementById('pr').textContent=matched+'/'+DATA.length;
        if(matched===DATA.length) win() }
      else { ea.textContent=''; eb.textContent='';
        ea.style.background='linear-gradient(135deg,#134e4a,#0f2b2b)'; ea.style.color='#eaf6f5';
        eb.style.background='linear-gradient(135deg,#134e4a,#0f2b2b)'; eb.style.color='#eaf6f5' }
      open=[]; lock=false },620) }
}
function win(){ clearInterval(timer); var sec=(performance.now()-t0)/1000;
  var rec=__get(bestKey(),''); var isNew=false;
  var val=moves+' 次 / '+sec.toFixed(1)+'s';
  if(!rec||moves<parseInt(rec)){ __set(bestKey(),String(moves)); rec=String(moves); isNew=true }
  document.getElementById('best').textContent=rec+' 次';
  var m=document.getElementById('msg'); m.style.display='block';
  var rank = moves<=12?'记忆怪物':moves<=18?'读谱脑子':moves<=24?'还行':'多练练';
  m.innerHTML='<div class="big">'+rank+'</div>'+val+(isNew?'　<span style="color:#F5D442">★ 新纪录</span>':'') }
document.getElementById('new').onclick=build;
build();
</script>
"""
    return _wrap(body.replace("__DATA__", data).replace("__STORE__", _store("mph_mem")))


# ================================================================ 7) 曲名打字
def type_html(titles: list[str], height: int = 520) -> str:
    """照着曲名敲，60 秒比 WPM 和准确率。曲名来自本地曲库（只取能直接用键盘敲的）。"""
    data = json.dumps([t for t in (titles or []) if t][:60], ensure_ascii=False)
    body = """
<div class="wrap">
  <div class="hud">
    <div>剩余<b id="tm">60.0s</b></div>
    <div>正确字符<b id="cc">0</b></div>
    <div>准确率<b id="ac">100%</b></div>
    <div>WPM<b id="wpm">0</b></div>
  </div>
  <div class="panel" id="target" style="min-height:74px;display:flex;align-items:center;justify-content:center"></div>
  <div class="btns">
    <button id="go">▶ 开始</button>
    <button class="alt" id="skip">⏭ 换一首</button>
  </div>
  <div class="panel" id="msg">倒计时 60 秒，敲完一首自动接下一首。大小写不敏感，符号要照敲。</div>
  <div class="tip">曲名全部来自你本地那份曲库快照，只挑了能用键盘直接敲的（纯英文/数字/符号）。
    <br>WPM 按标准算法算：正确字符数 ÷ 5 ÷ 分钟。</div>
</div>
<script>
__STORE__
var DATA=__DATA__;
var idx=0,pos=0,ok=0,bad=0,t0=0,timer=null,run=false,LEFT=60;
function cur(){ return DATA[idx % DATA.length] }
function esc(s){ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') }
function elapsedMin(){ return Math.max(0.05,(performance.now()-t0)/60000) }
function render(){
  var s=cur(),h='';
  for(var i=0;i<s.length;i++){
    var c=esc(s[i]===' '?' ':s[i]);
    h+="<span class='ch "+(i<pos?'ok':(i===pos?'now':''))+"'>"+c+"</span>";
  }
  document.getElementById('target').innerHTML=h;
  document.getElementById('cc').textContent=ok;
  var tot=ok+bad;
  document.getElementById('ac').textContent=(tot?Math.round(ok/tot*100):100)+'%';
  document.getElementById('wpm').textContent=Math.round((ok/5)/elapsedMin());
}
function tick(){
  var rem=LEFT-(performance.now()-t0)/1000;
  if(rem<=0){ document.getElementById('tm').textContent='0.0s'; finish(); return }
  document.getElementById('tm').textContent=rem.toFixed(1)+'s'; render();
}
function finish(){ run=false; clearInterval(timer);
  var wpm=Math.round((ok/5)/elapsedMin()), acc=(ok+bad)?Math.round(ok/(ok+bad)*100):100;
  var m=document.getElementById('msg');
  var rank = wpm>=60?'手速怪物':wpm>=40?'键盘熟练':wpm>=25?'正常水平':'慢慢来';
  var rec=parseInt(__get('mph_type','0'))||0, isNew=false;
  if(wpm>rec){ __set('mph_type',String(wpm)); isNew=true }
  m.innerHTML='<div class="big">'+rank+'</div>WPM '+wpm+'　·　准确率 '+acc+'%　·　敲对 '+ok+' 字符'
    +(isNew?'　<span style="color:#F5D442">★ 新纪录</span>':'　最高 '+Math.max(rec,wpm));
}
function next(){ idx++; pos=0; render() }
function start(){ idx=0;pos=0;ok=0;bad=0;run=true;LEFT=60;t0=performance.now();
  document.getElementById('tm').textContent='60.0s';
  document.getElementById('msg').textContent='敲吧。';
  render(); clearInterval(timer); timer=setInterval(tick,100) }
document.addEventListener('keydown',function(e){
  if(!run) return;
  var k=e.key; if(k.length!==1) return;
  if(e.ctrlKey||e.metaKey||e.altKey) return;
  var want=cur()[pos];
  if(want!==undefined && k.toLowerCase()===want.toLowerCase()){ ok++; pos++;
    if(pos>=cur().length){ next() } }
  else { bad++ }
  e.preventDefault(); render();
});
document.getElementById('go').onclick=start;
document.getElementById('skip').onclick=function(){ if(run) next() };
render();
</script>
"""
    css = (".ch{display:inline-block;font-size:22px;font-weight:700;letter-spacing:1px;color:#5d6b70;"
           "padding:0 1px;border-radius:4px;transition:color .1s,background .1s}"
           ".ch.ok{color:#04222a;background:#39C5BB}"
           ".ch.now{color:#04222a;background:#F5D442;box-shadow:0 0 12px rgba(245,212,66,.5)}")
    return _wrap(body.replace("__DATA__", data).replace("__STORE__", _store("mph_type")), css)


# ================================================================ 8) NOTE 落块
def drop_html(height: int = 620) -> str:
    """俄罗斯方块，方块用舞萌的难度配色。消一行加一层，速度随等级变快。"""
    body = """
<div class="wrap">
  <div class="hud">
    <div>得分<b id="sc">0</b></div>
    <div>消行<b id="ln">0</b></div>
    <div>等级<b id="lv">1</b></div>
    <div>最佳<b id="best">—</b></div>
  </div>
  <div class="stage">
    <canvas id="cv" width="240" height="432"></canvas>
    <div class="center" id="over"></div>
  </div>
  <div class="btns">
    <button id="go">▶ 开始</button>
    <button class="alt" id="pause">⏸ 暂停</button>
  </div>
  <div class="tip"><b>← →</b> 移动　<b>↑ / X</b> 顺时针转　<b>Z</b> 逆时针　<b>↓</b> 加速下落　<b>空格</b> 直落到底</div>
</div>
<script>
__STORE__
var cv=document.getElementById('cv'),ctx=cv.getContext('2d');
var COLS=10,ROWS=18,C=24;
var SHAPES=[[[1,1,1,1]],[[1,1],[1,1]],[[0,1,0],[1,1,1]],[[1,0,0],[1,1,1]],
            [[0,0,1],[1,1,1]],[[1,1,0],[0,1,1]],[[0,1,1],[1,1,0]]];
var COLORS=['#39C5BB','#F5D442','#A66BFF','#3B82F6','#F97316','#22C55E','#E5484D'];
var grid=[],cur=null,score=0,lines=0,level=1,run=false,paused=false,acc=0,last=0;
function mkgrid(){ grid=[]; for(var r=0;r<ROWS;r++){ var row=[]; for(var c=0;c<COLS;c++) row.push(-1); grid.push(row) } }
function rot(m){ var n=m.length,o=[]; for(var i=0;i<n;i++){ o.push([]); for(var j=0;j<n;j++) o[i].push(m[n-1-j][i]) } return o }
function spawn(){ var i=Math.floor(Math.random()*SHAPES.length);
  cur={m:SHAPES[i].map(function(r){return r.slice()}),ci:i,r:0,c:Math.floor(COLS/2)-1};
  if(hit(cur.m,cur.r,cur.c)){ gameover() } }
function hit(m,r,c){ for(var i=0;i<m.length;i++) for(var j=0;j<m[i].length;j++){
    if(!m[i][j]) continue;
    var rr=r+i,cc=c+j;
    if(rr>=ROWS||cc<0||cc>=COLS) return true;
    if(rr>=0&&grid[rr][cc]>=0) return true }
  return false }
function merge(){ for(var i=0;i<cur.m.length;i++) for(var j=0;j<cur.m[i].length;j++){
    if(cur.m[i][j]&&cur.r+i>=0) grid[cur.r+i][cur.c+j]=cur.ci }
  var cleared=0;
  for(var r=ROWS-1;r>=0;r--){ var full=true;
    for(var c=0;c<COLS;c++) if(grid[r][c]<0) full=false;
    if(full){ grid.splice(r,1); var nr=[]; for(var c2=0;c2<COLS;c2++) nr.push(-1); grid.unshift(nr); cleared++; r++ } }
  if(cleared){ lines+=cleared; score+=[0,100,300,500,800][cleared]*level; level=1+Math.floor(lines/10);
    document.getElementById('ln').textContent=lines; document.getElementById('lv').textContent=level }
  spawn(); }
function draw(){ ctx.clearRect(0,0,cv.width,cv.height);
  ctx.fillStyle='rgba(255,255,255,.03)'; ctx.fillRect(0,0,cv.width,cv.height);
  for(var r=0;r<ROWS;r++) for(var c=0;c<COLS;c++){
    if(grid[r][c]>=0){ px(c,r,COLORS[grid[r][c]]) } }
  if(cur){ for(var i=0;i<cur.m.length;i++) for(var j=0;j<cur.m[i].length;j++){
    if(cur.m[i][j]&&cur.r+i>=0) px(cur.c+j,cur.r+i,COLORS[cur.ci]) } }
  document.getElementById('sc').textContent=score; }
function px(c,r,col){ ctx.fillStyle=col; ctx.fillRect(c*C+1,r*C+1,C-2,C-2);
  ctx.fillStyle='rgba(255,255,255,.22)'; ctx.fillRect(c*C+1,r*C+1,C-2,4) }
function step(){ var d=Math.max(90,620-(level-1)*55);
  if(acc>=d){ acc=0;
    if(!hit(cur.m,cur.r+1,cur.c)) cur.r++;
    else merge() } }
function gameover(){ run=false;
  var rec=parseInt(__get('mph_drop','0'))||0, isNew=false;
  if(score>rec){ __set('mph_drop',String(score)); isNew=true }
  document.getElementById('best').textContent=Math.max(rec,score)||'—';
  var o=document.getElementById('over'); o.style.opacity=1;
  o.innerHTML='<div class="big">结束</div>得分 '+score+'　消 '+lines+' 行'
    +(isNew?'　<span style="color:#F5D442">★ 新纪录</span>':''); }
function loop(ts){ requestAnimationFrame(loop);
  if(!last) last=ts; var dt=ts-last; last=ts;
  if(!run||paused) { draw(); return }
  acc+=dt; step(); draw(); }
function start(){ mkgrid(); score=0;lines=0;level=1;acc=0;run=true;paused=false;
  document.getElementById('ln').textContent='0'; document.getElementById('lv').textContent='1';
  document.getElementById('over').style.opacity=0; document.getElementById('over').innerHTML='';
  document.getElementById('best').textContent=__get('mph_drop','0')||'—';
  spawn(); }
document.addEventListener('keydown',function(e){ if(!run) return; var k=e.key;
  function tryMove(m,r,c){ if(!hit(m,r,c)){ cur.m=m;cur.r=r;cur.c=c; draw() } }
  if(k==='ArrowLeft'){ tryMove(cur.m,cur.r,cur.c-1); e.preventDefault() }
  else if(k==='ArrowRight'){ tryMove(cur.m,cur.r,cur.c+1); e.preventDefault() }
  else if(k==='ArrowDown'){ if(!hit(cur.m,cur.r+1,cur.c)) cur.r++; else merge(); e.preventDefault() }
  else if(k==='ArrowUp'||k==='x'||k==='X'){ tryMove(rot(cur.m),cur.r,cur.c); e.preventDefault() }
  else if(k==='z'||k==='Z'){ tryMove(rot(rot(cur.m)),cur.r,cur.c); e.preventDefault() }
  else if(k===' '){ while(!hit(cur.m,cur.r+1,cur.c)) cur.r++; merge(); e.preventDefault() } });
document.getElementById('go').onclick=start;
document.getElementById('pause').onclick=function(){ paused=!paused;
  this.textContent=paused?'▶ 继续':'⏸ 暂停' };
mkgrid(); draw(); requestAnimationFrame(loop);
</script>
"""
    return _wrap(body.replace("__STORE__", _store("mph_drop")), ".stage{width:240px;margin:0 auto}")


# ================================================================ 9) 音符蛇
def snake_html(height: int = 560) -> str:
    body = """
<div class="wrap">
  <div class="hud">
    <div>长度<b id="len">3</b></div>
    <div>得分<b id="sc">0</b></div>
    <div>用时<b id="tm">0s</b></div>
    <div>最佳<b id="best">—</b></div>
  </div>
  <div class="stage"><canvas id="cv" width="320" height="320"></canvas>
    <div class="center" id="over"></div></div>
  <div class="btns"><button id="go">▶ 开始</button></div>
  <div class="tip">方向键或 <b>WASD</b> 控制，吃掉青绿色的音符就变长。撞墙或撞到自己就结束。
    <br>吃得越多越快，纯消磨时间用。</div>
</div>
<script>
__STORE__
var cv=document.getElementById('cv'),ctx=cv.getContext('2d');
var N=20,C=16;
var snake=[{x:10,y:10},{x:9,y:10},{x:8,y:10}],dir={x:1,y:0},pending=null;
var food={x:15,y:10},score=0,run=false,steps=0,t0=0,timer=null;
function place(){ while(true){ var ok=true; var p={x:Math.floor(Math.random()*N),y:Math.floor(Math.random()*N)};
  for(var i=0;i<snake.length;i++) if(snake[i].x===p.x&&snake[i].y===p.y){ ok=false; break }
  if(ok){ food=p; return } } }
function draw(){ ctx.fillStyle='#080b0f'; ctx.fillRect(0,0,cv.width,cv.height);
  ctx.fillStyle='#39C5BB'; ctx.beginPath();
  ctx.arc(food.x*C+C/2,food.y*C+C/2,C/2-2,0,7); ctx.fill();
  for(var i=0;i<snake.length;i++){ var s=snake[i];
    ctx.fillStyle=i===0?'#F5D442':'#2f8f88';
    ctx.fillRect(s.x*C+1,s.y*C+1,C-2,C-2) } }
function tick(){ if(!run) return;
  if(pending){ dir=pending; pending=null }
  var h={x:snake[0].x+dir.x,y:snake[0].y+dir.y};
  if(h.x<0||h.y<0||h.x>=N||h.y>=N) return over();
  for(var i=0;i<snake.length;i++) if(snake[i].x===h.x&&snake[i].y===h.y) return over();
  snake.unshift(h);
  if(h.x===food.x&&h.y===food.y){ score+=10; place(); document.getElementById('sc').textContent=score }
  else snake.pop();
  document.getElementById('len').textContent=snake.length;
  draw(); }
function over(){ run=false; clearInterval(timer);
  var rec=parseInt(__get('mph_snake','0'))||0,isNew=false;
  if(score>rec){ __set('mph_snake',String(score)); isNew=true }
  document.getElementById('best').textContent=Math.max(rec,score)||'—';
  var o=document.getElementById('over'); o.style.opacity=1;
  o.innerHTML='<div class="big">撞了</div>得分 '+score+'　长度 '+snake.length
    +(isNew?'　<span style="color:#F5D442">★ 新纪录</span>':''); }
function start(){ snake=[{x:10,y:10},{x:9,y:10},{x:8,y:10}]; dir={x:1,y:0}; pending=null;
  score=0;run=true;steps=0;t0=performance.now();
  document.getElementById('sc').textContent='0'; document.getElementById('len').textContent='3';
  document.getElementById('over').style.opacity=0; document.getElementById('over').innerHTML='';
  document.getElementById('best').textContent=__get('mph_snake','0')||'—';
  place(); clearInterval(timer); timer=setInterval(tick,110) }
document.addEventListener('keydown',function(e){ var k=(e.key||'').toLowerCase();
  var m={arrowleft:[-1,0],arrowright:[1,0],arrowup:[0,-1],arrowdown:[0,1],a:[-1,0],d:[1,0],w:[0,-1],s:[0,1]};
  if(k in m){ var v=m[k]; if(v[0]!==-dir.x||v[1]!==-dir.y) pending={x:v[0],y:v[1]}; e.preventDefault() } });
document.getElementById('go').onclick=start;
draw();
</script>
"""
    return _wrap(body.replace("__STORE__", _store("mph_snake")), ".stage{width:320px;margin:0 auto}")


# ================================================================ 10) 判定偏移校准
def offset_html(height: int = 520) -> str:
    """
    专业向小工具：播 120 BPM 的节拍，你跟着敲空格，统计你 habitual 的早晚偏差，
    给出建议写进机台的判定偏移值。全程 Web Audio 合成，不碰任何音频文件。
    """
    body = """
<div class="wrap">
  <div class="hud">
    <div>已敲<b id="cnt">0 / 16</b></div>
    <div>平均偏差<b id="avg">—</b></div>
    <div>稳定性<b id="std">—</b></div>
  </div>
  <canvas id="cv" width="440" height="120"></canvas>
  <div class="btns">
    <button id="go">▶ 开始校准</button>
    <button class="alt" id="reset">↻ 重来</button>
  </div>
  <div class="panel" id="msg">跟着节拍敲空格（或点上面的按钮）。敲满 16 下，我告诉你该把判定偏移调成多少。</div>
  <div class="tip">节拍是程序实时合成的 120 BPM，不是任何受版权保护的音频。
    结果只表示「你在这台设备、这个状态下的手感」，换设备建议重测。</div>
</div>
<script>
__STORE__
var cv=document.getElementById('cv'),ctx=cv.getContext('2d');
var BPM=120,BEAT=60000/BPM,NEED=16;
var ac=null,startT=0,beats=[],tapIdx=0,offs=[],run=false,sched=0,timer=null;
function audio(){ if(!ac){try{ac=new (window.AudioContext||window.webkitAudioContext)()}catch(e){ac=null}} return ac }
function clickAt(t){ var a=audio(); if(!a) return;
  var o=a.createOscillator(),g=a.createGain(); o.type='square'; o.frequency.value=1200;
  g.gain.setValueAtTime(0.0001,t); g.gain.linearRampToValueAtTime(0.12,t+0.004);
  g.gain.exponentialRampToValueAtTime(0.0001,t+0.05);
  o.connect(g); g.connect(a.destination); o.start(t); o.stop(t+0.06) }
function schedule(){ var a=audio(); if(!a) return;
  while(beats.length < 400 && beats.length * (BEAT/1000) < (a.currentTime-startT)+2){
    var t=startT+beats.length*(BEAT/1000); beats.push(t); clickAt(t) } }
function tap(){ if(!run) return; var a=audio(); if(!a) return;
  var now=a.currentTime,bi=Math.round((now-startT)/(BEAT/1000));
  if(bi<0) return;
  var off=(now-(startT+bi*(BEAT/1000)))*1000;
  if(offs.length>=NEED) return;
  offs.push(off); upd(); draw();
  if(offs.length>=NEED) done() }
function mean(a){ var s=0; for(var i=0;i<a.length;i++) s+=a[i]; return a.length?s/a.length:0 }
function stdev(a){ if(a.length<2) return 0; var m=mean(a),s=0;
  for(var i=0;i<a.length;i++) s+=(a[i]-m)*(a[i]-m); return Math.sqrt(s/(a.length-1)) }
function upd(){ document.getElementById('cnt').textContent=offs.length+' / '+NEED;
  document.getElementById('avg').textContent=offs.length?(mean(offs)>0?'+':'')+mean(offs).toFixed(1)+'ms':'—';
  document.getElementById('std').textContent=offs.length>1?'±'+stdev(offs).toFixed(1)+'ms':'—' }
function draw(){ ctx.clearRect(0,0,cv.width,cv.height);
  ctx.fillStyle='rgba(255,255,255,.05)'; ctx.fillRect(0,0,cv.width,cv.height);
  ctx.fillStyle='rgba(57,197,187,.7)'; ctx.fillRect(cv.width/2-1,0,2,cv.height);
  ctx.fillStyle='rgba(255,255,255,.18)';
  ctx.fillRect(cv.width/2-46,0,2,cv.height); ctx.fillRect(cv.width/2+46,0,2,cv.height);
  ctx.font='11px sans-serif'; ctx.fillStyle='#7f8f96';
  ctx.fillText('早',cv.width/2-58,14); ctx.fillText('准',cv.width/2+4,14); ctx.fillText('晚',cv.width/2+50,14);
  for(var i=0;i<offs.length;i++){ var v=offs[i];
    var x=cv.width/2+Math.max(-180,Math.min(180,v))*0.9;
    var y=26+i*5.2;
    ctx.fillStyle=Math.abs(v)<=45?'#39C5BB':Math.abs(v)<=90?'#F5D442':'#E5484D';
    ctx.fillRect(x,y,Math.max(2,Math.abs(v)*0.9),4);
    if(v<0){ ctx.fillRect(x+Math.abs(v)*0.9,y,Math.abs(v)*0.9,4) } }
  ctx.fillStyle='#7f8f96'; ctx.fillText('±200ms',8,cv.height-6) }
function done(){ run=false;
  var m=mean(offs),sd=stdev(offs);
  var suggest=-Math.round(m);
  var judge = Math.abs(m)<=20?'你的节奏感很准，几乎不用调':
              (m>0?'你习惯性偏晚':'你习惯性偏早')+'，建议把判定偏移设为 '+(suggest>0?'+':'')+suggest+'ms';
  var stab = sd<=25?'手感很稳':sd<=45?'还算稳定':'波动有点大，多测几次取平均更靠谱';
  document.getElementById('msg').innerHTML='<div class="big">'+(m>0?'+':'')+m.toFixed(1)+'ms</div>'
    +judge+'<br><span style="color:#7f8f96">'+stab+'（标准差 ±'+sd.toFixed(1)+'ms）</span>';
  __set('mph_offset',String(suggest)) }
function start(){ audio(); var a=audio(); if(!a){ document.getElementById('msg').textContent='这个浏览器不支持 Web Audio，换 Chrome/Edge 试试。'; return }
  if(a.state==='suspended'&&a.resume) a.resume();
  beats=[];offs=[];run=true;startT=a.currentTime+0.6;
  document.getElementById('msg').textContent='跟着节拍敲空格…';
  upd(); draw(); clearInterval(timer); timer=setInterval(schedule,200); schedule() }
function reset(){ run=false; clearInterval(timer); offs=[]; upd(); draw();
  document.getElementById('msg').textContent='跟着节拍敲空格（或点上面的按钮）。敲满 16 下，我告诉你该把判定偏移调成多少。' }
document.addEventListener('keydown',function(e){ if(e.code==='Space'||e.key===' '){ tap(); e.preventDefault() } });
document.getElementById('go').onclick=start;
document.getElementById('reset').onclick=reset;
cv.addEventListener('pointerdown',tap);
draw();
</script>
"""
    return _wrap(body.replace("__STORE__", _store("mph_offset")),
                 "canvas{background:#080b0f;border:1px solid rgba(255,255,255,.1);border-radius:10px;margin:6px auto}")


# ================================================================ 12) 氛围音（纯合成）
def ambience_html(height: int = 120) -> str:
    """
    给专属空间垫一层底噪：三种音色全部用 Web Audio 实时合成（正弦叠加 + 缓慢起伏），
    不加载、不引用任何音频文件，也就没有任何版权问题。
    """
    body = """
<div class="wrap" style="max-width:none">
  <div style="display:flex;gap:8px;align-items:center;justify-content:center;flex-wrap:wrap">
    <button id="on">🔊 氛围音：关</button>
    <button class="alt" id="mood">音色：深夜档案</button>
    <input id="vol" type="range" min="0" max="100" value="35" style="width:110px">
    <span id="lv" style="font-size:12px;color:#7f8f96">35%</span>
  </div>
  <div class="tip" style="margin-top:6px">底噪是实时合成的，关掉就彻底静音。
    想听清楚台词就把音量拉低一点。</div>
</div>
<script>
var MOODS=[
  {name:'深夜档案',base:110,ratio:[1,1.5,2.02],type:'sine',lfo:0.07},
  {name:'星空',base:146.8,ratio:[1,1.25,1.5,2],type:'triangle',lfo:0.05},
  {name:'心跳',base:82,ratio:[1,1.5],type:'sine',lfo:0.5}
];
var mi=0,ac=null,gain=null,nodes=[],on=false;
function audio(){ if(!ac){try{ac=new (window.AudioContext||window.webkitAudioContext)()}catch(e){ac=null}} return ac }
function build(){ var a=audio(); if(!a) return; stop();
  var m=MOODS[mi];
  gain=a.createGain(); gain.gain.value=0; gain.connect(a.destination);
  m.ratio.forEach(function(r,i){
    var o=a.createOscillator(); o.type=m.type; o.frequency.value=m.base*r*(1+i*0.002);
    var g=a.createGain(); g.gain.value=0.34/(i+1);
    var lfo=a.createOscillator(); lfo.frequency.value=m.lfo*(i+1);
    var lg=a.createGain(); lg.gain.value=0.16/(i+1);
    lfo.connect(lg); lg.connect(g.gain);
    o.connect(g); g.connect(gain); o.start(); lfo.start();
    nodes.push(o,lfo);
  });
  gain.gain.linearRampToValueAtTime(parseInt(document.getElementById('vol').value)/100*0.22,a.currentTime+1.2);
}
function stop(){ if(gain){ try{ gain.gain.linearRampToValueAtTime(0,ac.currentTime+0.4) }catch(e){} }
  nodes.forEach(function(n){ try{ n.stop(ac.currentTime+0.5) }catch(e){} });
  nodes=[]; setTimeout(function(){ try{ gain&&gain.disconnect() }catch(e){} },700); }
document.getElementById('on').onclick=function(){
  var a=audio(); if(!a){ this.textContent='这个浏览器不支持 Web Audio'; return }
  if(a.state==='suspended'&&a.resume) a.resume();
  on=!on; this.textContent='🔊 氛围音：'+(on?'开':'关');
  if(on) build(); else stop();
};
document.getElementById('mood').onclick=function(){ mi=(mi+1)%MOODS.length;
  this.textContent='音色：'+MOODS[mi].name; if(on) build(); };
document.getElementById('vol').oninput=function(){
  document.getElementById('lv').textContent=this.value+'%';
  try{ gain.gain.setTargetAtTime(parseInt(this.value)/100*0.22,ac.currentTime,0.2) }catch(e){}
};
</script>
"""
    return _wrap(body, "input[type=range]{accent-color:#39C5BB}")


# ================================================================ 11) 插画拼图（可选）
def puzzle_html(image_b64: str, n: int = 3, height: int = 620) -> str:
    """把一张原创插画切成 n×n 的滑块拼图。图片以 base64 内嵌，不引用任何外部资源。"""
    body = """
<div class="wrap">
  <div class="hud">
    <div>步数<b id="mv">0</b></div>
    <div>用时<b id="tm">0.0s</b></div>
    <div>最佳<b id="best">—</b></div>
  </div>
  <canvas id="cv" width="330" height="330"></canvas>
  <div class="btns">
    <button id="new">↻ 打乱</button>
    <button class="alt" id="peek">👀 看原图</button>
  </div>
  <div class="panel" id="msg">点空格旁边的块把它挪过来，拼回原图。</div>
  <div class="tip">拼的是程序里那张原创插画，拼好会整张显示给你看。</div>
</div>
<script>
__STORE__
var N=__N__;
var cv=document.getElementById('cv'),ctx=cv.getContext('2d');
var S=cv.width/N;
var img=new Image(),tiles=[],blank=N*N-1,moves=0,t0=0,timer=null,done=false,peeking=false;
img.onload=function(){ reset(); };
img.src='data:image/jpeg;base64,__B64__';
function reset(){ tiles=[]; for(var i=0;i<N*N;i++) tiles.push(i); blank=N*N-1; moves=0; done=false;
  document.getElementById('mv').textContent='0';
  document.getElementById('msg').textContent='点空格旁边的块把它挪过来，拼回原图。';
  shuffle(); t0=performance.now(); clearInterval(timer);
  timer=setInterval(function(){ if(!done) document.getElementById('tm').textContent=((performance.now()-t0)/1000).toFixed(1)+'s' },100);
  document.getElementById('best').textContent=__get('mph_puz','')||'—';
  draw(); }
function shuffle(){ var last=-1;
  for(var k=0;k<N*N*20;k++){ var nb=neighbors(blank);
    var cand=nb.filter(function(x){ return x!==last });
    var pick=cand[Math.floor(Math.random()*cand.length)];
    last=blank; swap(pick); } }
function neighbors(i){ var r=Math.floor(i/N),c=i%N,out=[];
  if(r>0) out.push(i-N); if(r<N-1) out.push(i+N);
  if(c>0) out.push(i-1); if(c<N-1) out.push(i+1); return out }
function swap(i){ var t=tiles[i]; tiles[i]=tiles[blank]; tiles[blank]=t; blank=i }
function draw(){ ctx.clearRect(0,0,cv.width,cv.height);
  if(peeking||done){ ctx.drawImage(img,0,0,cv.width,cv.height); return }
  for(var i=0;i<N*N;i++){ var v=tiles[i];
    if(v===N*N-1) continue;
    var r=Math.floor(i/N),c=i%N, sr=Math.floor(v/N), sc=v%N;
    ctx.drawImage(img,sc*img.width/N,sr*img.height/N,img.width/N,img.height/N,c*S,r*S,S,S);
    ctx.strokeStyle='rgba(13,17,23,.85)'; ctx.lineWidth=1; ctx.strokeRect(c*S,r*S,S,S) } }
function solved(){ for(var i=0;i<N*N;i++) if(tiles[i]!==i) return false; return true }
function tap(x,y){ if(done||peeking) return;
  var c=Math.floor(x/S),r=Math.floor(y/S),i=r*N+c;
  if(neighbors(blank).indexOf(i)<0) return;
  swap(i); moves++; document.getElementById('mv').textContent=moves; draw();
  if(solved()) win(); }
function win(){ done=true; clearInterval(timer);
  var sec=(performance.now()-t0)/1000;
  var rec=parseInt(__get('mph_puz','0'))||0,isNew=false;
  if(!rec||moves<rec){ __set('mph_puz',String(moves)); isNew=true }
  document.getElementById('best').textContent=moves+' 步';
  document.getElementById('msg').innerHTML='<div class="big">拼好了</div>'+moves+' 步 / '+sec.toFixed(1)+'s'
    +(isNew?'　<span style="color:#F5D442">★ 新纪录</span>':'');
  peeking=false; draw(); }
cv.addEventListener('pointerdown',function(e){ var r=cv.getBoundingClientRect();
  tap((e.clientX-r.left)*(cv.width/r.width),(e.clientY-r.top)*(cv.height/r.height)) });
document.getElementById('new').onclick=function(){ peeking=false; reset() };
document.getElementById('peek').onclick=function(){ peeking=!peeking;
  this.textContent=peeking?'🙈 收起来':'👀 看原图'; draw() };
draw();
</script>
"""
    body = (body.replace("__STORE__", _store("mph_puz"))
                .replace("__B64__", image_b64)
                .replace("__N__", str(int(n))))
    return _wrap(body, "canvas{background:#080b0f;border:1px solid rgba(255,255,255,.1);"
                       "border-radius:12px;margin:6px auto;touch-action:none}")


# ================================================================ 成绩码（小游戏 → 账号）
_CODE_JS = """
function __crc(s){var h=5381;for(var i=0;i<s.length;i++)h=((h*33)^s.charCodeAt(i))>>>0;
  var d='0123456789abcdefghijklmnopqrstuvwxyz',o='';
  while(h){o=d[h%36]+o;h=Math.floor(h/36)}return (o||'0').slice(0,5)}
function __code(o){var b=btoa(unescape(encodeURIComponent(JSON.stringify(o))));
  return 'MM1:'+b+':'+__crc(b)}
function __showCode(res){
  var el=document.getElementById('codebox'); if(!el) return;
  el.style.display='block';
  el.innerHTML="<div style='font-size:11px;color:#7f8f96;margin-top:10px'>"
    +"成绩码 —— 复制后粘回主界面「成绩登记处」，这局就存进你的账号了：</div>"
    +"<div style='display:flex;gap:6px;margin-top:4px'>"
    +"<input id='ccode' readonly value='"+__code(res)+"' style='flex:1;background:#05080c;"
    +"border:1px solid rgba(255,255,255,.16);color:#9fe8e2;border-radius:9px;padding:6px 8px;"
    +"font-size:11px;font-family:Consolas,monospace'>"
    +"<button onclick='var e=document.getElementById(\\\"ccode\\\");e.select();"
    +"try{document.execCommand(\\\"copy\\\");this.innerText=\\\"已复制\\\"}catch(E){this.innerText=\\\"手动复制\\\"}'>📋</button></div>";
}
"""


# ================================================================ 13) 读谱训练
def score_html(records: list[dict] | None = None, height: int = 620) -> str:
    """
    读谱训练：给一小段谱面，判断它的配置。这是真机上最值钱的能力 ——
    眼睛先读懂，手才跟得上。谱面是现场生成的小节，不涉及任何真实谱面数据。
    """
    body = """
<div class="wrap">
  <div class="hud">
    <div>进度<b id="idx">1 / 10</b></div>
    <div>答对<b id="ok">0</b></div>
    <div>正确率<b id="acc">—</b></div>
    <div>最佳<b id="best">—</b></div>
  </div>
  <canvas id="cv" width="480" height="200"></canvas>
  <div class="panel" style="margin-top:8px"><b id="ask">点「开始」出题</b></div>
  <div class="btns" id="opts"></div>
  <div class="btns"><button id="go">▶ 开始一轮（10 题）</button></div>
  <div id="codebox" style="display:none"></div>
  <div class="tip">谱面是程序按常见配置（交替 / 连打 / 双押 / BREAK 混入 / 稀疏）现场画出来的，
    不引用任何真实谱面文件。题目问的是「这段什么配置」和「有几个 BREAK」。</div>
</div>
<script>
__STORE__
__CODE__
var cv=document.getElementById('cv'),ctx=cv.getContext('2d');
var N=10,i=0,ok=0,cur=null,keys=[];
var PAT={alt:'左右交替',stream:'同轨连打',dbl:'双押',brk:'混入 BREAK',sparse:'稀疏 4 分'};
function rnd(n){return Math.floor(Math.random()*n)}
function build(){
  var ks=Object.keys(PAT),p=ks[rnd(ks.length)],notes=[],brk=0;
  var SL=32;                                     // 8 拍 × 4（16 分格）
  for(var s=0;s<SL;s++){
    if(p==='alt'){ if(s%4===0) notes.push({s:s,l:(s/4)%2?2:1,b:0}) }
    else if(p==='stream'){ if(s%2===0) notes.push({s:s,l:1+rnd(2),b:0}) }
    else if(p==='dbl'){ if(s%4===0){ notes.push({s:s,l:0,b:0}); notes.push({s:s,l:3,b:0}) } }
    else if(p==='brk'){ if(s%4===0){ notes.push({s:s,l:rnd(4),b:Math.random()<0.45?1:0}) } }
    else { if(s%8===0) notes.push({s:s,l:rnd(4),b:0}) }
  }
  for(var k=0;k<notes.length;k++) if(notes[k].b) brk++;
  return {p:p,notes:notes,brk:brk};
}
function draw(){
  ctx.clearRect(0,0,cv.width,cv.height);
  ctx.fillStyle='rgba(255,255,255,.04)';ctx.fillRect(0,0,cv.width,cv.height);
  var W=cv.width,H=cv.height,SL=32,cw=W/SL,top=34,lh=(H-top-16)/4;
  for(var l=0;l<4;l++){ ctx.fillStyle=l%2?'rgba(255,255,255,.03)':'rgba(255,255,255,.06)';
    ctx.fillRect(0,top+l*lh,W,lh) }
  ctx.strokeStyle='rgba(255,255,255,.10)';ctx.lineWidth=1;
  for(var s=0;s<=SL;s+=4){ ctx.beginPath();ctx.moveTo(s*cw,top);ctx.lineTo(s*cw,H-16);ctx.stroke() }
  for(var l=0;l<=4;l++){ ctx.beginPath();ctx.moveTo(0,top+l*lh);ctx.lineTo(W,top+l*lh);ctx.stroke() }
  if(!cur) return;
  for(var k=0;k<cur.notes.length;k++){
    var n=cur.notes[k],x=n.s*cw+cw/2,y=top+n.l*lh+lh/2,r=Math.min(cw,lh)*0.34;
    if(n.b){ ctx.fillStyle='#F5D442';ctx.beginPath();
      for(var q=0;q<10;q++){var a=Math.PI*2*q/10-Math.PI/2,rr=(q%2?r*0.5:r);
        ctx[q?'lineTo':'moveTo'](x+Math.cos(a)*rr,y+Math.sin(a)*rr)}
      ctx.closePath();ctx.fill();ctx.strokeStyle='#fff';ctx.lineWidth=1.4;ctx.stroke();
    }else{ ctx.fillStyle='#39C5BB';ctx.beginPath();ctx.arc(x,y,r,0,7);ctx.fill();
      ctx.strokeStyle='rgba(255,255,255,.7)';ctx.lineWidth=1.2;ctx.stroke() }
  }
}
function ask(){
  cur=build();
  var mode=Math.random()<0.55?'type':'brk';
  var q,ans,opts;
  if(mode==='type'){ q='这段是什么配置？'; ans=PAT[cur.p];
    opts=[ans]; var pool=Object.keys(PAT).filter(function(k){return k!==cur.p});
    while(opts.length<4){ var t=PAT[pool[rnd(pool.length)]]; if(opts.indexOf(t)<0) opts.push(t) }
    opts.sort(function(){return Math.random()-0.5});
  }else{ q='这段里有几个 BREAK（黄色星）？'; ans=String(cur.brk);
    opts=[ans]; while(opts.length<4){ var v=String(rnd(5)); if(opts.indexOf(v)<0) opts.push(v) }
    opts.sort(function(){return Math.random()-0.5});
  }
  cur.mode=mode;cur.ans=ans;
  document.getElementById('ask').textContent=q;
  var h='';opts.forEach(function(o){h+="<button class='alt' data-v='"+o+"'>"+o+"</button>"});
  document.getElementById('opts').innerHTML=h;
  Array.prototype.forEach.call(document.querySelectorAll('#opts button'),function(b){
    b.onclick=function(){pick(b.dataset.v)}});
  draw();upd();
}
function pick(v){
  var right=(v===cur.ans);
  if(right)ok++;
  var old=parseInt(__get('mph_score_best','0'),10);
  var acc=Math.round(ok/N*100);
  document.getElementById('ask').innerHTML=(right?'✅ 对':'❌ 错，答案是 <b>'+cur.ans+'</b>')
    +(cur.mode==='type'?'':'　（黄色星是 BREAK）');
  i++;
  if(i>=N){
    if(acc>old){__set('mph_score_best',String(acc));old=acc}
    document.getElementById('ask').innerHTML+='　<br><b>一轮结束：'+ok+' / '+N+
      '　正确率 '+acc+'%</b>';
    document.getElementById('opts').innerHTML="<button id='again'>↻ 再来一轮</button>";
    document.getElementById('again').onclick=function(){i=0;ok=0;ask()};
    __showCode({g:'score',t:'读谱训练',ach:acc,rk:acc>=90?'SS':acc>=70?'S':acc>=50?'A':'B',
                sc:acc*100,n:N,ok:ok});
    document.getElementById('best').textContent=old?old+'%':'—';
    upd();return;
  }
  setTimeout(ask,650);
}
function upd(){ document.getElementById('idx').textContent=Math.min(i+1,N)+' / '+N;
  document.getElementById('ok').textContent=ok;
  document.getElementById('acc').textContent=(i?Math.round(ok/i*100):'—')+'%';
  document.getElementById('best').textContent=(__get('mph_score_best','0')||'-')+
    (__get('mph_score_best','0')?'%':''); }
document.getElementById('go').onclick=function(){i=0;ok=0;ask()};
draw();upd();
</script>
"""
    return _wrap(body.replace("__STORE__", _store("mph_score_best"))
                     .replace("__CODE__", _CODE_JS),
                 "canvas{background:#080b0f;border:1px solid rgba(255,255,255,.1);"
                 "border-radius:12px;margin:6px auto}")


# ================================================================ 14) 节奏稳定性
def steady_html(height: int = 560) -> str:
    """
    比「判定偏移校准」更狠的版本：敲 32 下，看你的偏差会不会越敲越飘。
    给的是平均偏移、标准差、前后漂移和建议偏移值。
    """
    body = """
<div class="wrap">
  <div class="hud">
    <div>已敲<b id="cnt">0 / 32</b></div>
    <div>平均偏移<b id="avg">—</b></div>
    <div>波动<b id="sd">—</b></div>
    <div>漂移<b id="dr">—</b></div>
  </div>
  <canvas id="cv" width="460" height="150"></canvas>
  <div class="btns"><button id="go">▶ 开始（120 BPM × 32 拍）</button>
    <button class="alt" id="reset">↻ 重来</button></div>
  <div class="panel" id="msg">跟着节拍敲空格，敲满 32 下。看的是你越敲越准还是越敲越飘。</div>
  <div id="codebox" style="display:none"></div>
  <div class="tip">节拍是实时合成的，不是任何音频文件。标准差越小越稳；
    「漂移」是后半段平均减前半段平均，正数说明你越敲越慢。</div>
</div>
<script>
__STORE__
__CODE__
var cv=document.getElementById('cv'),ctx=cv.getContext('2d');
var BPM=120,BEAT=60000/BPM,NEED=32;
var ac=null,startT=0,beats=[],offs=[],run=false,timer=null;
function audio(){if(!ac){try{ac=new (window.AudioContext||window.webkitAudioContext)()}catch(e){ac=null}}return ac}
function clickAt(t){var a=audio();if(!a)return;
  var o=a.createOscillator(),g=a.createGain();o.type='square';o.frequency.value=1150;
  g.gain.setValueAtTime(0.0001,t);g.gain.linearRampToValueAtTime(0.11,t+0.004);
  g.gain.exponentialRampToValueAtTime(0.0001,t+0.05);
  o.connect(g);g.connect(a.destination);o.start(t);o.stop(t+0.06)}
function sched(){var a=audio();if(!a)return;
  while(beats.length<400&&beats.length*(BEAT/1000)<(a.currentTime-startT)+2){
    var t=startT+beats.length*(BEAT/1000);beats.push(t);clickAt(t)}}
function mean(a){if(!a.length)return 0;var s=0;for(var i=0;i<a.length;i++)s+=a[i];return s/a.length}
function sdv(a){if(a.length<2)return 0;var m=mean(a),s=0;
  for(var i=0;i<a.length;i++)s+=(a[i]-m)*(a[i]-m);return Math.sqrt(s/(a.length-1))}
function tap(){if(!run)return;var a=audio();if(!a)return;
  var now=a.currentTime,bi=Math.round((now-startT)/(BEAT/1000));
  if(bi<0||offs.length>=NEED)return;
  offs.push((now-(startT+bi*(BEAT/1000)))*1000);
  upd();draw();if(offs.length>=NEED)done()}
function draw(){
  ctx.clearRect(0,0,cv.width,cv.height);
  ctx.fillStyle='rgba(255,255,255,.04)';ctx.fillRect(0,0,cv.width,cv.height);
  var mid=cv.width/2;
  ctx.strokeStyle='rgba(57,197,187,.75)';ctx.lineWidth=2;
  ctx.beginPath();ctx.moveTo(mid,0);ctx.lineTo(mid,cv.height);ctx.stroke();
  ctx.strokeStyle='rgba(255,255,255,.16)';ctx.lineWidth=1;
  [-90,-45,45,90].forEach(function(v){var x=mid+v*1.1;
    ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,cv.height);ctx.stroke()});
  ctx.font='10px sans-serif';ctx.fillStyle='#7f8f96';ctx.fillText('±90ms',mid+92,12);
  if(offs.length>1){
    var step=(cv.width-20)/(NEED-1);
    ctx.beginPath();
    for(var i=0;i<offs.length;i++){
      var x=10+i*step,y=cv.height/2-Math.max(-70,Math.min(70,offs[i]))*0.85;
      i?ctx.lineTo(x,y):ctx.moveTo(x,y)}
    ctx.strokeStyle='#F5D442';ctx.lineWidth=2;ctx.stroke();
    for(var i=0;i<offs.length;i++){
      var x=10+i*step,y=cv.height/2-Math.max(-70,Math.min(70,offs[i]))*0.85;
      ctx.fillStyle=Math.abs(offs[i])<=45?'#39C5BB':Math.abs(offs[i])<=90?'#F5D442':'#E5484D';
      ctx.beginPath();ctx.arc(x,y,2.6,0,7);ctx.fill()}
  }
}
function upd(){document.getElementById('cnt').textContent=offs.length+' / '+NEED;
  document.getElementById('avg').textContent=offs.length?(mean(offs)>0?'+':'')+mean(offs).toFixed(1)+'ms':'—';
  document.getElementById('sd').textContent=offs.length>1?'±'+sdv(offs).toFixed(1)+'ms':'—';
  if(offs.length>=8){var h=offs.length>>1;
    document.getElementById('dr').textContent=((mean(offs.slice(h))-mean(offs.slice(0,h)))>0?'+':'')
      +(mean(offs.slice(h))-mean(offs.slice(0,h))).toFixed(1)+'ms'} }
function done(){
  run=false;clearInterval(timer);
  var m=mean(offs),sd=sdv(offs),h=offs.length>>1;
  var dr=mean(offs.slice(h))-mean(offs.slice(0,h));
  var rk=sd<=12?'AP':sd<=20?'SSS':sd<=30?'SS':sd<=45?'S':sd<=60?'A':'B';
  var ach=Math.max(0,100-sd*1.5);
  document.getElementById('msg').innerHTML="<div class='big'>"+rk+"</div>"
    +"平均 <b>"+(m>0?'+':'')+m.toFixed(1)+"ms</b>　波动 <b>±"+sd.toFixed(1)+"ms</b>　漂移 <b>"
    +(dr>0?'+':'')+dr.toFixed(1)+"ms</b><br>"
    +(Math.abs(m)<=20?'几乎不用调偏移。':'建议判定偏移设为 '+(m>0?'-':'+')+Math.abs(Math.round(m))+'ms。')
    +"<br><span style='color:#7f8f96'>"+(sd<=20?'手感很稳，可以冲高难度了。':
      sd<=45?'还算稳，长曲后半段注意别被带跑。':'波动偏大，先打慢歌把手感固定下来。')+"</span>";
  __set('mph_steady_best',String(Math.round(ach*100)/100));
  __showCode({g:'steady',t:'节奏稳定性',ach:Math.round(ach*100)/100,rk:rk,
              sc:Math.round(ach*1000),n:NEED,sd:Math.round(sd*100)/100,avg:Math.round(m*100)/100});
}
function start(){audio();var a=audio();
  if(!a){document.getElementById('msg').textContent='浏览器不支持 Web Audio，换 Chrome/Edge。';return}
  if(a.state==='suspended'&&a.resume)a.resume();
  beats=[];offs=[];run=true;startT=a.currentTime+0.8;
  document.getElementById('msg').textContent='跟着节拍敲空格…';
  document.getElementById('codebox').style.display='none';
  upd();draw();clearInterval(timer);timer=setInterval(sched,200);sched()}
document.addEventListener('keydown',function(e){
  if(e.code==='Space'||e.key===' '){tap();e.preventDefault()}});
cv.addEventListener('pointerdown',tap);
document.getElementById('go').onclick=start;
document.getElementById('reset').onclick=function(){run=false;clearInterval(timer);offs=[];upd();draw();
  document.getElementById('msg').textContent='跟着节拍敲空格，敲满 32 下。看的是你越敲越准还是越敲越飘。';
  document.getElementById('codebox').style.display='none'};
draw();
</script>
"""
    return _wrap(body.replace("__STORE__", _store("mph_steady_best"))
                     .replace("__CODE__", _CODE_JS),
                 "canvas{background:#080b0f;border:1px solid rgba(255,255,255,.1);"
                 "border-radius:12px;margin:6px auto}")


# ================================================================ 15) 连打耐力
def stamina_html(height: int = 560) -> str:
    """
    30 秒连打：左右手交替敲 F / J，看你能撑多少，以及后段掉速多少。
    结束后给一条 APM 曲线（每秒手速），掉速率就是「耐力」。
    """
    body = """
<div class="wrap">
  <div class="hud">
    <div>剩余<b id="left">30.0s</b></div>
    <div>总敲<b id="taps">0</b></div>
    <div>当前手速<b id="apm">0.0/s</b></div>
    <div>最佳<b id="best">—</b></div>
  </div>
  <canvas id="cv" width="460" height="150"></canvas>
  <div class="btns"><button id="go">▶ 开始（30 秒）</button>
    <button class="alt" id="reset">↻ 重来</button></div>
  <div class="panel" id="msg">交替敲 <b>F</b> 和 <b>J</b>（必须换手，连敲同一个键不算）。撑满 30 秒。</div>
  <div id="codebox" style="display:none"></div>
  <div class="tip">这是纯手速/耐力的测试，跟真实谱面无关。
    「掉速」= 后三分之一的平均手速比前三分之一掉了多少百分比，掉得越少耐力越好。</div>
</div>
<script>
__STORE__
__CODE__
var cv=document.getElementById('cv'),ctx=cv.getContext('2d');
var DUR=30,t0=0,run=false,tapT=[],last='',raf=null;
function audio(){if(!window.__ac){try{window.__ac=new (window.AudioContext||window.webkitAudioContext)()}catch(e){}}return window.__ac}
function blip(){var a=audio();if(!a)return;var o=a.createOscillator(),g=a.createGain();
  o.type='triangle';o.frequency.value=520;g.gain.setValueAtTime(0.05,a.currentTime);
  g.gain.exponentialRampToValueAtTime(0.0001,a.currentTime+0.04);
  o.connect(g);g.connect(a.destination);o.start();o.stop(a.currentTime+0.05)}
function perSec(){var b=[];for(var s=0;s<DUR;s++){var c=0;
  for(var i=0;i<tapT.length;i++){var t=tapT[i]/1000;if(t>=s&&t<s+1)c++}b.push(c)}return b}
function draw(){
  ctx.clearRect(0,0,cv.width,cv.height);
  ctx.fillStyle='rgba(255,255,255,.04)';ctx.fillRect(0,0,cv.width,cv.height);
  var b=perSec(),W=cv.width-20,H=cv.height-24,bw=(W)/DUR,mx=Math.max(4,Math.max.apply(null,b));
  for(var s=0;s<DUR;s++){
    var h=b[s]/mx*(H-10),x=10+s*bw;
    ctx.fillStyle=(tapT.length&&(tapT[tapT.length-1]/1000)>=s)?'#39C5BB':'rgba(57,197,187,.35)';
    ctx.fillRect(x,H-h+12,bw-1.2,h)}
  ctx.strokeStyle='rgba(255,255,255,.18)';ctx.lineWidth=1;
  ctx.beginPath();ctx.moveTo(10,12+H);ctx.lineTo(10+bw*DUR,12+H);ctx.stroke();
  ctx.fillStyle='#7f8f96';ctx.font='10px sans-serif';ctx.fillText('0s',10,cv.height-4);
  ctx.fillText(DUR+'s',10+bw*DUR-18,cv.height-4);
}
function loop(){
  if(!run)return;
  var el=(performance.now()-t0)/1000;
  document.getElementById('left').textContent=Math.max(0,DUR-el).toFixed(1)+'s';
  document.getElementById('taps').textContent=tapT.length;
  var c=0;for(var i=0;i<tapT.length;i++)if(tapT[i]/1000>el-1&&tapT[i]/1000<=el)c++;
  document.getElementById('apm').textContent=c.toFixed(1)+'/s';
  draw();
  if(el>=DUR){finish();return}
  raf=requestAnimationFrame(loop);
}
function tap(k){
  if(!run||k===last)return;
  last=k;blip();tapT.push(performance.now()-t0);
}
function finish(){
  run=false;
  var b=perSec(),tot=tapT.length,avg=tot/DUR;
  var seg=Math.floor(DUR/3);
  var f=0,l=0;for(var s=0;s<seg;s++)f+=b[s];for(var s=DUR-seg;s<DUR;s++)l+=b[s];
  f=f/seg;l=l/seg;
  var drop=f>0?Math.max(0,(f-l)/f*100):0;
  var pk=Math.max.apply(null,b);
  var rk=avg>=8?'鬼手':avg>=6.5?'SSS':avg>=5?'SS':avg>=3.8?'S':avg>=2.5?'A':'B';
  var ach=Math.min(100,avg/8*100);
  var old=parseFloat(__get('mph_stam_best','0'))||0;
  if(ach>old){__set('mph_stam_best',String(Math.round(ach*100)/100));old=ach}
  document.getElementById('msg').innerHTML="<div class='big'>"+rk+"</div>"
    +"总敲 <b>"+tot+"</b> 下　平均 <b>"+avg.toFixed(2)+"/s</b>　峰值 <b>"+pk+"/s</b><br>"
    +"前段 "+f.toFixed(2)+"/s → 后段 "+l.toFixed(2)+"/s　掉速 <b>"+drop.toFixed(1)+"%</b><br>"
    +"<span style='color:#7f8f96'>"+(drop<=8?'耐力惊人，后段完全没掉。':
      drop<=20?'正常范围，长曲后半段还能再压一压。':'后段掉得明显，练连打时试试放松手腕。')+"</span>";
  document.getElementById('best').textContent=old.toFixed(0)+'%';
  draw();
  __showCode({g:'stamina',t:'连打耐力',ach:Math.round(ach*100)/100,rk:rk,
              sc:Math.round(ach*1000),n:tot,avg:Math.round(avg*100)/100,drop:Math.round(drop*10)/10});
}
function start(){
  audio();t0=performance.now();run=true;tapT=[];last='';
  document.getElementById('msg').textContent='敲！F / J 交替！';
  document.getElementById('codebox').style.display='none';
  if(raf)cancelAnimationFrame(raf);loop();
}
document.addEventListener('keydown',function(e){
  var k=(e.key||'').toLowerCase();
  if(k==='f'||k==='j'){tap(k);e.preventDefault()}});
document.getElementById('go').onclick=start;
document.getElementById('reset').onclick=function(){
  run=false;if(raf)cancelAnimationFrame(raf);tapT=[];
  document.getElementById('msg').textContent='交替敲 F 和 J（必须换手，连敲同一个键不算）。撑满 30 秒。';
  document.getElementById('left').textContent=DUR.toFixed(1)+'s';
  document.getElementById('taps').textContent='0';
  document.getElementById('apm').textContent='0.0/s';
  document.getElementById('codebox').style.display='none';draw()};
document.getElementById('best').textContent=(__get('mph_stam_best','')||'—');
draw();
</script>
"""
    return _wrap(body.replace("__STORE__", _store("mph_stam_best"))
                     .replace("__CODE__", _CODE_JS),
                 "canvas{background:#080b0f;border:1px solid rgba(255,255,255,.1);"
                 "border-radius:12px;margin:6px auto}")


# ================================================================ 16) 曲库宾果
def bingo_cards(records: list[dict], seed: str = "0", n_balls: int = 24) -> dict | None:
    """
    生成一张 5×5 宾果卡（24 首真实曲目 + 中心 FREE），以及一串「开球条件」。
    每个条件都保证卡上至少有 1 格、最多 8 格能命中 —— 不会开出无解的球。
    """
    import random as _r
    pool = [r for r in (records or [])
            if (r.get("title") or "").strip() and (r.get("bpm") or 0) and r.get("ds")]
    if len(pool) < 24:
        return None
    rng = _r.Random(f"bingo-{seed}")
    picks = rng.sample(pool, 24)
    cells = [{"title": p["title"], "artist": p.get("artist") or "",
              "bpm": int(p.get("bpm") or 0), "genre": p.get("genre") or "未分类",
              "ds": round(float(p.get("ds") or 0), 1)} for p in picks]
    cells.insert(12, {"title": "FREE", "artist": "", "bpm": 0, "genre": "", "ds": 0.0, "free": True})

    def _hits(fn) -> list[int]:
        return [i for i, c in enumerate(cells) if not c.get("free") and fn(c)]

    balls, seen = [], set()
    for _ in range(n_balls * 12):
        if len(balls) >= n_balls:
            break
        kind = rng.choice(["bpm_hi", "bpm_lo", "ds_hi", "ds_lo", "genre", "title", "artist"])
        if kind == "bpm_hi":
            x = rng.choice([140, 160, 175, 185, 200])
            h, t = _hits(lambda c: c["bpm"] >= x), f"BPM ≥ {x}"
        elif kind == "bpm_lo":
            x = rng.choice([100, 120, 130, 140])
            h, t = _hits(lambda c: 0 < c["bpm"] <= x), f"BPM ≤ {x}"
        elif kind == "ds_hi":
            x = rng.choice([11.0, 12.0, 13.0, 13.5, 14.0])
            h, t = _hits(lambda c: c["ds"] >= x), f"定数 ≥ {x}"
        elif kind == "ds_lo":
            x = rng.choice([8.0, 9.0, 10.0, 11.0])
            h, t = _hits(lambda c: 0 < c["ds"] <= x), f"定数 ≤ {x}"
        elif kind == "genre":
            g = rng.choice([c["genre"] for c in cells if not c.get("free")])
            h, t = _hits(lambda c: c["genre"] == g), f"流派：{g}"
        elif kind == "title":
            w = rng.choice(cells[rng.randrange(25)]["title"])
            if not w.strip():
                continue
            h, t = _hits(lambda c: w in c["title"]), f"曲名里有「{w}」"
        else:
            src = [c["artist"] for c in cells if not c.get("free") and len(c["artist"]) >= 2]
            if not src:
                continue
            a = rng.choice(src)
            w = a[:2]
            h, t = _hits(lambda c: w in c["artist"]), f"艺人名带「{w}」"
        if not (1 <= len(h) <= 8) or t in seen:
            continue
        seen.add(t)
        balls.append({"text": t, "hits": h})
    if len(balls) < 8:
        return None
    return {"cells": cells, "balls": balls}


def bingo_html(cards: dict, height: int = 640) -> str:
    """
    曲库宾果：卡上是 24 首真实曲目，每开一球给一个条件（BPM / 定数 / 流派 / 曲名），
    你找出卡上满足条件的那格点掉它。先连成一条线就 BINGO。
    """
    import json as _j
    data = _j.dumps(cards or {}, ensure_ascii=False)
    body = """
<div class="wrap">
  <div class="hud">
    <div>已标记<b id="mk">1</b></div>
    <div>用时<b id="tm">0s</b></div>
    <div>开球<b id="bn">0</b></div>
    <div>状态<b id="stt">准备</b></div>
  </div>
  <div class="panel" id="ball" style="text-align:center">点「开始」发第一球</div>
  <div id="grid" style="display:grid;grid-template-columns:repeat(5,1fr);gap:4px;margin:8px 0"></div>
  <div class="btns">
    <button id="go">▶ 开始</button>
    <button class="alt" id="next">🎱 下一球</button>
    <button class="alt" id="new">🆕 换一张卡</button>
  </div>
  <div id="codebox" style="display:none"></div>
  <div class="tip">格子里的曲名全部来自本地曲库快照。点错不扣东西，但会提示你再找找 ——
    这游戏考的不是手速，是你对曲库熟不熟。</div>
</div>
<script>
__STORE__
__CODE__
var CARD=__DATA__;
var marked={12:1},bi=0,t0=0,timer=null,run=false,wrong=0;
function render(){
  var h='';
  CARD.cells.forEach(function(c,i){
    var on=marked[i];
    var bg=on?'rgba(57,197,187,.30)':'rgba(255,255,255,.05)';
    var bd=on?'#39C5BB':'rgba(255,255,255,.13)';
    var sub=c.free?'':('<span style="font-size:9px;color:#7f8f96">'+c.bpm+' · '+c.ds+'</span>');
    h+="<div data-i='"+i+"' style='background:"+bg+";border:1px solid "+bd+";border-radius:9px;"
      +"padding:6px 3px;min-height:58px;display:flex;flex-direction:column;justify-content:center;"
      +"cursor:pointer;font-size:10px;line-height:1.25;overflow:hidden'>"
      +"<div style='font-weight:700;color:"+(on?'#9fe8e2':'#dff0ef')+"'>"+c.title+"</div>"+sub+"</div>";
  });
  document.getElementById('grid').innerHTML=h;
  Array.prototype.forEach.call(document.querySelectorAll('#grid div'),function(d){
    d.onclick=function(){clickCell(+d.dataset.i)}});
  document.getElementById('mk').textContent=Object.keys(marked).length;
}
function nextBall(){
  if(bi>=CARD.balls.length){document.getElementById('ball').textContent='球用完了，换张卡再来。';return}
  var b=CARD.balls[bi];
  document.getElementById('ball').innerHTML="<b style='font-size:15px;color:#F5D442'>🎱 "+b.text+"</b>"
    +"<div style='font-size:11px;color:#7f8f96;margin-top:3px'>在卡上找出满足这一条的格子，点它</div>";
  document.getElementById('bn').textContent=(bi+1)+' / '+CARD.balls.length;
}
function clickCell(i){
  if(!run||marked[i])return;
  var b=CARD.balls[bi]; if(!b)return;
  if(b.hits.indexOf(i)>=0){
    marked[i]=1;bi++;wrong=0;render();
    if(bingo()){win();return}
    nextBall();
  }else{
    wrong++;
    document.getElementById('ball').innerHTML="<b style='color:#E5484D'>✗ 这格不满足，再找找</b>"
      +"<div style='font-size:11px;color:#7f8f96;margin-top:3px'>🎱 "+b.text+"</div>";
  }
}
function lines(){
  var L=[];
  for(var r=0;r<5;r++){var a=[];for(var c=0;c<5;c++)a.push(r*5+c);L.push(a)}
  for(var c=0;c<5;c++){var a=[];for(var r=0;r<5;r++)a.push(r*5+c);L.push(a)}
  L.push([0,6,12,18,24]);L.push([4,8,12,16,20]);
  return L;
}
function bingo(){
  var ls=lines();
  for(var i=0;i<ls.length;i++){
    var ok=true;for(var k=0;k<5;k++)if(!marked[ls[i][k]]){ok=false;break}
    if(ok)return true;
  }
  return false;
}
function win(){
  run=false;clearInterval(timer);
  var el=Math.round((Date.now()-t0)/1000);
  var n=Object.keys(marked).length;
  var ach=Math.min(100,Math.max(20,100-el*0.6));
  document.getElementById('stt').textContent='BINGO';
  document.getElementById('ball').innerHTML="<div class='big'>BINGO!</div>用时 "+el+"s　开球 "+(bi+1)
    +" 个　标记 "+n+" 格";
  __showCode({g:'bingo',t:'曲库宾果',ach:Math.round(ach*100)/100,rk:el<=40?'SSS':el<=70?'SS':el<=110?'S':'A',
              sc:Math.round(ach*1000),n:n,sec:el});
}
function start(){
  marked={12:1};bi=0;wrong=0;run=true;t0=Date.now();
  document.getElementById('stt').textContent='进行中';
  clearInterval(timer);
  timer=setInterval(function(){
    if(run)document.getElementById('tm').textContent=Math.round((Date.now()-t0)/1000)+'s'},500);
  render();nextBall();
}
document.getElementById('go').onclick=start;
document.getElementById('next').onclick=function(){if(run&&bi<CARD.balls.length-1){bi++;nextBall()}};
document.getElementById('new').onclick=function(){location.reload()};
render();
</script>
"""
    return _wrap(body.replace("__STORE__", _store("mph_bingo"))
                     .replace("__CODE__", _CODE_JS)
                     .replace("__DATA__", data),
                 "#grid div{transition:.15s}#grid div:hover{filter:brightness(1.25)}")


# ================================================================ 18) 判定偏移挑战
def judge_html(height: int = 620) -> str:
    """
    判定偏移挑战：四段不同 BPM（90 / 120 / 150 / 180）各敲 8 下，中间不停，
    实时画偏差散点 + 最近 5 下的移动平均线，结束后给「逐段偏移趋势」和一个建议偏移值。
    跟固定 BPM 的校准不一样 —— 这里看的是你的偏移会不会跟着曲速跑。
    """
    body = """
<div class="wrap">
  <div class="hud">
    <div>当前 BPM<b id="bpm">90</b></div>
    <div>已敲<b id="cnt">0 / 32</b></div>
    <div>移动平均<b id="ma">—</b></div>
    <div>本段均值<b id="sg">—</b></div>
  </div>
  <canvas id="cv" width="480" height="200"></canvas>
  <div class="btns"><button id="go">▶ 开始（4 段 × 8 拍）</button>
    <button class="alt" id="reset">↻ 重来</button></div>
  <div class="panel" id="msg">四段 BPM 依次来：<b>90 → 120 → 150 → 180</b>，每段敲 8 下空格（或点画布）。<br>
    慢速敲完直接切快，中间不停 —— 看的是速度变了你会不会跟着飘。</div>
  <div id="codebox" style="display:none"></div>
  <div class="tip">节拍是实时合成的，不是任何音频文件。散点图里<b>上=偏早、下=偏晚</b>，
    黄线是最近 5 下的移动平均，背景色带就是四个 BPM 段。<br>
    最后会给每一段各自的平均偏移：如果慢速和快速的建议值差很多，说明你的偏移是跟着曲速走的。</div>
</div>
<script>
__STORE__
__CODE__
var cv=document.getElementById('cv'),ctx=cv.getContext('2d');
var SEGS=[90,120,150,180],PER=8,TOT=SEGS.length*PER;
var ac=null,startT=0,beats=[],offs=[],used=[],run=false,over=false;
function audio(){if(!ac){try{ac=new (window.AudioContext||window.webkitAudioContext)()}catch(e){ac=null}}return ac}
function clickAt(t,f,v){var a=audio();if(!a)return;
  var o=a.createOscillator(),g=a.createGain();o.type='square';o.frequency.value=f;
  g.gain.setValueAtTime(0.0001,t);g.gain.linearRampToValueAtTime(v,t+0.004);
  g.gain.exponentialRampToValueAtTime(0.0001,t+0.05);
  o.connect(g);g.connect(a.destination);o.start(t);o.stop(t+0.06)}
function mean(a){var s=0;for(var i=0;i<a.length;i++)s+=a[i];return a.length?s/a.length:0}
function sdv(a){if(a.length<2)return 0;var m=mean(a),s=0;
  for(var i=0;i<a.length;i++)s+=(a[i]-m)*(a[i]-m);return Math.sqrt(s/(a.length-1))}
function build(){beats=[];used=[];var t=startT;
  for(var s=0;s<SEGS.length;s++){var bt=60/SEGS[s];
    for(var i=0;i<PER;i++){beats.push({t:t,seg:s});used.push(0);t+=bt}}
  for(var k=0;k<beats.length;k++)clickAt(beats[k].t,beats[k].seg%2?920:1250,0.1);
  for(var s2=0;s2<SEGS.length;s2++)clickAt(beats[s2*PER].t-0.13,470+s2*80,0.07)}
function curBpm(){var a=audio();if(!a)return SEGS[0];
  var now=a.currentTime,i;
  for(i=beats.length-1;i>=0;i--){if(now>=beats[i].t)return SEGS[beats[i].seg]}
  return SEGS[0]}
function tap(){if(!run||over)return;var a=audio();if(!a)return;
  var now=a.currentTime,bi=-1,bd=1e9;
  for(var i=0;i<beats.length;i++){if(used[i])continue;
    var d=Math.abs(beats[i].t-now);if(d<bd){bd=d;bi=i}}
  if(bi<0)return;
  var prev=bi>0?beats[bi-1].t:beats[bi].t-0.5;
  var next=bi<beats.length-1?beats[bi+1].t:beats[bi].t+0.5;
  if(bd>Math.min(beats[bi].t-prev,next-beats[bi].t)/2)return;
  used[bi]=1;
  offs.push({off:(now-beats[bi].t)*1000,seg:beats[bi].seg});
  upd();draw();
  if(offs.length>=TOT)finish()}
function upd(){
  document.getElementById('cnt').textContent=offs.length+' / '+TOT;
  document.getElementById('bpm').textContent=curBpm();
  if(offs.length){
    var st=Math.max(0,offs.length-5),sm=0,cn=0;
    for(var i=st;i<offs.length;i++){sm+=offs[i].off;cn++}
    var m=sm/cn;
    document.getElementById('ma').textContent=(m>0?'+':'')+m.toFixed(1)+'ms';
  }else document.getElementById('ma').textContent='—';
  var last=offs.length?offs[offs.length-1].seg:-1;
  if(last>=0){var sa=[];
    for(var i2=0;i2<offs.length;i2++)if(offs[i2].seg===last)sa.push(offs[i2].off);
    var mm=mean(sa);
    document.getElementById('sg').textContent=(mm>0?'+':'')+mm.toFixed(1)+'ms';
  }else document.getElementById('sg').textContent='—';
}
function draw(){
  ctx.clearRect(0,0,cv.width,cv.height);
  ctx.fillStyle='rgba(255,255,255,.04)';ctx.fillRect(0,0,cv.width,cv.height);
  var W=cv.width,H=cv.height,mid=H/2-8,pad=14,step=(W-pad*2)/(TOT-1);
  for(var s=0;s<SEGS.length;s++){
    var x0=pad+s*PER*step-step/2,x1=pad+(s+1)*PER*step-step/2;
    ctx.fillStyle=s%2?'rgba(57,197,187,.06)':'rgba(166,107,255,.06)';
    ctx.fillRect(x0,0,x1-x0,H-18)}
  ctx.strokeStyle='rgba(255,255,255,.14)';ctx.lineWidth=1;
  [-90,-45,45,90].forEach(function(v){ctx.beginPath();
    ctx.moveTo(pad,mid+v*0.62);ctx.lineTo(W-pad,mid+v*0.62);ctx.stroke()});
  ctx.strokeStyle='rgba(57,197,187,.75)';ctx.lineWidth=2;
  ctx.beginPath();ctx.moveTo(pad,mid);ctx.lineTo(W-pad,mid);ctx.stroke();
  ctx.font='10px sans-serif';ctx.fillStyle='#7f8f96';
  ctx.fillText('早',pad+3,13);ctx.fillText('晚',pad+3,H-22);
  ctx.fillText('±90ms',W-52,13);
  if(offs.length>=2){
    ctx.beginPath();
    for(var i=0;i<offs.length;i++){
      var st2=Math.max(0,i-4),sm2=0,cn2=0;
      for(var k=st2;k<=i;k++){sm2+=offs[k].off;cn2++}
      var y=mid+Math.max(-130,Math.min(130,sm2/cn2))*0.62;
      i?ctx.lineTo(pad+i*step,y):ctx.moveTo(pad+i*step,y)}
    ctx.strokeStyle='#F5D442';ctx.lineWidth=2;ctx.stroke()}
  for(var i2=0;i2<offs.length;i2++){
    var o=offs[i2].off,y2=mid+Math.max(-130,Math.min(130,o))*0.62;
    ctx.fillStyle=Math.abs(o)<=45?'#39C5BB':Math.abs(o)<=90?'#F5D442':'#E5484D';
    ctx.beginPath();ctx.arc(pad+i2*step,y2,3,0,7);ctx.fill()}
  ctx.strokeStyle='rgba(255,255,255,.22)';ctx.lineWidth=1;
  for(var s3=1;s3<SEGS.length;s3++){
    var xx=pad+s3*PER*step-step/2;
    ctx.beginPath();ctx.moveTo(xx,0);ctx.lineTo(xx,H-18);ctx.stroke()}
  for(var s4=0;s4<SEGS.length;s4++){
    ctx.fillStyle='#7f8f96';
    ctx.fillText(SEGS[s4]+'',pad+(s4*PER+PER/2-0.5)*step,H-5)}
}
function finish(){
  run=false;over=true;
  var all=[],segs=[];
  for(var i=0;i<offs.length;i++)all.push(offs[i].off);
  for(var s=0;s<SEGS.length;s++){var a2=[];
    for(var i2=0;i2<offs.length;i2++)if(offs[i2].seg===s)a2.push(offs[i2].off);
    segs.push(a2.length?mean(a2):0)}
  var m=mean(all),sd=sdv(all);
  var mx=Math.max.apply(null,segs),mn=Math.min.apply(null,segs),spread=mx-mn;
  var trend=segs[SEGS.length-1]-segs[0];
  var rk=sd<=12&&spread<=15?'SSS+':sd<=18&&spread<=25?'SSS':sd<=26&&spread<=35?'SS':sd<=36?'S':sd<=50?'A':'B';
  var ach=Math.max(0,100-sd*1.2-spread*0.6);
  var sug=-Math.round(m);
  var h='';
  for(var s2=0;s2<SEGS.length;s2++){
    var v=segs[s2];
    h+="<span style='color:#9fe8e2'>"+SEGS[s2]+"</span> "+(v>0?'+':'')+v.toFixed(1)+"ms　"}
  var cmt=spread<=15?'各段偏移基本一致，一个固定值就够用。':
          (trend>0?'曲速越快你敲得越晚':'曲速越快你敲得越早')+'，前后差 '
          +Math.abs(trend).toFixed(0)+'ms，快歌建议单独再调一次。';
  document.getElementById('msg').innerHTML="<div class='big'>"+rk+"</div>"
    +"整体平均 <b>"+(m>0?'+':'')+m.toFixed(1)+"ms</b>　波动 <b>±"+sd.toFixed(1)
    +"ms</b>　段间极差 <b>"+spread.toFixed(1)+"ms</b><br>"
    +"<span style='color:#7f8f96'>逐段趋势："+h+"</span><br>"
    +(Math.abs(m)<=20?'几乎不用调偏移。':'建议判定偏移设为 '+(sug>0?'+':'')+sug+'ms。')
    +"<br><span style='color:#7f8f96'>"+cmt+"</span>";
  var old=parseFloat(__get('mph_judge_best','0'))||0;
  if(ach>old){__set('mph_judge_best',String(Math.round(ach*100)/100));old=ach}
  __showCode({g:'judge',t:'判定偏移挑战',ach:Math.round(ach*100)/100,rk:rk,
              sc:Math.round(ach*1000),n:offs.length,sd:Math.round(sd*100)/100,
              avg:Math.round(m*100)/100,spread:Math.round(spread*100)/100});
}
function start(){audio();var a=audio();
  if(!a){document.getElementById('msg').textContent='这个浏览器不支持 Web Audio，换 Chrome/Edge 试试。';return}
  if(a.state==='suspended'&&a.resume)a.resume();
  offs=[];over=false;run=true;startT=a.currentTime+1.0;build();
  document.getElementById('msg').innerHTML='跟着节拍敲空格…（90 → 120 → 150 → 180）';
  document.getElementById('codebox').style.display='none';
  upd();draw()}
document.addEventListener('keydown',function(e){
  if(e.code==='Space'||e.key===' '){tap();e.preventDefault()}});
cv.addEventListener('pointerdown',tap);
document.getElementById('go').onclick=start;
document.getElementById('reset').onclick=function(){run=false;over=false;offs=[];
  document.getElementById('msg').innerHTML='四段 BPM 依次来：<b>90 → 120 → 150 → 180</b>，'
    +'每段敲 8 下空格（或点画布）。<br>慢速敲完直接切快，中间不停 —— 看的是速度变了你会不会跟着飘。';
  document.getElementById('codebox').style.display='none';upd();draw()};
draw();
</script>
"""
    return _wrap(body.replace("__STORE__", _store("mph_judge_best"))
                     .replace("__CODE__", _CODE_JS),
                 "canvas{background:#080b0f;border:1px solid rgba(255,255,255,.1);"
                 "border-radius:12px;margin:6px auto}")


# ================================================================ 19) 双押拆解
def chord_html(height: int = 640) -> str:
    """
    双押拆解：圆环上同时亮 2~3 个方位，你要在极短窗口内把它们「一次」按下去。
    判的不是按没按到，是两个键落下的时间差 —— 差超过 40ms 就算拆开了，
    快歌里那就会变成一个 PERFECT 一个 GREAT。
    """
    body = """
<div class="wrap">
  <div class="hud">
    <div>轮次<b id="rd">0 / 12</b></div>
    <div>完全同时<b id="sr">—</b></div>
    <div>最大同押<b id="mc">—</b></div>
    <div>连击<b id="cb">0</b></div>
    <div>最佳<b id="best">—</b></div>
  </div>
  <div class="stage">
    <canvas id="cv" width="480" height="290"></canvas>
    <div class="center" id="jd"></div>
  </div>
  <div class="btns"><button id="go">▶ 开始（12 轮）</button>
    <button class="alt" id="reset">↻ 重来</button></div>
  <div class="panel" id="msg">圆环上会同时亮 <b>2~3 个方位</b>，把对应的键<b>同时</b>按下去。<br>
    键盘 <b>1~8</b> 对应顺时针八个方位（正上方是 1），也可以直接点/戳圆环上那一格。</div>
  <div id="codebox" style="display:none"></div>
  <div class="tip">「完全同时」= 这一轮所有键落下的时间差在 <b>40ms 以内</b>。<br>
    真机上双押被拆开是最隐蔽的失分项 —— 表面上是两个 GREAT，实际是你两只手差了一点点。</div>
</div>
<script>
__STORE__
__CODE__
var cv=document.getElementById('cv'),ctx=cv.getContext('2d');
var CX=cv.width/2,CY=cv.height/2,R=100;
var ROUNDS=12,SIM=40;
var FREQ=[523,587,659,784,880,988,1175,1319];
var ac=null;
var ri=0,hit=0,sim=0,maxChord=0,combo=0,mxCombo=0,spreads=[];
var need=[],pressed={},tOpen=0,win=900,state='idle',raf=null;
function audio(){if(!ac){try{ac=new (window.AudioContext||window.webkitAudioContext)()}catch(e){ac=null}}return ac}
function tone(i,v){var a=audio();if(!a)return;
  var o=a.createOscillator(),g=a.createGain();o.type='triangle';o.frequency.value=FREQ[i];
  g.gain.setValueAtTime(0.0001,a.currentTime);
  g.gain.linearRampToValueAtTime(v||0.09,a.currentTime+0.005);
  g.gain.exponentialRampToValueAtTime(0.0001,a.currentTime+0.16);
  o.connect(g);g.connect(a.destination);o.start();o.stop(a.currentTime+0.18)}
function mean(a){if(!a.length)return 0;var s=0;for(var i=0;i<a.length;i++)s+=a[i];return s/a.length}
function angOf(i){return -Math.PI/2+i*Math.PI/4}
function px(i){return CX+Math.cos(angOf(i))*R}
function py(i){return CY+Math.sin(angOf(i))*R}
function say(t,c){var el=document.getElementById('jd');el.textContent=t;el.style.color=c;
  el.style.opacity=1;clearTimeout(el._t);el._t=setTimeout(function(){el.style.opacity=0},420)}
function upd(){document.getElementById('rd').textContent=ri+' / '+ROUNDS;
  document.getElementById('sr').textContent=hit?Math.round(sim/hit*100)+'%':'—';
  document.getElementById('mc').textContent=maxChord?maxChord+' 键':'—';
  document.getElementById('cb').textContent=combo}
function draw(){
  ctx.clearRect(0,0,cv.width,cv.height);
  ctx.strokeStyle='rgba(255,255,255,.10)';ctx.lineWidth=1;
  ctx.beginPath();ctx.arc(CX,CY,R,0,7);ctx.stroke();
  ctx.beginPath();ctx.arc(CX,CY,R*0.42,0,7);ctx.stroke();
  var left=state==='open'?Math.max(0,win-(performance.now()-tOpen)):0;
  for(var i=0;i<8;i++){
    var x=px(i),y=py(i),on=need.indexOf(i)>=0,done=!!pressed[i];
    ctx.beginPath();ctx.arc(x,y,21,0,7);
    ctx.fillStyle=on?(done?'rgba(57,197,187,.85)':'rgba(245,212,66,.9)'):'rgba(255,255,255,.06)';
    ctx.fill();
    ctx.strokeStyle=on?'#fff':'rgba(255,255,255,.16)';ctx.lineWidth=on?2:1;ctx.stroke();
    if(on&&!done){
      ctx.beginPath();ctx.arc(x,y,34-22*(1-left/win),0,7);
      ctx.strokeStyle='rgba(57,197,187,.8)';ctx.lineWidth=3;ctx.stroke()}
    ctx.font='12px sans-serif';ctx.fillStyle=on?'#04222a':'#7f8f96';ctx.textAlign='center';
    ctx.fillText(String(i+1),x,y+4);ctx.textAlign='left';}
  ctx.textAlign='center';
  if(state==='open'){
    ctx.fillStyle='#39C5BB';ctx.font='13px sans-serif';
    ctx.fillText(need.length+' 押 · 剩 '+(left/1000).toFixed(2)+'s',CX,26);
    var w=260,x0=CX-w/2;
    ctx.fillStyle='rgba(255,255,255,.10)';ctx.fillRect(x0,CY+R+28,w,5);
    ctx.fillStyle=left/win>0.4?'#39C5BB':'#E5484D';ctx.fillRect(x0,CY+R+28,w*(left/win),5);
  }else{
    ctx.fillStyle='#7f8f96';ctx.font='12px sans-serif';
    ctx.fillText('点「开始」出题',CX,26)}
  ctx.textAlign='left';
}
function loop(){if(raf)cancelAnimationFrame(raf);
  draw();
  if(state==='open'&&performance.now()-tOpen>win){miss()}
  raf=requestAnimationFrame(loop)}
function miss(){state='idle';combo=0;say('MISS','#E5484D');ri++;upd();
  setTimeout(nextRound,420)}
function resolve(){
  state='idle';
  var ts=[],i;
  for(i=0;i<need.length;i++)ts.push(pressed[need[i]]);
  var mx=Math.max.apply(null,ts),mn=Math.min.apply(null,ts),spread=mx-mn;
  var late=performance.now()-tOpen;
  if(late>win){miss();return}
  hit++;combo++;if(combo>mxCombo)mxCombo=combo;
  spreads.push(spread);
  var isSim=spread<=SIM;
  if(isSim)sim++;
  if(need.length>maxChord)maxChord=need.length;
  say(isSim?'同时 '+spread+'ms':'拆开 '+spread+'ms',isSim?'#39C5BB':'#F5D442');
  ri++;upd();setTimeout(nextRound,420)}
function press(p){
  if(state!=='open')return;
  if(need.indexOf(p)<0){miss();return}
  if(pressed[p])return;
  pressed[p]=performance.now();tone(p,0.1);draw();
  for(var i=0;i<need.length;i++)if(!pressed[need[i]])return;
  resolve()}
function nextRound(){
  if(ri>=ROUNDS){finish();return}
  var k=2;
  if(ri>=3&&Math.random()<0.5)k=3;
  if(ri>=8&&Math.random()<0.7)k=3;
  var pool=[0,1,2,3,4,5,6,7];need=[];
  for(var i=0;i<k;i++){var q=Math.floor(Math.random()*pool.length);need.push(pool[q]);pool.splice(q,1)}
  pressed={};win=Math.max(560,900-ri*28);tOpen=performance.now();state='open';
  for(var j=0;j<need.length;j++)tone(need[j],0.07);
  upd();loop()}
function finish(){
  state='idle';need=[];
  var rate=Math.round(hit/ROUNDS*100),simRate=hit?Math.round(sim/hit*100):0;
  var asp=Math.round(mean(spreads));
  var rk=rate>=95&&simRate>=80?'SSS+':rate>=90&&simRate>=65?'SSS':
         rate>=80&&simRate>=45?'SS':rate>=65?'S':rate>=50?'A':'B';
  var ach=Math.round(rate*0.6+simRate*0.4);
  var cmt=simRate>=80?'双手是同时落下的，双押不会被拆 —— 打快歌很占便宜。':
          simRate>=50?'大部分双押能同时按下，再快的谱就有点撑不住了。':
          '你的双押基本是先后按的，快歌里会偷偷变成一好一坏，刻意练「一起落手」。';
  document.getElementById('msg').innerHTML="<div class='big'>"+rk+"</div>"
    +"命中 <b>"+hit+" / "+ROUNDS+"</b>　完全同时 <b>"+simRate+"%</b>　最大同押 <b>"
    +(maxChord||0)+" 键</b><br>平均落手间隔 <b>"+asp+"ms</b>　最长连击 <b>"+mxCombo+"</b><br>"
    +"<span style='color:#7f8f96'>"+cmt+"</span>";
  var old=parseFloat(__get('mph_chord_best','0'))||0;
  if(ach>old){__set('mph_chord_best',String(ach));old=ach}
  document.getElementById('best').textContent=old?old+'%':'—';
  draw();
  __showCode({g:'chord',t:'双押拆解',ach:ach,rk:rk,sc:ach*1000,n:ROUNDS,
              hit:hit,sim:sim,mc:maxChord,asp:asp});
}
function start(){audio();ri=0;hit=0;sim=0;maxChord=0;combo=0;mxCombo=0;spreads=[];need=[];state='idle';
  document.getElementById('msg').innerHTML='圆环上会同时亮 <b>2~3 个方位</b>，'
    +'把对应的键<b>同时</b>按下去。<br>键盘 <b>1~8</b> 对应顺时针八个方位（正上方是 1）。';
  document.getElementById('codebox').style.display='none';
  document.getElementById('best').textContent=__get('mph_chord_best','')||'—';
  upd();draw();nextRound()}
document.addEventListener('keydown',function(e){
  var k=(e.key||'');
  if(k>='1'&&k<='8'){press(parseInt(k,10)-1);e.preventDefault()}});
cv.addEventListener('pointerdown',function(e){
  var r=cv.getBoundingClientRect();
  var x=(e.clientX-r.left)*(cv.width/r.width)-CX,y=(e.clientY-r.top)*(cv.height/r.height)-CY;
  var v=Math.round((Math.atan2(y,x)+Math.PI/2)/(Math.PI/4));
  press(((v%8)+8)%8)});
document.getElementById('go').onclick=start;
document.getElementById('reset').onclick=function(){state='idle';need=[];ri=0;hit=0;sim=0;
  maxChord=0;combo=0;spreads=[];
  document.getElementById('msg').innerHTML='圆环上会同时亮 <b>2~3 个方位</b>，'
    +'把对应的键<b>同时</b>按下去。<br>键盘 <b>1~8</b> 对应顺时针八个方位（正上方是 1）。';
  document.getElementById('codebox').style.display='none';upd();draw()};
document.getElementById('best').textContent=__get('mph_chord_best','')||'—';
draw();
</script>
"""
    return _wrap(body.replace("__STORE__", _store("mph_chord_best"))
                     .replace("__CODE__", _CODE_JS),
                 "canvas{background:#080b0f;border:1px solid rgba(255,255,255,.1);"
                 "border-radius:12px;margin:6px auto}.center{font-size:20px}")


# ================================================================ 20) 谱面记忆复述
def echo_html(height: int = 600) -> str:
    """
    谱面记忆复述：先放一小段（方位 + 节奏）给你听，再让你凭记忆敲回来。
    方位错了或者漏敲就直接结束；每过一轮序列加长一个，最长 8 个。
    跟「音符记忆」的区别是这里连节奏一起考 —— 间隔也要敲得差不多。
    """
    body = """
<div class="wrap">
  <div class="hud">
    <div>轮次<b id="rd">0</b></div>
    <div>序列长度<b id="ln">3</b></div>
    <div>已复述<b id="ps">0 / 3</b></div>
    <div>节奏误差<b id="er">—</b></div>
    <div>最佳<b id="best">—</b></div>
  </div>
  <canvas id="cv" width="480" height="170"></canvas>
  <div class="btns"><button id="go">▶ 开始（从 3 个音起）</button>
    <button class="alt" id="reset">↻ 重来</button></div>
  <div class="panel" id="msg">先<b>听</b>一遍：四个圆会按节奏亮起来，各自音高不同。<br>
    放完之后轮到你 —— 用 <b>D F J K</b>（或点画面）把<b>方位和节奏</b>原样敲回来。</div>
  <div id="codebox" style="display:none"></div>
  <div class="tip">判定：<b>方位必须完全一致</b>（错一个就结束），间隔误差累计超过 900ms 也算漏。<br>
    每过一轮序列加一个音，最长 8 个。音是实时合成的，四个方位四个音高。</div>
</div>
<script>
__STORE__
__CODE__
var cv=document.getElementById('cv'),ctx=cv.getContext('2d');
var START=3,MAXLEN=8,GAPS=[250,375,500];
var FREQ=[523,659,784,1047],KEYN=['D','F','J','K'];
var ac=null;
var seq=[],cum=[],len=START,maxLen=0,round=0,errs=[],pos=0,curLit=-1,flash=-1;
var state='idle',baseT=0,inT0=0,raf=null,flashT=0;
function audio(){if(!ac){try{ac=new (window.AudioContext||window.webkitAudioContext)()}catch(e){ac=null}}return ac}
function toneAt(t,i){var a=audio();if(!a)return;
  var o=a.createOscillator(),g=a.createGain();o.type='sine';o.frequency.value=FREQ[i];
  g.gain.setValueAtTime(0.0001,t);g.gain.linearRampToValueAtTime(0.14,t+0.008);
  g.gain.exponentialRampToValueAtTime(0.0001,t+0.22);
  o.connect(g);g.connect(a.destination);o.start(t);o.stop(t+0.24)}
function tone(i){var a=audio();if(!a)return;toneAt(a.currentTime,i)}
function bad(){var a=audio();if(!a)return;
  var o=a.createOscillator(),g=a.createGain();o.type='sawtooth';o.frequency.value=150;
  g.gain.setValueAtTime(0.0001,a.currentTime);g.gain.linearRampToValueAtTime(0.1,a.currentTime+0.01);
  g.gain.exponentialRampToValueAtTime(0.0001,a.currentTime+0.3);
  o.connect(g);g.connect(a.destination);o.start();o.stop(a.currentTime+0.32)}
function mean(a){if(!a.length)return 0;var s=0;for(var i=0;i<a.length;i++)s+=a[i];return s/a.length}
function makeSeq(n){var s=[];
  for(var i=0;i<n;i++)s.push({lane:Math.floor(Math.random()*4),
    gap:i?GAPS[Math.floor(Math.random()*GAPS.length)]:0});
  return s}
function upd(){document.getElementById('rd').textContent=round;
  document.getElementById('ln').textContent=len;
  document.getElementById('ps').textContent=(state==='in'?pos:0)+' / '+seq.length;
  var ae=0;for(var i=0;i<errs.length;i++)ae+=Math.abs(errs[i]);
  document.getElementById('er').textContent=errs.length?Math.round(ae/errs.length)+'ms':'—'}
function draw(){
  ctx.clearRect(0,0,cv.width,cv.height);
  ctx.fillStyle='rgba(255,255,255,.04)';ctx.fillRect(0,0,cv.width,cv.height);
  var W=cv.width,cw=W/4,cy=62;
  for(var i=0;i<4;i++){
    var x=cw*i+cw/2,lit=(state==='play'&&curLit===i)||(state==='in'&&flash===i);
    ctx.beginPath();ctx.arc(x,cy,27,0,7);
    ctx.fillStyle=lit?'#F5D442':'rgba(255,255,255,.07)';ctx.fill();
    ctx.strokeStyle=lit?'#fff':'rgba(255,255,255,.18)';ctx.lineWidth=lit?2.4:1;ctx.stroke();
    ctx.font='15px sans-serif';ctx.textAlign='center';
    ctx.fillStyle=lit?'#04222a':'#7f8f96';ctx.fillText(KEYN[i],x,cy+6)}
  ctx.font='11px sans-serif';ctx.fillStyle='#7f8f96';ctx.textAlign='center';
  ctx.fillText(state==='play'?'听…':state==='in'?'敲回来':state==='over'?'结束':'点「开始」',W/2,18);
  var n=seq.length||START,d=26,x0=W/2-n*d/2+d/2,y0=132;
  for(var k=0;k<n;k++){
    var xx=x0+k*d,filled=false,col='#39C5BB',txt='';
    if(state==='play'){filled=(k<=curLit);col='#F5D442'}
    else if(state==='in'){filled=(k<pos);col='#39C5BB'}
    else if(state==='over'){filled=true;col='rgba(255,255,255,.25)';txt=String(seq[k].lane+1)}
    ctx.beginPath();ctx.arc(xx,y0,9,0,7);
    ctx.fillStyle=filled?col:'rgba(255,255,255,.08)';ctx.fill();
    if(txt){ctx.fillStyle='#e6f1f0';ctx.font='10px sans-serif';ctx.fillText(txt,xx,y0+3)}}
  ctx.textAlign='left';
}
function loop(){
  if(raf)cancelAnimationFrame(raf);
  var a=audio();
  if(state==='play'&&a){
    var now=a.currentTime,cur=-1;
    for(var i=0;i<seq.length;i++){
      var t=baseT+cum[i]/1000;                 /* cum 是毫秒，baseT 是秒 */
      if(now>=t&&now<t+0.16)cur=i}
    curLit=cur;
    if(now>baseT+cum[seq.length-1]/1000+0.45){toInput();return}
  }
  if(state==='in'&&pos>0&&performance.now()-inT0>cum[pos]+900){
    fail('漏了 —— 第 '+(pos+1)+' 个音没敲出来');return}
  draw();
  raf=requestAnimationFrame(loop)}
function play(){
  seq=makeSeq(len);cum=[0];
  var t=0;
  for(var i=1;i<seq.length;i++){t+=seq[i].gap;cum.push(t)}
  var a=audio();
  if(!a){document.getElementById('msg').textContent='这个浏览器不支持 Web Audio，换 Chrome/Edge 试试。';return}
  if(a.state==='suspended'&&a.resume)a.resume();
  baseT=a.currentTime+0.7;state='play';curLit=-1;pos=0;errs=[];
  for(var j=0;j<seq.length;j++)toneAt(baseT+cum[j]/1000,seq[j].lane);
  document.getElementById('msg').innerHTML='听好了…（'+len+' 个音）';
  upd();loop()}
function toInput(){
  state='in';curLit=-1;inT0=0;pos=0;
  document.getElementById('msg').innerHTML='<b>该你了</b> —— 把方位和节奏原样敲回来。';
  draw();loop()}
function tapLane(l){
  if(state!=='in')return;
  var now=performance.now();
  if(pos===0)inT0=now;
  flash=l;clearTimeout(flashT);
  flashT=setTimeout(function(){flash=-1;draw()},130);
  if(seq[pos].lane!==l){
    fail('方位错了 —— 第 '+(pos+1)+' 个应该是 <b>'+(seq[pos].lane+1)+'</b> 号位');return}
  errs.push((now-inT0)-cum[pos]);
  tone(l);pos++;upd();draw();
  if(pos>=seq.length){setTimeout(next,620)}}
function next(){
  maxLen=len;round++;
  if(len>=MAXLEN){finish(true);return}
  len++;setTimeout(play,450)}
function fail(why){
  state='over';bad();
  document.getElementById('msg').innerHTML='<b style="color:#E5484D">'+why+'</b>';
  finish(false)}
function clear(fin){
  var ae=0,bs=0;
  for(var i=0;i<errs.length;i++){ae+=Math.abs(errs[i]);bs+=errs[i]}
  var aerr=errs.length?ae/errs.length:0,bias=errs.length?bs/errs.length:0;
  var ml=maxLen;
  var rk=ml>=8?'SSS+':ml>=7?'SSS':ml>=6?'SS':ml>=5?'S':ml>=4?'A':'B';
  var ach=Math.max(0,Math.min(100,ml/MAXLEN*100-aerr/12));
  var cmt=ml>=7?'短序列的记忆已经很牢了，可以试试边听边记住间隔。':
          ml>=5?'能复述到 '+ml+' 个，长一点就断 —— 试试把序列按「两个一组」切着记。':
          '先别管节奏，把方位顺序记下来就是进步。';
  var head=fin?'<div class="big">'+rk+'　全通</div>':'<div class="big">'+rk+'</div>';
  document.getElementById('msg').innerHTML+=head
    +"完整复述到 <b>"+ml+"</b> 个音　第 <b>"+round+"</b> 轮<br>"
    +"节奏平均误差 <b>"+Math.round(aerr)+"ms</b>　"
    +(errs.length?'（整体'+(bias>0?'偏慢':'偏快')+' '+Math.abs(Math.round(bias))+'ms）':'')+"<br>"
    +"<span style='color:#7f8f96'>"+cmt+"</span>";
  var old=parseFloat(__get('mph_echo_best','0'))||0;
  if(ach>old){__set('mph_echo_best',String(Math.round(ach*100)/100));old=ach}
  document.getElementById('best').textContent=old?Math.round(old)+'%':'—';
  draw();
  __showCode({g:'echo',t:'谱面记忆复述',ach:Math.round(ach*100)/100,rk:rk,
              sc:Math.round(ach*1000),n:ml,rd:round,er:Math.round(aerr)});
}
function finish(fin){state='over';if(raf)cancelAnimationFrame(raf);clear(fin)}
function start(){
  audio();len=START;maxLen=0;round=0;errs=[];seq=[];pos=0;state='idle';
  document.getElementById('codebox').style.display='none';
  document.getElementById('best').textContent=__get('mph_echo_best','')||'—';
  upd();draw();play()}
document.addEventListener('keydown',function(e){
  var k=(e.key||'').toLowerCase(),i=KEYN.map(function(x){return x.toLowerCase()}).indexOf(k);
  if(i>=0){tapLane(i);e.preventDefault()}});
cv.addEventListener('pointerdown',function(e){
  var r=cv.getBoundingClientRect();
  var x=(e.clientX-r.left)*(cv.width/r.width);
  tapLane(Math.max(0,Math.min(3,Math.floor(x/(cv.width/4)))))});
document.getElementById('go').onclick=start;
document.getElementById('reset').onclick=function(){
  state='idle';if(raf)cancelAnimationFrame(raf);len=START;maxLen=0;round=0;errs=[];seq=[];pos=0;
  document.getElementById('msg').innerHTML='先<b>听</b>一遍：四个圆会按节奏亮起来，各自音高不同。<br>'
    +'放完之后轮到你 —— 用 <b>D F J K</b>（或点画面）把<b>方位和节奏</b>原样敲回来。';
  document.getElementById('codebox').style.display='none';upd();draw()};
document.getElementById('best').textContent=__get('mph_echo_best','')||'—';
draw();
</script>
"""
    return _wrap(body.replace("__STORE__", _store("mph_echo_best"))
                     .replace("__CODE__", _CODE_JS),
                 "canvas{background:#080b0f;border:1px solid rgba(255,255,255,.1);"
                 "border-radius:12px;margin:6px auto}")


# ================================================================ 21) 连击生存
def survive_html(height: int = 660) -> str:
    """
    连击生存：NOTE 越来越快、判定窗口越来越窄，漏一个就掉血，血空了结束。
    判的不是准不准，是「在手感被逼到极限时还能撑多久」。
    """
    body = """
<div class="wrap">
  <div class="hud">
    <div>血量<b id="hp">100</b></div>
    <div>连击<b id="cb">0</b></div>
    <div>存活<b id="tm">0.0s</b></div>
    <div>BPM<b id="bp">110</b></div>
    <div>判定窗口<b id="wd">±130ms</b></div>
    <div>最佳<b id="best">—</b></div>
  </div>
  <div class="stage">
    <canvas id="cv" width="400" height="420"></canvas>
    <div class="center" id="jd"></div>
  </div>
  <div class="btns"><button id="go">▶ 开始生存</button>
    <button class="alt" id="reset">↻ 重来</button></div>
  <div class="panel" id="msg">四条轨，键盘 <b>D F J K</b>（也能点画面）。NOTE 会越来越快，判定窗口会越来越窄。<br>
    <b>漏一个掉 20 血</b>，CRITICAL 回 2 血、PERFECT 回 1 血 —— 血空了就结束。</div>
  <div id="codebox" style="display:none"></div>
  <div class="tip">BPM 每 12 个 NOTE 涨 10（110 起步，220 封顶），判定窗口每 10 个 NOTE 收窄 8ms，
    从 ±130ms 一路收到 <b>±40ms</b>。<br>前 20 秒谁都撑得住，真正的分水岭在后面 —— 那时候窗口已经比你的手抖还窄了。</div>
</div>
<script>
__STORE__
__CODE__
var cv=document.getElementById('cv'),ctx=cv.getContext('2d');
var W=cv.width,H=cv.height,JY=H-64,LW=W/4,LEAD=1400;
var LANECOL=['#39C5BB','#F5D442','#E5484D','#A66BFF'];
var ac=null;
var notes=[],t0=0,run=false,raf=null,hp=100,combo=0,mx=0,spawned=0,judged=0,lastT=0,lastLane=-1,dead=false;
function audio(){if(!ac){try{ac=new (window.AudioContext||window.webkitAudioContext)()}catch(e){ac=null}}return ac}
function blip(f,v){var a=audio();if(!a)return;
  var o=a.createOscillator(),g=a.createGain();o.type='square';o.frequency.value=f;
  g.gain.setValueAtTime(0.0001,a.currentTime);g.gain.linearRampToValueAtTime(v,a.currentTime+0.005);
  g.gain.exponentialRampToValueAtTime(0.0001,a.currentTime+0.06);
  o.connect(g);g.connect(a.destination);o.start();o.stop(a.currentTime+0.08)}
function bpmOf(){return Math.min(220,110+Math.floor(spawned/12)*10)}
function winOf(){return Math.max(40,130-Math.floor(judged/10)*8)}
function say(t,c){var el=document.getElementById('jd');el.textContent=t;el.style.color=c;
  el.style.opacity=1;clearTimeout(el._t);el._t=setTimeout(function(){el.style.opacity=0},380)}
function upd(){document.getElementById('hp').textContent=Math.max(0,Math.round(hp));
  document.getElementById('cb').textContent=combo;
  document.getElementById('bp').textContent=bpmOf();
  document.getElementById('wd').textContent='±'+winOf()+'ms'}
function hurt(n){n.jud=true;n.hit=false;judged++;combo=0;hp-=20;blip(140,0.1);
  say('MISS','#E5484D');upd();
  if(hp<=0){hp=0;upd();end()}}
function judge(n,dt){
  var a=Math.abs(dt),w=winOf(),j,c,h;
  if(a<=w*0.4){j='CRITICAL';c='#39C5BB';h=2}
  else if(a<=w*0.75){j='PERFECT';c='#7ee0d6';h=1}
  else {j='GREAT';c='#F5D442';h=0}
  n.jud=true;n.hit=true;judged++;combo++;if(combo>mx)mx=combo;
  hp=Math.min(100,hp+h);blip(660+combo%5*40,0.1);
  say(j,c);upd()}
function press(lane){
  if(!run)return;
  var now=performance.now()-t0,best_n=null,bd=1e9;
  for(var i=0;i<notes.length;i++){var n=notes[i];
    if(n.jud||n.lane!==lane)continue;var d=Math.abs(n.t-now);
    if(d<bd){bd=d;best_n=n}}
  if(best_n&&bd<=winOf())judge(best_n,best_n.t-now)}
function spawn(){
  var now=performance.now()-t0;
  while(lastT<now+LEAD){
    lastT+=60000/bpmOf();
    var lane=Math.floor(Math.random()*4);
    if(lane===lastLane&&Math.random()<0.6)lane=(lane+1+Math.floor(Math.random()*3))%4;
    lastLane=lane;
    notes.push({t:lastT,lane:lane,jud:false,hit:false});spawned++}}
function draw(){
  ctx.clearRect(0,0,W,H);
  var now=run?performance.now()-t0:0;
  for(var l=0;l<4;l++){ctx.fillStyle='rgba(255,255,255,.03)';ctx.fillRect(l*LW,0,LW-2,H)}
  ctx.fillStyle='#39C5BB';ctx.fillRect(0,JY,W,3);
  ctx.fillStyle='rgba(255,255,255,.12)';
  for(var l2=0;l2<4;l2++)ctx.fillRect(l2*LW+8,JY-34,LW-18,30);
  ctx.font='12px sans-serif';ctx.fillStyle='rgba(255,255,255,.35)';
  var ks=['D','F','J','K'];
  for(var l3=0;l3<4;l3++)ctx.fillText(ks[l3],l3*LW+LW/2-4,JY-14);
  var hpw=(W-24)*Math.max(0,hp)/100;
  ctx.fillStyle='rgba(255,255,255,.08)';ctx.fillRect(12,10,W-24,7);
  ctx.fillStyle=hp>50?'#39C5BB':hp>25?'#F5D442':'#E5484D';ctx.fillRect(12,10,hpw,7);
  if(!run)return;
  for(var i=0;i<notes.length;i++){
    var n=notes[i],y=JY-((n.t-now)/LEAD)*(JY+40);
    if(y<-40||y>H+40)continue;
    if(n.jud&&n.hit)continue;
    ctx.fillStyle=LANECOL[n.lane];
    ctx.beginPath();ctx.arc(n.lane*LW+LW/2,y,15,0,7);ctx.fill();
    ctx.strokeStyle='rgba(255,255,255,.5)';ctx.lineWidth=2;ctx.stroke()}
}
function loop(){
  draw();
  if(!run)return;
  var now=performance.now()-t0;
  spawn();
  for(var i=0;i<notes.length;i++){
    var n=notes[i];
    if(!n.jud&&now-n.t>winOf()){hurt(n);if(!run)return}}
  document.getElementById('tm').textContent=(now/1000).toFixed(1)+'s';
  raf=requestAnimationFrame(loop)}
function end(){
  run=false;dead=true;
  var t=(performance.now()-t0)/1000;
  var rk=t>=90?'SSS+':t>=70?'SSS':t>=50?'SS':t>=35?'S':t>=20?'A':'B';
  var ach=Math.min(100,(t/90)*80+(Math.min(mx,80)/80)*20);
  var cmt=t>=70?'这个耐力和集中度，长曲后半段基本不会崩。':
          t>=40?'能撑到窗口收窄的阶段，再练就是「快但稳」那一档了。':
          '前半段就掉了，先放慢把手感固定住 —— 别急着追 NOTE。';
  document.getElementById('msg').innerHTML="<div class='big'>"+rk+"</div>"
    +"存活 <b>"+t.toFixed(1)+"s</b>　最高连击 <b>"+mx+"</b>　打了 <b>"+judged+"</b> 个 NOTE<br>"
    +"结束时 BPM <b>"+bpmOf()+"</b>　窗口 <b>±"+winOf()+"ms</b><br>"
    +"<span style='color:#7f8f96'>"+cmt+"</span>";
  var old=parseFloat(__get('mph_survive_best','0'))||0;
  if(ach>old){__set('mph_survive_best',String(Math.round(ach*100)/100));old=ach}
  document.getElementById('best').textContent=old?Math.round(old)+'%':'—';
  __showCode({g:'survive',t:'连击生存',ach:Math.round(ach*100)/100,rk:rk,
              sc:Math.round(ach*1000),n:judged,ms:Math.round(t*1000),mc:mx});
}
function start(){
  audio();var a=audio();
  if(!a){document.getElementById('msg').textContent='这个浏览器不支持 Web Audio，换 Chrome/Edge 试试。';return}
  if(a.state==='suspended'&&a.resume)a.resume();
  notes=[];t0=performance.now();run=true;dead=false;
  hp=100;combo=0;mx=0;spawned=0;judged=0;lastT=700;lastLane=-1;
  document.getElementById('msg').innerHTML='撑住 —— 漏一个掉 20 血。';
  document.getElementById('codebox').style.display='none';
  document.getElementById('best').textContent=__get('mph_survive_best','')||'—';
  upd();loop()}
document.addEventListener('keydown',function(e){
  var k=(e.key||'').toLowerCase(),i=['d','f','j','k'].indexOf(k);
  if(i>=0){press(i);e.preventDefault()}});
cv.addEventListener('pointerdown',function(e){
  var r=cv.getBoundingClientRect();
  var x=(e.clientX-r.left)*(W/r.width);
  press(Math.max(0,Math.min(3,Math.floor(x/LW))))});
document.getElementById('go').onclick=start;
document.getElementById('reset').onclick=function(){
  run=false;dead=false;notes=[];hp=100;combo=0;mx=0;spawned=0;judged=0;
  document.getElementById('msg').innerHTML='四条轨，键盘 <b>D F J K</b>（也能点画面）。'
    +'NOTE 会越来越快，判定窗口会越来越窄。<br><b>漏一个掉 20 血</b>，CRITICAL 回 2 血、PERFECT 回 1 血。';
  document.getElementById('tm').textContent='0.0s';
  document.getElementById('codebox').style.display='none';upd();draw()};
document.getElementById('best').textContent=__get('mph_survive_best','')||'—';
draw();
</script>
"""
    return _wrap(body.replace("__STORE__", _store("mph_survive_best"))
                     .replace("__CODE__", _CODE_JS),
                 "canvas{background:#080b0f;border:1px solid rgba(255,255,255,.1);"
                 "border-radius:12px;margin:6px auto}.center{font-size:20px}")
