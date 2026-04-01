"""
reports/dashboard_builder.py
Builds static HTML dashboard pages for GitHub Pages.
Called from main.py step 28b — after build_intraday_report() completes.
NEVER raises — all failures logged and skipped safely.
"""

import html
import json
import os
from datetime import datetime

import pytz

from utils.logger import get_logger

log = get_logger('dashboard_builder')

DOCS_DIR = 'docs'
DATA_DIR = os.path.join(DOCS_DIR, 'assets', 'data')

_FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link href="https://fonts.googleapis.com/css2?family=Orbitron'
    ':wght@400;600;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet">'
)
_CHARTJS = '<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js" defer></script>'
_EM = '\u2014'  # em dash — safe to use inside f-string expressions


# ── Safe helpers ────────────────────────────────────────────────────────────

def _esc(val) -> str:
    """Escape a data-derived string for HTML insertion. Returns '—' for None/empty."""
    if not val:
        return '\u2014'
    return html.escape(str(val))


def _safe_json(data) -> str:
    """Serialize data for <script type="application/json"> blocks (Pattern A)."""
    return (
        json.dumps(data)
        .replace('</script>', '<\\/script>')
        .replace('\u2028', '\\u2028')
        .replace('\u2029', '\\u2029')
    )


def _safe_js_json(data) -> str:
    """Serialize data for inline JS variable assignment (Pattern B)."""
    return json.dumps(data, ensure_ascii=True).replace('</script>', '<\\/script>')


# ── Numeric formatters ──────────────────────────────────────────────────────

def _fmt_pct(val) -> str:
    if not isinstance(val, (int, float)):
        return '\u2014'
    arrow = '\u25b2' if val > 0 else '\u25bc' if val < 0 else '\u2014'
    return f'{arrow}{abs(val):.1f}%'


def _fmt_score(val, decimals=1) -> str:
    if not isinstance(val, (int, float)):
        return '\u2014'
    return f'{val:.{decimals}f}'


def _fmt_price(val) -> str:
    if not isinstance(val, (int, float)):
        return '\u2014'
    return f'${val:,.2f}'


def _fmt_index_val(val) -> str:
    if not isinstance(val, (int, float)):
        return '\u2014'
    return f'{val:,.0f}'


def _calc_return_from_history(data: list, trading_days: int) -> str:
    if not data or len(data) <= trading_days:
        return '\u2014'
    try:
        start = data[-trading_days - 1]
        end   = data[-1]
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            return '\u2014'
        if start == 0:
            return '\u2014'
        pct   = ((end - start) / start) * 100
        arrow = '\u25b2' if pct > 0 else '\u25bc' if pct < 0 else '\u2014'
        return f'{arrow}{abs(pct):.1f}%'
    except Exception:
        return '\u2014'


def _sanitize_price_history(raw: list) -> list:
    """
    Remove any non-numeric or NaN values from a price history list before storage.

    SYSTEM CONTRACT: rank.json MUST NEVER contain unsanitized price_history.
    All writes to price_history in rank.json must pass through _update_rank_board(),
    which calls this function. Never bypass _update_rank_board() to write price_history
    directly to rank.json — doing so breaks the Chart.js render pipeline.
    """
    import math
    if not raw or not isinstance(raw, list):
        return []
    return [p for p in raw if isinstance(p, (int, float)) and not math.isnan(p)]


def _build_idx_data(index_history: dict, indices: dict) -> dict:
    """Build IDX_DATA dict for index page Chart.js injection (Pattern B)."""
    def _dir_color(chg):
        if isinstance(chg, (int, float)) and chg > 0:
            return '#39e8a0', 'rgba(57,232,160,0.12)'
        if isinstance(chg, (int, float)) and chg < 0:
            return '#ff4d6d', 'rgba(255,77,109,0.12)'
        return '#ff9a3c', 'rgba(255,154,60,0.12)'

    idx_map = {
        'dow': ('Dow Jones', 'dow',    'dow'),
        'sp':  ('S&P 500',   'sp500',  'sp500'),
        'nq':  ('Nasdaq',    'nasdaq', 'nasdaq'),
    }
    result = {}
    for key, (name, idx_key, hist_key) in idx_map.items():
        chg     = (indices.get(idx_key) or {}).get('change_pct')
        col, bg = _dir_color(chg)
        data    = _sanitize_price_history(
            index_history.get(hist_key) or []
        )
        result[key] = {
            'name':     name,
            'color':    col,
            'bg_color': bg,
            'data':     data,
            'stat1m':   _calc_return_from_history(data, 21),
            'stat3m':   _EM,
            'stat6m':   _EM,
        }
    return result


# ── CSS-class helpers ────────────────────────────────────────────────────────

def _conf_cls(score) -> str:
    if not isinstance(score, (int, float)):
        return 'nt'
    if score >= 75: return 'up'
    if score >= 50: return 'nt'
    return 'dn'


def _breadth_cls(label: str) -> str:
    l = (label or '').lower()
    if 'strong' in l: return 'up'
    if 'weak'   in l: return 'dn'
    return 'nt'


def _eq_cls(verdict: str) -> str:
    s = (verdict or '').upper()
    if 'SUPPORT' in s: return 'up'
    if 'WEAK' in s or 'RISK' in s: return 'dn'
    if 'NEUTRAL' in s: return 'nt'
    return 'pu'


def _rot_cls(signal: str) -> str:
    s = (signal or '').upper()
    if s == 'SUPPORT': return 'up'
    if s == 'WEAKEN':  return 'dn'
    if s == 'WAIT':    return 'nt'
    return 'pu'


def _align_cls(val: str) -> str:
    v = (val or '').strip().upper()
    if v == 'ALIGNED':  return 'sig-up'
    if v == 'CONFLICT': return 'sig-dn'
    return 'sig-nt'


# ── Module-level JS string constants ────────────────────────────────────────
# These are NOT f-strings — { } have their literal meaning inside them.

_DAYS_JS = """
const DAYS = Array.from({length:30},(_,i)=>{
  const d=new Date(); d.setDate(d.getDate()-(29-i));
  return d.toLocaleDateString('en-US',{month:'short',day:'numeric'});
});
"""

_EASING_JS = """
function easeOutExpo(t)  { return t===1?1:1-Math.pow(2,-10*t); }
function easeOutCubic(t) { return 1-Math.pow(1-t,3); }
"""

_GENIE_JS = """
function genieClipOpen(t){
  const e=easeOutExpo(t),x1=46*(1-e),x2=54+46*e,tx1=3*(1-e),tx2=97+3*e;
  return `polygon(${tx1.toFixed(1)}% 0%, ${tx2.toFixed(1)}% 0%, ${x2.toFixed(1)}% 100%, ${x1.toFixed(1)}% 100%)`;
}
function genieClipClose(t){
  const tB=Math.min(t*1.6,1),tT=Math.max((t-0.4)/0.6,0);
  const bx1=easeOutCubic(tB)*46,bx2=100-easeOutCubic(tB)*46;
  const tx1=easeOutCubic(tT)*46,tx2=100-easeOutCubic(tT)*46;
  return `polygon(${tx1.toFixed(1)}% 0%, ${tx2.toFixed(1)}% 0%, ${bx2.toFixed(1)}% 100%, ${bx1.toFixed(1)}% 100%)`;
}
let expandRAF=null, expandHeight=0;
function getFullHeight(){
  const ex=document.getElementById('idx-expand'),pan=document.getElementById('idx-panel-active');
  if(!pan) return 200;
  const pH=ex.style.height,pC=ex.style.clipPath;
  ex.style.height='auto'; ex.style.clipPath='';
  const h=pan.offsetHeight+8;
  ex.style.height=pH; ex.style.clipPath=pC;
  return h;
}
function animateGenie(fromH,toH,dur,onDone){
  if(expandRAF){cancelAnimationFrame(expandRAF);expandRAF=null;}
  const ex=document.getElementById('idx-expand'),start=performance.now(),opening=toH>fromH;
  function frame(now){
    const raw=Math.min((now-start)/dur,1);
    const tH=opening?easeOutExpo(raw):easeOutCubic(raw);
    const h=fromH+(toH-fromH)*tH; expandHeight=h;
    const clip=opening?genieClipOpen(raw):genieClipClose(raw);
    const sc=opening?0.93+0.07*easeOutExpo(raw):1.0-0.07*easeOutCubic(raw);
    const mt=h>0?8*Math.min(raw*4,1):0;
    ex.style.height=h+'px'; ex.style.marginTop=mt+'px';
    ex.style.opacity=opening?Math.min(raw*3,1):Math.max(1-raw,0);
    ex.style.clipPath=clip; ex.style.transform=`scaleX(${sc.toFixed(4)})`;
    if(raw<1){expandRAF=requestAnimationFrame(frame);}
    else{
      expandRAF=null;
      if(toH>0){ex.style.height=toH+'px';ex.style.marginTop='8px';ex.style.opacity='1';
        ex.style.clipPath='polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)';ex.style.transform='scaleX(1)';}
      else{ex.style.height='0';ex.style.marginTop='0';ex.style.opacity='0';
        ex.style.clipPath='polygon(46% 0%, 54% 0%, 54% 0%, 46% 0%)';ex.style.transform='scaleX(0.93)';}
      isAnimating=false; if(onDone)onDone();
    }
  }
  expandRAF=requestAnimationFrame(frame);
}
"""

_SLIDE_JS = """
function animateSlide(prevKey,nextKey,onDone){
  const fromO=IDX_ORDER.indexOf(prevKey),toO=IDX_ORDER.indexOf(nextKey);
  const dir=toO>fromO?'left':'right';
  const ex=document.getElementById('idx-expand'),vp=document.getElementById('idx-slide-viewport');
  const tr=document.getElementById('idx-slide-track'),ac=document.getElementById('idx-panel-active');
  if(window._mreCharts&&window._mreCharts['idx-chart']){window._mreCharts['idx-chart'].destroy();delete window._mreCharts['idx-chart'];}
  ex.classList.add('sliding');
  const pW=ac.offsetWidth,pH=ac.offsetHeight;
  vp.style.height=pH+'px'; vp.style.overflow='hidden';
  const cl=ac.cloneNode(true); cl.removeAttribute('id');
  cl.style.cssText=`position:absolute;top:0;left:0;width:${pW}px;z-index:1;transform:translateX(0);opacity:1;pointer-events:none;`;
  tr.appendChild(cl);
  const d=IDX_DATA[nextKey];
  ac.querySelector('.idx-expand-name').textContent=d.name;
  ac.querySelector('#idx-stat-1m').textContent=d.stat1m;
  ac.querySelector('#idx-stat-3m').textContent=d.stat3m;
  ac.querySelector('#idx-stat-6m').textContent=d.stat6m;
  const eX=dir==='left'?pW:-pW;
  ac.style.cssText=`position:absolute;top:0;left:0;width:${pW}px;z-index:2;transform:translateX(${eX}px);opacity:0.7;`;
  tr.style.position='relative'; tr.style.height=pH+'px';
  const DUR=520,start=performance.now(),exitX=dir==='left'?-pW:pW;
  let slideRAF=null;
  function frame(now){
    const raw=Math.min((now-start)/DUR,1),ease=easeOutCubic(raw);
    const fo=Math.max(1-raw/0.6,0),fi=raw<0.3?0:easeOutCubic((raw-0.3)/0.7);
    cl.style.transform=`translateX(${exitX*ease}px)`; cl.style.opacity=fo.toFixed(3);
    ac.style.transform=`translateX(${eX*(1-ease)}px)`; ac.style.opacity=fi.toFixed(3);
    if(raw<1){slideRAF=requestAnimationFrame(frame);}
    else{
      cl.remove(); ac.style.cssText='';
      tr.style.height=''; tr.style.position='';
      vp.style.height=''; vp.style.overflow='';
      ex.classList.remove('sliding');
      ac.querySelector('.idx-panel-header').style.opacity='0';
      ac.querySelector('.idx-panel-header').style.transform='translateY(-6px)';
      ac.querySelector('.idx-chart-wrap').style.opacity='0';
      ac.querySelector('.idx-chart-wrap').style.transform='translateY(-6px)';
      requestAnimationFrame(()=>{
        ac.querySelector('.idx-panel-header').style.opacity='';
        ac.querySelector('.idx-panel-header').style.transform='';
        ac.querySelector('.idx-chart-wrap').style.opacity='';
        ac.querySelector('.idx-chart-wrap').style.transform='';
        ex.classList.add('slide-reveal');
      });
      isAnimating=false;
      if(onDone) pendingChartTimer=setTimeout(()=>{pendingChartTimer=null;onDone();},320);
    }
  }
  slideRAF=requestAnimationFrame(frame);
}
"""

_TOGGLE_IDX_JS = """
let currentIdx=null, isAnimating=false, pendingChartTimer=null;
const IDX_ORDER=['dow','sp','nq'];
function toggleIdx(key){
  if(isAnimating)return;
  if(pendingChartTimer){clearTimeout(pendingChartTimer);pendingChartTimer=null;}
  if(window._mreCharts&&window._mreCharts['idx-chart']){
    window._mreCharts['idx-chart'].destroy();delete window._mreCharts['idx-chart'];
  }
  const ex=document.getElementById('idx-expand'),pill=document.getElementById('pill-'+key);
  if(currentIdx===key){
    pill.classList.remove('active');
    ex.classList.remove('content-visible','slide-reveal');
    currentIdx=null; isAnimating=true;
    animateGenie(expandHeight,0,340,null); return;
  }
  const prevIdx=currentIdx,panelOpen=expandHeight>20;
  document.querySelectorAll('.idx-pill').forEach(p=>p.classList.remove('active'));
  pill.classList.add('active'); currentIdx=key; isAnimating=true;
  if(panelOpen){
    animateSlide(prevIdx,key,()=>buildIdxChart(IDX_DATA[key]));
  } else {
    const d=IDX_DATA[key];
    document.getElementById('idx-expand-name').textContent=d.name;
    document.getElementById('idx-stat-1m').textContent=d.stat1m;
    document.getElementById('idx-stat-3m').textContent=d.stat3m;
    document.getElementById('idx-stat-6m').textContent=d.stat6m;
    const full=getFullHeight();
    animateGenie(0,full,580,()=>{ex.classList.add('content-visible');buildIdxChart(d);});
  }
}
"""

_BUILD_IDX_CHART_JS = """
function buildIdxChart(d){
  if(typeof Chart==='undefined')return;
  window._mreCharts=window._mreCharts||{};
  const cid='idx-chart',cv=document.getElementById(cid);
  if(!cv)return;
  if(window._mreCharts[cid]){window._mreCharts[cid].destroy();delete window._mreCharts[cid];}
  const col=d.color;
  window._mreCharts[cid]=new Chart(cv.getContext('2d'),{
    type:'line',
    data:{labels:DAYS,datasets:[{data:d.data,borderColor:col,borderWidth:1.8,fill:true,tension:0.38,
      backgroundColor:ctx=>{const{ctx:c,chartArea:a}=ctx.chart;if(!a)return 'transparent';
        const g=c.createLinearGradient(0,a.top,0,a.bottom);g.addColorStop(0,col+'30');g.addColorStop(1,'transparent');return g;},
      pointRadius:0,pointHoverRadius:3,pointHoverBackgroundColor:col,
      pointHoverBorderColor:'#0a0610',pointHoverBorderWidth:2,hitRadius:20}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:{mode:'index',intersect:false,
        backgroundColor:d.bg_color,borderColor:'rgba(155,89,255,0.25)',borderWidth:1,
        titleColor:'#4a3d72',bodyColor:'#f0eaff',
        titleFont:{family:'Share Tech Mono',size:10},bodyFont:{family:'Share Tech Mono',size:11},
        callbacks:{title:i=>DAYS[i[0].dataIndex],label:i=>' $'+i.raw.toFixed(2)}}},
      scales:{x:{display:false},y:{display:false}},
      interaction:{mode:'index',intersect:false},animation:{duration:600,easing:'easeInOutCubic'}}
  });
}
"""

_RAF_COLLAPSE_JS = """
function rafCollapseRow(el,innerSel,duration,onDone){
  const fromH=el.offsetHeight;
  if(fromH===0){el.style.display='none';if(onDone)onDone();return;}
  const inner=el.querySelector(innerSel);
  el.style.height=fromH+'px'; el.style.overflow='hidden';
  const start=performance.now();
  function frame(now){
    const raw=Math.min((now-start)/duration,1),ease=1-Math.pow(1-raw,3);
    el.style.height=(fromH*(1-ease)).toFixed(1)+'px';
    if(inner){
      inner.style.opacity=(1-Math.min(raw*1.8,1)).toFixed(3);
      inner.style.transform=`scaleY(${(1-ease*0.28).toFixed(4)}) translateY(${(-5*ease).toFixed(2)}px)`;
      inner.style.transformOrigin='top';
    }
    if(raw<1){requestAnimationFrame(frame);}
    else{
      el.classList.remove('open'); el.style.display='none';
      el.style.height=''; el.style.overflow='';
      if(inner){inner.style.opacity='';inner.style.transform='';inner.style.transformOrigin='';}
      if(onDone)onDone();
    }
  }
  requestAnimationFrame(frame);
}
function closeRpExp(el){if(!el.classList.contains('open'))return;rafCollapseRow(el,'.rp-exp-inner',260,null);}
function closeRpExpInstant(el){
  if(!el.classList.contains('open'))return;
  el.classList.remove('open'); el.style.display='none'; el.style.height='';
  const inner=el.querySelector('.rp-exp-inner');
  if(inner){inner.style.opacity='';inner.style.transform='';inner.style.transformOrigin='';}
}
function rpT(id){
  const el=document.getElementById(id),was=el.classList.contains('open');
  document.querySelectorAll('.rp-exp').forEach(e=>{if(e!==el)closeRpExpInstant(e);});
  if(!was){
    el.style.display=''; el.style.height='';
    const inner=el.querySelector('.rp-exp-inner');
    if(inner){inner.style.opacity='';inner.style.transform='';}
    el.classList.add('open');
    el.querySelectorAll('.pex-item').forEach((item,i)=>{
      item.style.animation='none'; item.offsetHeight;
      item.style.animation=`pex-spark 0.22s ease both ${0.04+i*0.06}s`;
    });
  } else { closeRpExp(el); }
}
function closeExpRow(row){if(!row.classList.contains('open'))return;rafCollapseRow(row,'.exp-inner',300,null);}
function closeExpRowInstant(row){
  if(!row.classList.contains('open'))return;
  row.classList.remove('open'); row.style.display='none'; row.style.height='';
  const inner=row.querySelector('.exp-inner');
  if(inner){inner.style.opacity='';inner.style.transform='';inner.style.transformOrigin='';}
}
"""

_EXP_T_JS = r"""
window._mreCharts=window._mreCharts||{};
function mkC(cid,data){
  if(typeof Chart==='undefined')return;
  const cv=document.getElementById(cid);if(!cv)return;
  if(window._mreCharts[cid]){window._mreCharts[cid].destroy();delete window._mreCharts[cid];}
  const up=data[data.length-1]>=data[0],col=up?'#39e8a0':'#ff4d6d';
  window._mreCharts[cid]=new Chart(cv.getContext('2d'),{
    type:'line',
    data:{labels:DAYS,datasets:[{data,borderColor:col,borderWidth:1.8,fill:true,tension:0.38,
      backgroundColor:ctx=>{const{ctx:c,chartArea:a}=ctx.chart;if(!a)return 'transparent';
        const g=c.createLinearGradient(0,a.top,0,a.bottom);
        g.addColorStop(0,up?'rgba(57,232,160,.18)':'rgba(255,77,109,.18)');
        g.addColorStop(1,'transparent');return g;},
      pointRadius:0,pointHoverRadius:3,pointHoverBackgroundColor:col,
      pointHoverBorderColor:'#0a0610',pointHoverBorderWidth:2,hitRadius:20}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:{mode:'index',intersect:false,
        backgroundColor:'#1a1430',borderColor:'rgba(155,89,255,0.25)',borderWidth:1,
        titleColor:'#4a3d72',bodyColor:'#f0eaff',
        titleFont:{family:'Share Tech Mono',size:10},bodyFont:{family:'Share Tech Mono',size:11},
        callbacks:{title:i=>DAYS[i[0].dataIndex],label:i=>' $'+i.raw.toFixed(2)}}},
      scales:{x:{display:false},y:{display:false}},
      interaction:{mode:'index',intersect:false},animation:{duration:800,easing:'easeInOutCubic'}}
  });
}
function countUp(el,target,prefix,suffix,duration){
  const start=performance.now();
  function step(now){
    const p=Math.min((now-start)/duration,1),ease=1-Math.pow(1-p,3);
    el.textContent=prefix+(target*ease).toFixed(target%1===0?0:1)+suffix;
    if(p<1)requestAnimationFrame(step);
    else el.textContent=prefix+(Number.isInteger(target)?target:target.toFixed(1))+suffix;
  }
  requestAnimationFrame(step);
}
function expT(btn){
  var el=document.getElementById(btn.dataset.ref);
  if(!el)return;
  var data;
  try{data=JSON.parse(el.textContent);}catch(e){data=[];}
  var cid=btn.dataset.cid,eid=btn.dataset.eid;
  var row=document.getElementById(eid);if(!row)return;
  var was=row.classList.contains('open');
  document.querySelectorAll('.exp-row').forEach(r=>{if(r!==row)closeExpRowInstant(r);});
  if(!was){
    row.style.display=''; row.style.height='';
    var inner=row.querySelector('.exp-inner');
    if(inner){inner.style.opacity='';inner.style.transform='';}
    row.classList.add('open');
    setTimeout(function(){
      row.querySelectorAll('.est-v').forEach(function(ev,i){
        var raw=ev.textContent.trim(),num=parseFloat(raw.replace(/[^0-9.]/g,''));
        if(!isNaN(num)&&num>0&&raw.length<12){
          var prefix=raw.match(/^[▲▼]/)?.[0]||'',suffix=raw.replace(/^[▲▼]?[\d.]+/,'');
          setTimeout(function(){countUp(ev,num,prefix,suffix,420);},i*50);
        }
      });
    },80);
    if(data&&data.length>=2){mkC(cid,data);}
  } else { closeExpRow(row); }
}
"""

_RCT_JS = "function rcT(el){el.classList.toggle('open');}"

_COPY_PROMPT_JS = """
document.addEventListener('DOMContentLoaded',function(){
  document.querySelectorAll('.copy-prompt-btn').forEach(function(btn){
    btn.addEventListener('click',function(e){
      e.stopPropagation();
      var el=document.getElementById(this.dataset.ref);if(!el)return;
      var text;
      try{text=JSON.parse(el.textContent);}catch(e){
        var s2=this;s2.textContent='Error';s2.style.color='var(--dn)';
        setTimeout(function(){s2.textContent='\u2389 AI Prompt';s2.style.color='';},1800);return;
      }
      var self=this;
      function onCopied(){
        var orig=self.textContent;self.textContent='Copied \u2713';
        self.style.color='var(--up)';self.style.borderColor='rgba(57,232,160,.5)';
        setTimeout(function(){self.textContent=orig;self.style.color='';self.style.borderColor='';},1800);
      }
      if(navigator.clipboard){
        navigator.clipboard.writeText(text).then(onCopied).catch(function(){
          var ta=document.createElement('textarea');ta.value=text;
          document.body.appendChild(ta);ta.select();document.execCommand('copy');
          document.body.removeChild(ta);onCopied();
        });
      } else {
        var ta=document.createElement('textarea');ta.value=text;
        document.body.appendChild(ta);ta.select();document.execCommand('copy');
        document.body.removeChild(ta);onCopied();
      }
    });
  });
});
"""


# ── Nav ──────────────────────────────────────────────────────────────────────

def _nav_html(active: str) -> str:
    """Returns sticky nav HTML. active: 'home' | 'rank' | 'news' | 'archive' | 'guide'"""
    pages = [
        ('index.html',   'home',    'Home'),
        ('rank.html',    'rank',    'Rank'),
        ('news.html',    'news',    'News'),
        ('archive.html', 'archive', 'Archive'),
        ('guide.html',   'guide',   'Guide'),
    ]
    tabs = ''
    for href, key, label in pages:
        on = ' on' if key == active.lower() else ''
        tabs += f'<a href="{href}" class="tab{on}">{label}</a>'
    return (
        '<nav>'
        '<div class="brand">'
        '<div class="brand-pulse"></div>'
        '<span>MRE // System</span>'
        '</div>'
        f'<div class="nav-tabs">{tabs}</div>'
        '</nav>'
    )


# ── Error fallback page ──────────────────────────────────────────────────────

def _err_page(nav_key: str, msg: str) -> str:
    return (
        '<!DOCTYPE html><html lang="en"><head>'
        '<meta charset="UTF-8">'
        f'{_FONTS_LINK}'
        '<link rel="stylesheet" href="assets/style.css">'
        '</head><body>'
        '<div class="scanlines"></div>'
        f'{_nav_html(nav_key)}'
        '<div class="pages"><div class="page on">'
        f'<div style="color:var(--dn);font-family:var(--ff-mono);padding:44px 28px;">{msg}</div>'
        '</div></div>'
        '<footer><span>MRE</span> &middot; Not investment advice</footer>'
        '</body></html>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# DATA WRITERS
def _write_news_json(confirmed_sectors: dict) -> None:
    """
    Writes docs/assets/data/news.json from confirmed sector articles.

    Preserve-on-empty: if confirmed_sectors is empty this run, the file is left
    unchanged so the index page npc widget retains last-run headlines.
    Intentional divergence from _write_news_page() which always reflects current
    run state. This may cause index and news page to temporarily display different
    data states after empty runs. This is by design.
    """
    if not isinstance(confirmed_sectors, dict):
        return
    if not confirmed_sectors:
        return
    news_path = os.path.join(DATA_DIR, 'news.json')
    now_et    = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
    payload   = {'generated': now_et.strftime('%Y-%m-%d %H:%M ET'), 'sectors': []}
    sectors_sorted = sorted(
        [(s, d) for s, d in confirmed_sectors.items() if d.get('articles')],
        key=lambda x: x[1].get('score', 0) if isinstance(x[1].get('score'), (int, float)) else 0,
        reverse=True,
    )
    for sector, data in sectors_sorted:
        payload['sectors'].append({
            'sector':   sector,
            'score':    data.get('score', 0),
            'articles': data.get('articles', []),
        })
    try:
        tmp = news_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, news_path)
        log.info(f'News JSON written: {len(payload["sectors"])} sectors')
    except Exception as e:
        log.error(f'News JSON write failed: {e}')


def _update_reports_index(companies, slot, indices, breadth, regime, full_url='', prompt_text=''):
    index_path = os.path.join(DATA_DIR, 'reports.json')
    try:
        with open(index_path, encoding='utf-8') as f:
            index = json.load(f)
    except Exception:
        index = {'reports': []}

    now_et = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
    vc = {
        'RESEARCH NOW': sum(1 for c in companies if c.get('market_verdict_display', c.get('summary_verdict', '')) == 'RESEARCH NOW'),
        'WATCH':        sum(1 for c in companies if c.get('market_verdict_display', c.get('summary_verdict', '')) == 'WATCH'),
        'SKIP':         sum(1 for c in companies if c.get('market_verdict_display', c.get('summary_verdict', '')) == 'SKIP'),
    }
    entry = {
        'date':       now_et.strftime('%Y-%m-%d'),
        'time':       now_et.strftime('%H:%M'),
        'slot':       slot,
        'breadth':    breadth.get('label', 'unknown') if breadth else 'unknown',
        'regime':     regime.get('label', 'unknown')  if regime  else 'unknown',
        'count':      len(companies),
        'tickers':    [c.get('ticker', '') for c in companies[:5]],
        'top_score':  max((c.get('composite_confidence', 0) for c in companies), default=0),
        'verdicts':   vc,
        'report_url': full_url,
        'prompt':     prompt_text[:12000] if prompt_text else '',
    }
    if not isinstance(index.get('reports'), list):
        index['reports'] = []
    index['reports'].insert(0, entry)
    index['reports'] = index['reports'][:50]
    try:
        tmp = index_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2)
        os.replace(tmp, index_path)
    except Exception as e:
        log.error(f'reports.json write failed: {e}')


def _update_rank_board(companies):
    rank_path = os.path.join(DATA_DIR, 'rank.json')
    now_et    = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
    week_key  = now_et.strftime('%Y-W%W')
    try:
        with open(rank_path, encoding='utf-8') as f:
            rank_data = json.load(f)
    except Exception:
        rank_data = {}
    if rank_data.get('week') != week_key:
        rank_data = {'week': week_key, 'stocks': {}}
    for c in companies:
        ticker = c.get('ticker', '')
        if not ticker:
            continue
        existing = rank_data['stocks'].get(ticker, {})
        new_conf  = c.get('composite_confidence', 0)
        if new_conf > existing.get('confidence', 0):
            raw_ph = c.get('price_history') or existing.get('price_history', [])
            rank_data['stocks'][ticker] = {
                'ticker':                  ticker,
                'name':                    c.get('company_name', ticker),
                'sector':                  c.get('sector', ''),
                'price':                   (c.get('current_price') or c.get('financials', {}).get('current_price')),
                'confidence':              round(new_conf, 1),
                'risk_score':              round(c.get('risk_score', 50), 1),
                'opportunity_score':       c.get('opportunity_score'),
                'signal_agreement':        c.get('agreement_score'),
                'return_1m':               c.get('return_1m'),
                'return_3m':               c.get('return_3m'),
                'return_6m':               c.get('return_6m'),
                'eq_verdict_display':      c.get('eq_verdict_display', ''),
                'rotation_signal_display': c.get('rotation_signal_display', ''),
                'market_verdict_display':  c.get('market_verdict_display', c.get('summary_verdict', '')),
                'market_verdict':          c.get('summary_verdict', ''),
                'price_history':           _sanitize_price_history(raw_ph),
                'alignment':               c.get('alignment', 'PARTIAL'),
            }
    try:
        tmp = rank_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(rank_data, f, indent=2)
        os.replace(tmp, rank_path)
    except Exception as e:
        log.error(f'rank.json write failed: {e}')


def _update_weekly_archive(companies, slot, breadth, regime, prompt_text='', is_debug=False, full_url=''):
    archive_path = os.path.join(DATA_DIR, 'weekly_archive.json')
    try:
        with open(archive_path, encoding='utf-8') as f:
            archive = json.load(f)
    except Exception:
        archive = {'weeks': {}}
    now_et   = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
    week_key = now_et.strftime('%Y-W%W')
    run_id   = f"{slot}_{now_et.strftime('%Y-%m-%dT%H:%M')}"
    run_entry = {
        'id':        run_id,
        'run_type':  'MANUAL' if is_debug else 'SCHEDULED',
        'timestamp': now_et.strftime('%Y-%m-%dT%H:%M'),
        'slot':      slot,
        'breadth':   breadth.get('label', '') if breadth else '',
        'regime':    regime.get('label', '')  if regime  else '',
        'count':     len(companies),
        'verdict_counts': {
            'RESEARCH NOW': sum(1 for c in companies if c.get('market_verdict_display', c.get('summary_verdict', '')) == 'RESEARCH NOW'),
            'WATCH':        sum(1 for c in companies if c.get('market_verdict_display', c.get('summary_verdict', '')) == 'WATCH'),
            'SKIP':         sum(1 for c in companies if c.get('market_verdict_display', c.get('summary_verdict', '')) == 'SKIP'),
        },
        'candidates': [
            {
                'ticker':          c.get('ticker', ''),
                'confidence':      round(c.get('composite_confidence', 0), 1),
                'eq_verdict':      c.get('eq_verdict_display', ''),
                'rotation_signal': c.get('rotation_signal_display', ''),
                'conclusion':      (c.get('eq_combined_reading', {}).get('conclusion', '') if c.get('eq_combined_reading') else '')[:200],
            }
            for c in companies
        ],
        'prompt':     prompt_text[:12000] if prompt_text else '',
        'report_url': full_url,
    }
    if week_key not in archive['weeks']:
        archive['weeks'][week_key] = {'runs': []}
    existing = archive['weeks'][week_key]['runs']
    if not any(r.get('id') == run_id for r in existing):
        existing.insert(0, run_entry)
    archive['weeks'][week_key]['runs'] = existing[:10]
    if len(archive['weeks']) > 12:
        for old in sorted(archive['weeks'].keys())[:len(archive['weeks']) - 12]:
            del archive['weeks'][old]
    try:
        tmp = archive_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(archive, f, indent=2)
        os.replace(tmp, archive_path)
    except Exception as e:
        log.error(f'weekly_archive.json write failed: {e}')


def _write_index_page(indices, breadth, regime, index_history=None):
    index_history = index_history or {}
    index_path    = os.path.join(DATA_DIR, 'reports.json')
    rank_path     = os.path.join(DATA_DIR, 'rank.json')
    news_path     = os.path.join(DATA_DIR, 'news.json')
    try:
        with open(index_path, encoding='utf-8') as f:
            reports_data = json.load(f)
    except Exception:
        reports_data = {}
    if not isinstance(reports_data, dict):
        reports = []
    else:
        reports_raw = reports_data.get('reports')
        reports = reports_raw if isinstance(reports_raw, list) else []

    try:
        with open(rank_path, encoding='utf-8') as f:
            rank_data = json.load(f)
    except Exception:
        rank_data = {}
    try:
        with open(news_path, encoding='utf-8') as f:
            news_data = json.load(f)
    except Exception:
        news_data = {}
    now_et = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
    html_content = _render_index_html(reports[:14], rank_data, indices, breadth, regime, now_et, index_history, news_data)
    out_path = os.path.join(DOCS_DIR, 'index.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html_content)


def _write_rank_page():
    rank_path = os.path.join(DATA_DIR, 'rank.json')
    try:
        with open(rank_path, encoding='utf-8') as f:
            rank_data = json.load(f)
    except Exception:
        rank_data = {}
    html_content = _render_rank_html(rank_data)
    with open(os.path.join(DOCS_DIR, 'rank.html'), 'w', encoding='utf-8') as f:
        f.write(html_content)


def _write_archive_page():
    archive_path = os.path.join(DATA_DIR, 'weekly_archive.json')
    try:
        with open(archive_path, encoding='utf-8') as f:
            archive_data = json.load(f)
    except Exception:
        archive_data = {'weeks': {}}
    html_content = _render_archive_html(archive_data)
    with open(os.path.join(DOCS_DIR, 'archive.html'), 'w', encoding='utf-8') as f:
        f.write(html_content)


def _write_news_page(confirmed_sectors: dict) -> None:
    """
    Writes docs/news.html from confirmed_sectors parameter directly.

    Run-current: always reflects this run's state. If nothing confirmed,
    renders a placeholder. Intentional divergence from _write_news_json()
    which preserves stale data on empty runs. This may cause index and news
    page to temporarily display different data states. This is by design.
    """
    if not isinstance(confirmed_sectors, dict):
        confirmed_sectors = {}
    news_html_path = os.path.join(DOCS_DIR, 'news.html')
    if not confirmed_sectors:
        sectors   = []
        generated = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York')).strftime('%Y-%m-%d %H:%M ET')
    else:
        now_et    = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
        generated = now_et.strftime('%Y-%m-%d %H:%M ET')
        sectors   = sorted(
            [
                {'sector': s, 'score': d.get('score', 0), 'articles': d.get('articles', [])}
                for s, d in confirmed_sectors.items()
                if d.get('articles')
            ],
            key=lambda x: x['score'] if isinstance(x['score'], (int, float)) else 0,
            reverse=True,
        )
    html_content = _render_news_html(sectors, generated)
    try:
        tmp = news_html_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(html_content)
        os.replace(tmp, news_html_path)
    except Exception as e:
        log.error(f'news.html write failed: {e}')
def _render_index_html(reports, rank_data, indices, breadth, regime, now_et, index_history, news_data) -> str:
    try:
        indices = indices or {}
        # ── Index pills ──────────────────────────────────────────────────────
        def _pill(key, pill_id, label_text):
            d     = indices.get(key, {})
            val   = _fmt_index_val(d.get('value'))
            chg   = d.get('change_pct')
            lbl   = (d.get('label') or '').upper()
            if isinstance(chg, (int, float)):
                arrow = '\u25b2' if chg > 0 else '\u25bc' if chg < 0 else '\u2014'
                cls   = 'up' if chg > 0 else 'dn' if chg < 0 else 'nt'
                chg_s = f'{arrow} {abs(chg):.2f}% {lbl}'
            else:
                cls   = 'nt'
                chg_s = '\u2014'
            return (
                f'<div class="idx-pill" id="pill-{pill_id}" onclick="toggleIdx(\'{pill_id}\')">'
                f'<div class="pill-left">'
                f'<div class="pill-label" style="font-size:13px;color:var(--pu-lt);font-family:var(--ff-mono);letter-spacing:0.04em;">// {label_text}</div>'
                f'<div class="pill-val">{val}</div>'
                f'<div class="pill-change {cls}">{chg_s}</div>'
                f'</div><div class="pill-chevron">\u25bc</div></div>'
            )

        pills = (
            _pill('dow',    'dow', 'Dow Jones') +
            _pill('sp500',  'sp',  'S&amp;P 500') +
            _pill('nasdaq', 'nq',  'Nasdaq')
        )

        # ── IDX_DATA Pattern B ───────────────────────────────────────────────
        idx_data_dict = _build_idx_data(index_history, indices)
        idx_script    = f'<script>const IDX_DATA={_safe_js_json(idx_data_dict)};</script>'

        # ── Status strip ─────────────────────────────────────────────────────
        b_label   = (breadth.get('label', '') if breadth else '').upper() or 'UNKNOWN'
        r_label   = (regime.get('label', '')  if regime  else '') or 'unknown'
        b_cls     = _breadth_cls(b_label)
        strip = (
            '<div class="status-strip stagger-3">'
            '<span class="ss-label" style="font-size:11px;color:var(--mist);">Breadth</span>'
            f'<span class="ss-val {b_cls}">{_esc(b_label)}</span>'
            '<span class="ss-divider">&middot;</span>'
            '<span class="ss-label" style="font-size:11px;color:var(--mist);">Market</span>'
            f'<span class="ss-val nt">{_esc(r_label)}</span>'
            '</div>'
        )

        # ── Rank preview ─────────────────────────────────────────────────────
        stocks_raw = rank_data.get('stocks', {})
        all_stocks = list(stocks_raw.values()) if isinstance(stocks_raw, dict) else (stocks_raw or [])
        all_stocks = [s for s in all_stocks if isinstance(s, dict)]
        top_stocks = sorted(
            all_stocks,
            key=lambda x: x.get('confidence') if isinstance(x.get('confidence'), (int, float)) else -1,
            reverse=True
        )[:5]

        rp_rows = ''
        for i, s in enumerate(top_stocks, 1):
            conf    = s.get('confidence')
            eq_v    = s.get('eq_verdict_display', '')
            rot_s   = s.get('rotation_signal_display', '')
            verdict = s.get('market_verdict_display') or s.get('market_verdict', '')
            c_cls   = _conf_cls(conf)
            rp_rows += (
                f'<div class="rp-row" onclick="rpT(\'rp{i}\')">'
                f'<div class="rp-n">#{i}</div>'
                f'<div class="rp-tick">{_esc(s.get("ticker", ""))}</div>'
                f'<div class="rp-sect">{_esc(s.get("sector","").replace("_"," ").title())}</div>'
                f'<div class="rp-conf {c_cls}">{_fmt_score(conf, 0)}</div>'
                f'<div style="font-size:11px;color:var(--mist);">{_fmt_score(s.get("risk_score"), 0)}</div>'
                f'<div><span class="ntag {_eq_cls(eq_v)}">{_esc(eq_v) or _EM}</span></div>'
                f'<div><span class="ntag {_rot_cls(rot_s)}">{_esc(rot_s) or _EM}</span></div>'
                f'</div>'
                f'<div class="rp-exp" id="rp{i}"><div class="rp-exp-inner">'
                f'<div class="pex-item"><div class="pex-k">1M Return</div><div class="pex-v">{_fmt_pct(s.get("return_1m"))}</div></div>'
                f'<div class="pex-item"><div class="pex-k">3M Return</div><div class="pex-v">{_fmt_pct(s.get("return_3m"))}</div></div>'
                f'<div class="pex-item"><div class="pex-k">6M Return</div><div class="pex-v">{_fmt_pct(s.get("return_6m"))}</div></div>'
                f'<div class="pex-item"><div class="pex-k">Verdict</div><div class="pex-v {_conf_cls(conf)}">{_esc(verdict)}</div></div>'
                f'</div></div>'
            )
        if not rp_rows:
            rp_rows = '<div style="padding:14px 18px;color:var(--mist);font-size:11px;">No candidates this week.</div>'
        rank_preview = (
            '<div class="rank-preview">'
            '<div class="rank-preview-head">'
            '<span class="rank-preview-title">Top 5 Candidates &middot; Week Rank</span>'
            '<a href="rank.html" class="rp-link">Full &rarr;</a>'
            '</div>'
            '<div class="rp-cols">'
            '<span class="rp-col-h">#</span><span class="rp-col-h">Ticker</span>'
            '<span class="rp-col-h">Sector</span><span class="rp-col-h">Conf</span>'
            '<span class="rp-col-h">Risk</span><span class="rp-col-h">EQ</span>'
            '<span class="rp-col-h">Rotation</span>'
            '</div>'
            f'{rp_rows}'
            '</div>'
        )

        # ── Report cards ─────────────────────────────────────────────────────
        cards_html = ''
        for report_index, r in enumerate(reports, 1):
            vc        = r.get('verdicts', {})
            if isinstance(vc, dict):
                rn_c = vc.get('RESEARCH NOW', 0)
                w_c  = vc.get('WATCH', 0)
                s_c  = vc.get('SKIP', 0)
            else:
                vlist = vc if isinstance(vc, list) else []
                rn_c  = vlist.count('RESEARCH NOW')
                w_c   = vlist.count('WATCH')
                s_c   = vlist.count('SKIP')
            tickers    = ', '.join(_esc(t) for t in (r.get('tickers') or []))
            top_score  = r.get('top_score', 0)
            b          = r.get('breadth', '')
            b_cls      = _breadth_cls(b)
            prompt_text = r.get('prompt', '')
            if prompt_text:
                uid          = f'prompt_{report_index}'
                script_block = f'<script type="application/json" id="{uid}">{_safe_json(prompt_text)}</script>'
                copy_btn     = f'<button class="btn mg copy-prompt-btn" data-ref="{uid}">⧉ Copy AI Prompt</button>'
            else:
                script_block = ''
                copy_btn     = ''
            report_url = r.get('report_url', '')
            full_btn   = f'<a href="{report_url}" class="btn" target="_blank" onclick="event.stopPropagation()">{chr(0x2197)} Full Report</a>' if report_url else ''
            count      = r.get('count', 0)
            cards_html += (
                f'{script_block}'
                f'<div class="rcard" onclick="rcT(this)">'
                f'<div class="rcard-head">'
                f'<div>'
                f'<div class="rcard-date">{_esc(r.get("date",""))} &middot; {_esc(r.get("slot",""))} &middot; {count} stock{"s" if count!=1 else ""}</div>'
                f'<div class="rcard-slot" style="font-size:11px;color:var(--mist);">{_esc(r.get("time",""))} ET &middot; {_esc(r.get("regime","").title())}</div>'
                f'</div>'
                f'<span class="rcard-badge {b_cls}">{_esc(b).title()}</span>'
                f'</div>'
                f'<div class="rcard-body"><div class="rcard-inner">'
                f'<div class="rcard-cols">'
                f'<div><div class="rcc-k">Sys 1 &middot; Tickers</div><div class="rcc-v">{tickers or _EM}'
                f'<br><span style="font-size:11px;color:var(--mist)">Top conf: {_fmt_score(top_score, 0)}/100</span></div></div>'
                f'<div><div class="rcc-k">Verdicts</div><div class="rcc-v">'
                f'<span style="color:var(--up)">RN:{rn_c}</span> '
                f'<span style="color:var(--nt)">W:{w_c}</span> '
                f'<span style="color:var(--dn)">S:{s_c}</span></div></div>'
                f'<div><div class="rcc-k">Breadth</div><div class="rcc-v" style="color:var(--{b_cls})">{_esc(b).title()}</div></div>'
                f'</div>'
                f'<div class="rcard-btns">{full_btn}{copy_btn}</div>'
                f'</div></div></div>'
            )
        if not cards_html:
            cards_html = '<div style="color:var(--mist);font-family:var(--ff-mono);font-size:11px;">No reports yet.</div>'

        # ── Signal Headlines ──────────────────────────────────────────────────
        try:
            sectors_list = news_data.get('sectors') if isinstance(news_data, dict) else None
            if not isinstance(sectors_list, list):
                sectors_list = []
            all_articles = []
            for sec in sectors_list:
                for art in sec.get('articles', []):
                    new_art = dict(art)
                    new_art['sector'] = sec.get('sector', '')
                    all_articles.append(new_art)
            all_articles.sort(
                key=lambda x: x.get('score') if isinstance(x.get('score'), (int, float)) else 0,
                reverse=True
            )
            top_headlines = all_articles[:5]
        except Exception:
            top_headlines = []

        npc_html = ''
        for art in top_headlines:
            score    = art.get('score', 0)
            sc       = 'var(--up)' if isinstance(score,(int,float)) and score>5 else 'var(--nt)' if isinstance(score,(int,float)) and score>2 else 'var(--pu-lt)'
            title    = _esc((art.get('title') or '')[:120])
            sector   = _esc((art.get('sector') or '').replace('_',' ').title())
            source   = _esc(art.get('source') or 'Unknown')
            pub      = _esc(art.get('published') or '')
            npc_html += (
                f'<div class="npc">'
                f'<div class="npc-stripe" style="background:linear-gradient(180deg,{sc},transparent)"></div>'
                f'<div>'
                f'<div class="npc-title">{title}</div>'
                f'<div class="npc-meta"><span class="ntag pu">{sector}</span> {source} &middot; {pub}</div>'
                f'</div></div>'
            )
        if not npc_html:
            npc_html = '<div style="color:var(--mist);font-family:var(--ff-mono);font-size:11px;">No signal headlines this run.</div>'

        # ── Inline page CSS ───────────────────────────────────────────────────
        page_css = (
            '<style>'
            '.idx-taskbar{display:flex;gap:8px;}'
            '.idx-chart-wrap canvas{width:100%!important;height:100%!important;}'
            '.exp-chart canvas{width:100%!important;height:100%!important;}'
            '</style>'
        )

        scan_time = now_et.strftime('%Y-%m-%d %H:%M ET')
        cand_count = rank_data.get('week', '')
        pg_sub     = f'{scan_time} &middot; Last scan'

        js_block = (
            f'<script>{_DAYS_JS}{_EASING_JS}{_GENIE_JS}{_SLIDE_JS}'
            f'{_TOGGLE_IDX_JS}{_BUILD_IDX_CHART_JS}'
            f'{_RAF_COLLAPSE_JS}{_RCT_JS}</script>'
            f'{idx_script}'
            f'<script>{_COPY_PROMPT_JS}</script>'
        )

        return (
            '<!DOCTYPE html><html lang="en"><head>'
            '<meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
            '<meta name="description" content="MRE Market Research Engine — Live dashboard">'
            '<title>MRE // Market Overview</title>'
            f'{_FONTS_LINK}'
            f'{_CHARTJS}'
            '<link rel="stylesheet" href="assets/style.css">'
            f'{page_css}'
            '</head><body>'
            '<div class="scanlines"></div>'
            f'{_nav_html("home")}'
            '<div class="pages"><div id="p-home" class="page on">'
            '<div class="pg-eyebrow stagger-1">Dashboard &middot; Active</div>'
            '<div class="pg-title stagger-1">Market <span class="hi">Overview</span></div>'
            f'<div class="pg-sub stagger-1">{pg_sub}</div>'
            '<div class="idx-section stagger-2">'
            '<div class="sl">Market Indices &middot; 30-day</div>'
            f'<div class="idx-taskbar">{pills}</div>'
            '<div class="idx-expand" id="idx-expand">'
            '<div class="idx-slide-viewport" id="idx-slide-viewport">'
            '<div class="idx-slide-track" id="idx-slide-track">'
            '<div class="idx-panel" id="idx-panel-active">'
            '<div class="idx-panel-header">'
            '<div class="idx-expand-name" id="idx-expand-name">\u2014</div>'
            '<div class="idx-expand-stats">'
            '<span>1M <span class="val" id="idx-stat-1m">\u2014</span></span>'
            '<span>3M <span class="val" id="idx-stat-3m">\u2014</span></span>'
            '<span>6M <span class="val" id="idx-stat-6m">\u2014</span></span>'
            '</div></div>'
            '<div class="idx-chart-wrap"><canvas id="idx-chart"></canvas></div>'
            '</div></div></div></div>'
            '</div>'
            '<div class="home-below" id="home-below">'
            f'{strip}'
            '<div class="stagger-4">'
            '<div class="sl">This Week\'s Best <a href="rank.html" class="rp-link" style="margin-left:8px">Full board &rarr;</a></div>'
            f'{rank_preview}'
            '</div>'
            '<div class="stagger-5">'
            '<div class="sl" style="margin-top:28px">Recent Reports</div>'
            f'{cards_html}'
            '</div>'
            '<div class="stagger-5">'
            '<div class="sl" style="margin-top:28px">Signal Headlines '
            '<a href="news.html" class="rp-link" style="margin-left:8px">All &rarr;</a></div>'
            f'<div class="npc-group">{npc_html}</div>'
            '</div>'
            '</div>'
            '</div></div>'
            '<footer><span>MRE</span> &middot; Free-tier data only &middot; Not investment advice &middot; Always verify before acting</footer>'
            f'{js_block}'
            '</body></html>'
        )
    except Exception as e:
        log.error(f'Index page render failed: {e}')
        return _err_page('home', 'Dashboard render error. Check logs.')


def _render_rank_html(rank_data: dict) -> str:
    try:
        stocks_raw = rank_data.get('stocks', {})
        stocks     = list(stocks_raw.values()) if isinstance(stocks_raw, dict) else (stocks_raw or [])
        stocks     = [s for s in stocks if isinstance(s, dict)]
        stocks     = sorted(
            stocks,
            key=lambda x: x.get('confidence') if isinstance(x.get('confidence'), (int, float)) else -1,
            reverse=True
        )
        week = rank_data.get('week', '')

        rows_html  = ''
        ph_scripts = ''
        for i, stock in enumerate(stocks, 1):
            conf    = stock.get('confidence')
            risk    = stock.get('risk_score')
            eq_v    = stock.get('eq_verdict_display', '')
            rot_s   = stock.get('rotation_signal_display', '')
            verdict = stock.get('market_verdict_display') or stock.get('market_verdict', '')
            raw_ph  = stock.get('price_history') or []
            ph_list = _sanitize_price_history(raw_ph)
            has_ch  = len(ph_list) > 1
            ph_uid  = f'ph-{i}'
            ph_scripts += f'<script type="application/json" id="{ph_uid}">{_safe_json(ph_list)}</script>'

            chart_el = f'<canvas id="ec{i}" height="92"></canvas>' if has_ch else '<div style="color:var(--mist);font-size:11px;padding:8px 0;">Price history unavailable</div>'
            exp_row = (
                f'<div class="exp-row" id="e{i}"><div class="exp-inner">'
                f'<div class="exp-stats">'
                f'<div class="est"><div class="est-k">1M</div><div class="est-v">{_fmt_pct(stock.get("return_1m"))}</div></div>'
                f'<div class="est"><div class="est-k">3M</div><div class="est-v">{_fmt_pct(stock.get("return_3m"))}</div></div>'
                f'<div class="est"><div class="est-k">6M</div><div class="est-v">{_fmt_pct(stock.get("return_6m"))}</div></div>'
                f'<div class="est"><div class="est-k">Verdict</div><div class="est-v {_conf_cls(conf)}">{_esc(verdict) or _EM}</div></div>'
                f'<div class="est"><div class="est-k">Align</div><div class="est-v {_align_cls(stock.get("alignment", ""))}">{_esc(stock.get("alignment", "")) or _EM}</div></div>'
                f'</div>'
                f'<div class="exp-chart">{chart_el}</div>'
                f'</div></div>'
            )
            rows_html += (
                f'<div class="rank-row" data-ref="{ph_uid}" data-eid="e{i}" data-cid="ec{i}" onclick="expT(this)">'
                f'<div class="td-n">#{i}</div>'
                f'<div class="td-t">{_esc(stock.get("ticker",""))}</div>'
                f'<div class="td-s">{_esc(stock.get("sector","").replace("_"," ").title())}</div>'
                f'<div class="td-p">{_fmt_price(stock.get("price"))}</div>'
                f'<div class="td-c {_conf_cls(conf)}">{_fmt_score(conf,0)}</div>'
                f'<div class="td-r">{_fmt_score(risk,0)}</div>'
                f'<div><span class="ntag {_eq_cls(eq_v)}" style="font-size:8px">{_esc(eq_v) or _EM}</span></div>'
                f'<div><span class="ntag {_rot_cls(rot_s)}" style="font-size:8px">{_esc(rot_s) or _EM}</span></div>'
                f'</div>'
                f'{exp_row}'
            )

        if not rows_html:
            rows_html = '<div style="color:var(--mist);font-family:var(--ff-mono);padding:28px;">No candidates this week.</div>'

        week_display = week.replace('W', ' \u2014 week ') if week else 'current week'


        return (
            '<!DOCTYPE html><html lang="en"><head>'
            '<meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
            '<meta name="description" content="MRE Weekly Rank Board">'
            '<title>MRE // Weekly Rankings</title>'
            f'{_FONTS_LINK}'
            f'{_CHARTJS}'
            '<link rel="stylesheet" href="assets/style.css">'
            '<style>.exp-chart canvas{width:100%!important;height:100%!important;}</style>'
            '</head><body>'
            '<div class="scanlines"></div>'
            f'{_nav_html("rank")}'
            '<div class="pages"><div id="p-rank" class="page on">'
            '<div class="pg-eyebrow">Rank Board &middot; Active</div>'
            '<div class="pg-title">Weekly <span class="hi">Rankings</span></div>'
            f'<div class="pg-sub">{_esc(week_display)} &middot; Resets Monday &middot; Click row to expand</div>'
            '<div class="rank-wrap">'
            '<div class="rank-head">'
            '<span class="rth">#</span><span class="rth">Ticker</span><span class="rth">Sector</span>'
            '<span class="rth">Price</span><span class="rth">Conf</span><span class="rth">Risk</span>'
            '<span class="rth">EQ</span><span class="rth">Rotation</span>'
            '</div>'
            f'{rows_html}'
            '</div>'
            '</div></div>'
            '<footer><span>MRE</span> &middot; Free-tier data only &middot; Not investment advice</footer>'
            f'{ph_scripts}'
            f'<script>{_DAYS_JS}{_EXP_T_JS}{_RAF_COLLAPSE_JS}{_COPY_PROMPT_JS}</script>'
            '</body></html>'
        )
    except Exception as e:
        log.error(f'Rank page render failed: {e}')
        return _err_page('rank', 'Rank render error. Check logs.')

def _render_archive_html(archive_data: dict) -> str:
    try:
        weeks_raw = archive_data.get('weeks', {})
        if not isinstance(weeks_raw, dict):
            weeks_raw = {}
        week_keys = sorted(weeks_raw.keys(), reverse=True)

        blocks_html = ''
        for wk in week_keys:
            week_info = weeks_raw[wk]
            runs      = week_info.get('runs', []) if isinstance(week_info, dict) else []
            label     = wk.replace('W', ' \u2014 Week ')
            cards_html = ''
            for run_idx, run in enumerate(runs):
                slot    = run.get('slot', '')
                ts      = run.get('timestamp', '')
                breadth = run.get('breadth', '')
                regime  = run.get('regime', '')
                count   = run.get('count', 0)
                run_type = run.get('run_type', '')
                b_cls   = _breadth_cls(breadth)
                cands   = run.get('candidates', [])
                tickers = ', '.join(_esc(c.get('ticker', '')) for c in cands[:5])
                top_conf = max((c.get('confidence', 0) for c in cands), default=0) if cands else 0
                vc      = run.get('verdict_counts', {})
                rn_c    = vc.get('RESEARCH NOW', 0) if isinstance(vc, dict) else 0
                w_c     = vc.get('WATCH', 0)        if isinstance(vc, dict) else 0
                s_c     = vc.get('SKIP', 0)         if isinstance(vc, dict) else 0
                prompt_text = run.get('prompt', '')
                if prompt_text:
                    uid          = f'arc_{wk}_{run_idx}'
                    script_block = f'<script type="application/json" id="{uid}">{_safe_json(prompt_text)}</script>'
                    copy_btn     = f'<button class="btn mg copy-prompt-btn" data-ref="{uid}">⧉ Copy AI Prompt</button>'
                else:
                    script_block = ''
                    copy_btn     = ''
                report_url = run.get('report_url', '')
                full_btn   = f'<a href="{report_url}" class="btn" target="_blank" onclick="event.stopPropagation()">{chr(0x2197)} Full Report</a>' if report_url else ''
                rtype_badge = f'<span style="font-size:8px;color:var(--sun);margin-left:8px">{_esc(run_type)}</span>' if run_type == 'MANUAL' else ''
                cards_html += (
                    f'{script_block}'
                    f'<div class="rcard" onclick="rcT(this)">'
                    f'<div class="rcard-head"><div>'
                    f'<div class="rcard-date">{_esc(ts)} &middot; {_esc(slot)} &middot; {count} stock{"s" if count!=1 else ""}{rtype_badge}</div>'
                    f'<div class="rcard-slot">{_esc(regime).title()}</div>'
                    f'</div><span class="rcard-badge {b_cls}">{_esc(breadth).title()}</span></div>'
                    f'<div class="rcard-body"><div class="rcard-inner">'
                    f'<div class="rcard-cols">'
                    f'<div><div class="rcc-k">Sys 1</div><div class="rcc-v">{tickers or _EM}'
                    f'<br><span style="color:var(--mist);font-size:10px">Top conf: {_fmt_score(top_conf, 0)}/100</span></div></div>'
                    f'<div><div class="rcc-k">Verdicts</div><div class="rcc-v">'
                    f'<span style="color:var(--up)">RN:{rn_c}</span> <span style="color:var(--nt)">W:{w_c}</span> <span style="color:var(--dn)">S:{s_c}</span>'
                    f'</div></div>'
                    f'<div><div class="rcc-k">Breadth</div><div class="rcc-v" style="color:var(--{b_cls})">{_esc(breadth).title()}</div></div>'
                    f'</div>'
                    f'<div class="rcard-btns">{full_btn}{copy_btn}</div>'
                    f'</div></div></div>'
                )
            blocks_html += (
                f'<div class="week-block">'
                f'<div class="week-head">{_esc(label)} <span class="week-count">{len(runs)} report{"s" if len(runs)!=1 else ""}</span></div>'
                f'{cards_html}'
                f'</div>'
            )
        if not blocks_html:
            blocks_html = '<div style="color:var(--mist);font-family:var(--ff-mono);font-size:11px;padding:28px;">No archive data yet.</div>'

        return (
            '<!DOCTYPE html><html lang="en"><head>'
            '<meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
            '<meta name="description" content="MRE Report Archive">'
            '<title>MRE // Report Archive</title>'
            f'{_FONTS_LINK}'
            '<link rel="stylesheet" href="assets/style.css">'
            '</head><body>'
            '<div class="scanlines"></div>'
            f'{_nav_html("archive")}'
            '<div class="pages"><div id="p-archive" class="page on">'
            '<div class="pg-eyebrow">History &middot; Stored</div>'
            '<div class="pg-title">Report <span class="hi">Archive</span></div>'
            '<div class="pg-sub">12 weeks retained &middot; 10 runs per week max</div>'
            f'{blocks_html}'
            '</div></div>'
            '<footer><span>MRE</span> &middot; Free-tier data only &middot; Not investment advice</footer>'
            f'<script>{_RCT_JS}{_COPY_PROMPT_JS}</script>'
            '</body></html>'
        )
    except Exception as e:
        log.error(f'Archive render failed: {e}')
        return _err_page('archive', 'Archive render error. Check logs.')


def _render_news_html(sectors: list, generated: str) -> str:
    try:
        if not sectors:
            body = (
                '<div style="color:var(--mist);font-family:var(--ff-mono);font-size:11px;padding:28px 0;">'
                'No sector news this run. Headlines will appear when sector signals are confirmed.'
                '</div>'
            )
        else:
            body = ''
            stripe_colors = [
                'linear-gradient(180deg,var(--up),transparent)',
                'linear-gradient(180deg,var(--nt),transparent)',
                'linear-gradient(180deg,var(--pu-lt),transparent)',
                'linear-gradient(180deg,var(--cyan),transparent)',
                'linear-gradient(180deg,var(--mg),transparent)',
            ]
            for si, sec in enumerate(sectors):
                sector_name = _esc((sec.get('sector') or '').replace('_', ' ').title())
                articles    = sec.get('articles', [])
                if not articles:
                    continue
                sc = stripe_colors[si % len(stripe_colors)]
                body += (
                    f'<div class="news-section">'
                    f'<div class="news-sec-head">'
                    f'<div class="nsh-stripe" style="background:{sc}"></div>'
                    f'<span class="nsh-name">{sector_name}</span>'
                    f'<span class="nsh-count">// {len(articles)} article{"s" if len(articles)!=1 else ""}</span>'
                    f'</div>'
                )
                for art in articles:
                    title   = _esc((art.get('title') or '')[:200])
                    summary = _esc((art.get('body') or art.get('summary') or '')[:400])
                    source  = _esc(art.get('source') or 'Unknown')
                    pub     = _esc(art.get('published') or '')
                    body    += (
                        f'<div class="news-card-full">'
                        f'<div class="ncf-title">{title}</div>'
                        f'<div class="ncf-summary">{summary}</div>'
                        f'<div class="ncf-foot">'
                        f'<span class="ncf-source">{source} &middot; {pub}</span>'
                        f'</div></div>'
                    )
                body += '</div>'

        return (
            '<!DOCTYPE html><html lang="en"><head>'
            '<meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
            '<meta name="description" content="MRE Signal Feed">'
            '<title>MRE // Signal Feed</title>'
            f'{_FONTS_LINK}'
            '<link rel="stylesheet" href="assets/style.css">'
            '</head><body>'
            '<div class="scanlines"></div>'
            f'{_nav_html("news")}'
            '<div class="pages"><div id="p-news" class="page on">'
            '<div class="pg-eyebrow">Signal Feed &middot; Current</div>'
            '<div class="pg-title">Today\'s <span class="hi">News</span></div>'
            f'<div class="pg-sub">Engine-filtered headlines &middot; {_esc(generated)}</div>'
            f'{body}'
            '</div></div>'
            '<footer><span>MRE</span> &middot; Free-tier data only &middot; Not investment advice</footer>'
            '</body></html>'
        )
    except Exception as e:
        log.error(f'News render failed: {e}')
        return _err_page('news', 'News render error. Check logs.')


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def build_dashboard(
    companies,
    slot,
    indices,
    breadth,
    regime,
    rotation=None,
    *,
    full_url='',
    prompt_text='',
    is_debug=False,
    index_history=None,
    confirmed_sectors=None,
):
    """
    Main dashboard builder. Call from main.py after build_intraday_report().

    Parameters
    ----------
    companies : list of company dicts (standard System 1 output)
    slot      : str — e.g. 'morning', 'midday', 'closing'
    indices   : dict — keys: 'dow', 'sp500', 'nasdaq'; values: {value, change_pct, label}
    breadth   : dict — {label: str}
    regime    : dict — {label: str}
    full_url  : str — GitHub Pages report URL
    prompt_text : str — AI research prompt for copy button
    is_debug  : bool — if True, tags archive entry as MANUAL
    index_history : dict — keys 'dow', 'sp500', 'nasdaq'; values: list[float] (30+ closes)
    confirmed_sectors : dict — sector name → {score, articles:[]} from SectorSignalAccumulator
    """
    index_history     = index_history     or {}
    confirmed_sectors = confirmed_sectors or {}
    os.makedirs(DATA_DIR, exist_ok=True)
    companies = companies or []

    # ── Write index_history.json ────────────────────────────────────────────
    if index_history:
        try:
            ih_path = os.path.join(DATA_DIR, 'index_history.json')
            tmp     = ih_path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(index_history, f, indent=2)
            os.replace(tmp, ih_path)
        except Exception as e:
            log.warning(f'index_history.json write failed: {e}')

    # ── Update data stores ──────────────────────────────────────────────────
    try:
        _update_reports_index(companies, slot, indices, breadth, regime, full_url, prompt_text)
    except Exception as e:
        log.error(f'_update_reports_index error: {e}')

    try:
        _update_rank_board(companies)
    except Exception as e:
        log.error(f'_update_rank_board error: {e}')

    try:
        _update_weekly_archive(companies, slot, breadth, regime, prompt_text, is_debug, full_url)
    except Exception as e:
        log.error(f'_update_weekly_archive error: {e}')

    # ── Write news data ─────────────────────────────────────────────────────
    try:
        _write_news_json(confirmed_sectors)
    except Exception as e:
        log.error(f'_write_news_json error: {e}')

    # ── Render all pages ────────────────────────────────────────────────────
    try:
        _write_index_page(indices, breadth, regime, index_history)
        log.info('index.html written')
    except Exception as e:
        log.error(f'index.html write failed: {e}')

    try:
        _write_rank_page()
        log.info('rank.html written')
    except Exception as e:
        log.error(f'rank.html write failed: {e}')

    try:
        _write_archive_page()
        log.info('archive.html written')
    except Exception as e:
        log.error(f'archive.html write failed: {e}')

    try:
        _write_news_page(confirmed_sectors)
        log.info('news.html written')
    except Exception as e:
        log.error(f'news.html write failed: {e}')

    log.info('build_dashboard complete')

