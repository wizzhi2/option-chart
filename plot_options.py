import datetime
import json
import re

from IPython.display import display, HTML, Javascript


def plot_strikes_3d(candidates=None, today=None):
    """Render an interactive 3-D scatter/grid of candidate strikes.

    X axis : expiry date (days from today)
    Y axis : strike price
    Z axis : bid price  (same units as plot_timeline Y axis)

    Mouse drag rotates the scene; scroll zooms.

    Parameters
    ----------
    candidates : list of dict
        Same format as the ``candidates`` arg of plot_timeline:
        keys ``Date`` (date), ``Strike`` (float), ``Bid`` (float).
    today : date, optional
        Override today's date.
    """
    if today is None:
        today = datetime.date.today()
    if candidates is None:
        candidates = []

    if not candidates:
        display(HTML("<p>No candidate data to plot.</p>"))
        return

    points = []
    for r in candidates:
        exp = r["Date"]
        days_to_exp = (exp - today).days
        bid = float(r["Bid"])
        daily_yield = bid / days_to_exp if days_to_exp > 0 else 0.0
        points.append({
            "x": days_to_exp,
            "y": float(r["Strike"]),
            "z": bid,
            "dy": daily_yield,
            "label": f"Strike ${r['Strike']:.1f} | 到期日{exp}({days_to_exp}d) | 权益金 ${bid:.2f}({daily_yield*100:.2f}$/d)",
        })

    pts_json = json.dumps(points)
    uid = f"s3d_{abs(hash(pts_json)) % 10**8}"

    html_part = f"""
<div id="viz_{uid}" style="position:relative;width:820px;height:680px;
  font-family:system-ui,-apple-system,'Segoe UI',sans-serif;font-size:13px;
  background:#fcfcfb;border-radius:8px;padding:0;">
  <div style="position:absolute;top:10px;left:16px;font-size:14px;font-weight:600;color:#0b0b0b;">Strike Candidates — 3-D View</div>
  <div style="position:absolute;top:30px;left:16px;font-size:12px;color:#52514e;">Drag to rotate · Scroll to zoom</div>
  <div style="position:absolute;bottom:28px;right:14px;font-size:11px;color:#52514e;line-height:1.7;">
    <span style="color:#2563eb">X</span> = Days to expiry &nbsp;
    <span style="color:#16a34a">Y</span> = Strike ($) &nbsp;
    <span style="color:#dc2626">Z</span> = Bid ($)
  </div>
  <div style="position:absolute;bottom:10px;left:16px;font-size:11px;color:#898781;">Each dot: one strike/expiry combination</div>
  <canvas id="c_{uid}" width="820" height="680"
    style="display:block;cursor:grab;"></canvas>
  <div id="tt_{uid}" style="position:absolute;background:#fcfcfb;border:1px solid #e1e0d9;
    border-radius:6px;padding:7px 11px;font-size:12px;color:#0b0b0b;
    pointer-events:none;display:none;box-shadow:0 2px 8px rgba(0,0,0,.12);white-space:nowrap;"></div>
</div>"""

    js_part = f"""
(function() {{
  var canvas = document.getElementById("c_{uid}");
  if (!canvas) {{ return; }}
  var ctx = canvas.getContext("2d");
  var tt  = document.getElementById("tt_{uid}");
  var vizEl = document.getElementById("viz_{uid}");

  var RAW = {pts_json};
  var W=820, H=680, CX=W/2, CY=H/2+60, SCALE=260;

  var xs=RAW.map(function(p){{return p.x;}}),
      ys=RAW.map(function(p){{return p.y;}}),
      zs=RAW.map(function(p){{return p.z;}}),
      dys=RAW.map(function(p){{return p.dy;}});
  var xMin=Math.min.apply(null,xs), xMax=Math.max.apply(null,xs);
  var yMin=Math.min.apply(null,ys), yMax=Math.max.apply(null,ys);
  var zMin=Math.min.apply(null,zs), zMax=Math.max.apply(null,zs);
  var dyMin=Math.min.apply(null,dys), dyMax=Math.max.apply(null,dys);
  function norm(v,mn,mx){{ return mx>mn?(v-mn)/(mx-mn):0.5; }}

  var pts = RAW.map(function(p){{
    return {{nx:norm(p.x,xMin,xMax)-.5, ny:norm(p.y,yMin,yMax)-.5,
            nz:norm(p.z,zMin,zMax)-.5,
            ndy:norm(p.dy,dyMin,dyMax), raw:p}};
  }});

  // color by Bid/Days (daily yield): bottom 30% = blue, top 30% = red, middle 60% uses full hue range
  function dotColor(ndy01){{
    var lo=0.30, hi=0.70;
    var t=ndy01<lo?0:ndy01>hi?1:(ndy01-lo)/(hi-lo);
    var hue=Math.round((1-t)*240);
    return "hsl("+hue+",80%,42%)";
  }}

  // vertical legend on the left: bar runs top=high(red) to bottom=low(blue)
  var LX=16, LY=100, LW=12, LH=400;
  function drawLegend(){{
    var lo=0.30, hi=0.70;
    // gradient bar — top=high yield (red), bottom=low yield (blue)
    var grad=ctx.createLinearGradient(0,LY,0,LY+LH);
    grad.addColorStop(0,   "hsl(0,80%,42%)");
    grad.addColorStop(1-hi,"hsl(0,80%,42%)");
    grad.addColorStop(0.50,"hsl(120,80%,42%)");
    grad.addColorStop(1-lo,"hsl(240,80%,42%)");
    grad.addColorStop(1,   "hsl(240,80%,42%)");
    ctx.save();
    ctx.beginPath();
    ctx.roundRect(LX,LY,LW,LH,3);
    ctx.fillStyle=grad; ctx.fill();
    ctx.strokeStyle="#ccc"; ctx.lineWidth=0.5; ctx.stroke();
    // label above bar
    ctx.font="bold 11px system-ui,sans-serif";
    ctx.fillStyle="#0b0b0b"; ctx.textAlign="center";
    ctx.fillText("Bid/Day",LX+LW/2,LY-14);
    ctx.fillText("(¢/d)",  LX+LW/2,LY-3);
    // ticks: fixed breakpoints + every actual data dy value
    ctx.font="10px system-ui,sans-serif"; ctx.textAlign="left";
    var tickNdys=[0, lo, 0.50, hi, 1.0];
    dys.forEach(function(dy){{ tickNdys.push(norm(dy,dyMin,dyMax)); }});
    tickNdys.sort(function(a,b){{return a-b;}});
    var kept=[];
    tickNdys.forEach(function(v){{
      if(!kept.length||v-kept[kept.length-1]>0.03) kept.push(v);
    }});
    kept.forEach(function(nv){{
      // nv=0 → bottom of bar (low/blue), nv=1 → top (high/red)
      var ty=LY+LH-(nv*LH);
      var val=(dyMin+nv*(dyMax-dyMin))*100;
      var col=dotColor(nv);
      ctx.strokeStyle=col; ctx.lineWidth=1;
      ctx.beginPath(); ctx.moveTo(LX+LW,ty); ctx.lineTo(LX+LW+4,ty); ctx.stroke();
      ctx.fillStyle=col;
      ctx.textAlign="left";
      ctx.fillText(val.toFixed(2)+"¢", LX+LW+7, ty+3.5);
    }});
    ctx.restore();
  }}

  // default view
  var rotX=-3.14/2+0.2, rotY=-0.1, zoom=1.5;
  var dragging=false, lastMX=0, lastMY=0;

  function rotMatX(a){{var c=Math.cos(a),s=Math.sin(a);return [[1,0,0],[0,c,-s],[0,s,c]];}}
  function rotMatY(a){{var c=Math.cos(a),s=Math.sin(a);return [[c,0,s],[0,1,0],[-s,0,c]];}}
  function mul(M,v){{return [M[0][0]*v[0]+M[0][1]*v[1]+M[0][2]*v[2],
                             M[1][0]*v[0]+M[1][1]*v[1]+M[1][2]*v[2],
                             M[2][0]*v[0]+M[2][1]*v[1]+M[2][2]*v[2]];}}
  function projectV(nx,ny,nz){{
    var v=mul(rotMatX(rotX),[nx,ny,nz]);
    v=mul(rotMatY(rotY),v);
    var s=SCALE*zoom;
    return {{sx:CX+v[0]*s, sy:CY-v[1]*s, depth:v[2]}};
  }}
  function project(p){{ return projectV(p.nx,p.ny,p.nz); }}

  var CORNERS=[[-0.5,-0.5,-0.5],[0.5,-0.5,-0.5],[0.5,0.5,-0.5],[-0.5,0.5,-0.5],
               [-0.5,-0.5,0.5],[0.5,-0.5,0.5],[0.5,0.5,0.5],[-0.5,0.5,0.5]];
  var EDGES=[[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];

  function draw(){{
    ctx.clearRect(0,0,W,H);
    drawLegend();
    // bounding box
    var cp=CORNERS.map(function(c){{return projectV(c[0],c[1],c[2]);}});
    ctx.save(); ctx.strokeStyle="#d4d2c9"; ctx.lineWidth=0.8; ctx.setLineDash([3,3]);
    EDGES.forEach(function(e){{
      ctx.beginPath(); ctx.moveTo(cp[e[0]].sx,cp[e[0]].sy);
      ctx.lineTo(cp[e[1]].sx,cp[e[1]].sy); ctx.stroke();
    }}); ctx.setLineDash([]); ctx.restore();
    // axes
    var o=projectV(-.5,-.5,-.5);
    [[projectV(.5,-.5,-.5),"#2563eb"],[projectV(-.5,.5,-.5),"#16a34a"],[projectV(-.5,-.5,.5),"#dc2626"]].forEach(function(pair){{
      ctx.save(); ctx.strokeStyle=pair[1]; ctx.lineWidth=2;
      ctx.beginPath(); ctx.moveTo(o.sx,o.sy); ctx.lineTo(pair[0].sx,pair[0].sy); ctx.stroke(); ctx.restore();
    }});
    // axis ticks
    ctx.font="14px system-ui,sans-serif";
    var xVals=[...new Set(xs)].sort(function(a,b){{return a-b;}});
    xVals.forEach(function(xv){{
      var p=projectV(norm(xv,xMin,xMax)-.5,-.5,-.5);
      ctx.fillStyle="#2563eb"; ctx.fillText(xv+"d",p.sx+3,p.sy+3);
    }});
    for(var i=0;i<=4;i++){{
      var yv=yMin+i*(yMax-yMin)/4;
      var p=projectV(-.5,norm(yv,yMin,yMax)-.5,-.5);
      ctx.fillStyle="#16a34a"; ctx.fillText("$"+Math.round(yv),p.sx+3,p.sy+3);
    }}
    for(var i=0;i<=4;i++){{
      var zv=zMin+i*(zMax-zMin)/4;
      var p=projectV(-.5,-.5,norm(zv,zMin,zMax)-.5);
      ctx.fillStyle="#dc2626"; ctx.fillText("$"+zv.toFixed(2),p.sx+3,p.sy+3);
    }}
    // grid lines — same expiry (along strike axis) and same strike (along expiry axis)
    ctx.save(); ctx.lineWidth=0.9; ctx.globalAlpha=0.28;
    // along-strike lines: group by expiry day, sort by strike, connect neighbours
    var byExpiry={{}};
    pts.forEach(function(p){{
      var k=p.raw.x;
      if(!byExpiry[k]) byExpiry[k]=[];
      byExpiry[k].push(p);
    }});
    Object.keys(byExpiry).forEach(function(k){{
      var row=byExpiry[k].slice().sort(function(a,b){{return a.raw.y-b.raw.y;}});
      for(var i=0;i<row.length-1;i++){{
        var a=project(row[i]), b=project(row[i+1]);
        var col=dotColor((row[i].ndy+row[i+1].ndy)/2);
        ctx.strokeStyle=col;
        ctx.beginPath(); ctx.moveTo(a.sx,a.sy); ctx.lineTo(b.sx,b.sy); ctx.stroke();
      }}
    }});
    // along-expiry lines: group by strike, sort by expiry day, connect neighbours
    var byStrike={{}};
    pts.forEach(function(p){{
      var k=p.raw.y;
      if(!byStrike[k]) byStrike[k]=[];
      byStrike[k].push(p);
    }});
    Object.keys(byStrike).forEach(function(k){{
      var row=byStrike[k].slice().sort(function(a,b){{return a.raw.x-b.raw.x;}});
      for(var i=0;i<row.length-1;i++){{
        var col=dotColor((row[i].ndy+row[i+1].ndy)/2);
        ctx.strokeStyle=col;
        var a=project(row[i]), b=project(row[i+1]);
        ctx.beginPath(); ctx.moveTo(a.sx,a.sy); ctx.lineTo(b.sx,b.sy); ctx.stroke();
      }}
    }});
    ctx.globalAlpha=1; ctx.restore();

    // dots back-to-front
    var sorted=pts.map(function(p){{var pr=project(p);return {{pr:pr,p:p}};}});
    sorted.sort(function(a,b){{return a.pr.depth-b.pr.depth;}});
    sorted.forEach(function(item){{
      var col=dotColor(item.p.ndy);
      ctx.beginPath(); ctx.arc(item.pr.sx,item.pr.sy,5,0,Math.PI*2);
      ctx.fillStyle=col; ctx.globalAlpha=0.85; ctx.fill();
      ctx.globalAlpha=1; ctx.strokeStyle="#fff"; ctx.lineWidth=0.8; ctx.stroke();
    }});
  }}

  draw();

  canvas.addEventListener("mousedown",function(e){{dragging=true;lastMX=e.clientX;lastMY=e.clientY;}});
  document.addEventListener("mouseup",function(){{dragging=false;}});
  document.addEventListener("mousemove",function(e){{
    if(!dragging)return;
    rotY+=(e.clientX-lastMX)*0.01; rotX+=(e.clientY-lastMY)*0.01;
    lastMX=e.clientX; lastMY=e.clientY; draw();
  }});
  canvas.addEventListener("wheel",function(e){{
    e.preventDefault();
    zoom*=e.deltaY>0?0.93:1.07; zoom=Math.min(Math.max(zoom,0.3),4); draw();
  }},{{passive:false}});

  canvas.addEventListener("mousemove",function(e){{
    if(dragging){{tt.style.display="none";return;}}
    var rect=canvas.getBoundingClientRect();
    var mx=(e.clientX-rect.left)*(W/rect.width), my=(e.clientY-rect.top)*(H/rect.height);
    var best=null, bestD=Infinity;
    pts.forEach(function(p){{
      var pr=project(p), d=Math.hypot(pr.sx-mx,pr.sy-my);
      if(d<bestD){{bestD=d;best={{p:p,pr:pr}};}}
    }});
    if(best&&bestD<14){{
      tt.textContent=best.p.raw.label; tt.style.display="block";
      var lx=e.clientX-rect.left+12, ly=e.clientY-rect.top-28;
      if(lx+220>W)lx-=234;
      tt.style.left=lx+"px"; tt.style.top=ly+"px";
    }}else{{tt.style.display="none";}}
  }});
  canvas.addEventListener("mouseleave",function(){{tt.style.display="none";}});
}})();"""

    display(HTML(html_part))
    display(Javascript(js_part))


def _daily_return(p_start, p_end, d_start, d_end):
    days = (d_end - d_start).days
    if days <= 0 or p_start == 0:
        return None
    return (p_start - p_end) / days


def _strike_color_fn(s_min, s_max):
    def color(strike):
        t = (strike - s_min) / (s_max - s_min) if s_max > s_min else 0.5
        hue = int(t * 270)
        return f"hsl({hue},80%,42%)"
    return color


def plot_timeline(positions=None, candidates=None, today=None):
    """Render an interactive option price timeline chart in a Jupyter cell.

    Parameters
    ----------
    positions : list of dict, optional
        Open positions. Each dict must have keys:
          ticker (str), expiry (str, "MM/DD/YYYY"), strike (float),
          type (str), price (float), cost_basis (float), open_date (date).
    candidates : list of dict, optional
        Candidate strikes. Each dict must have keys:
          date (date), strike (float), bid (float).
    today : date, optional
        Override today's date (defaults to datetime.date.today()).
    """
    if today is None:
        today = datetime.date.today()

    if positions is None:
        positions = []
    if candidates is None:
        candidates = []

    all_strikes = (
        [r["Strike"] for r in positions]
        + [r["Strike"] for r in candidates]
    )
    if not all_strikes:
        display(HTML("<p>No data to plot.</p>"))
        return

    s_min_all = min(all_strikes)
    s_max_all = max(all_strikes)
    strike_color = _strike_color_fn(s_min_all, s_max_all)

    # ── position series ──────────────────────────────────────────────────────
    position_series = []
    for row in positions:
        expiry = row["Expiry"]
        open_date = row["Open Date"]
        open_price = abs(row["Cost Basis"]) / 100
        cur_price = row["price"]
        r1 = _daily_return(open_price, cur_price, open_date, today)
        r2 = _daily_return(cur_price, 0, today, expiry)
        position_series.append({
            "label": f"{row['Ticker']} {row['Expiry']} ${row['Strike']:.0f}{row['Type']}",
            "color": strike_color(row["Strike"]),
            "points": [
                {"x": open_date.isoformat(), "y": round(open_price, 4),
                 "tip": f"Open date<br>Price: ${open_price:.3f}"},
                {"x": today.isoformat(), "y": round(cur_price, 4),
                 "tip": f"Today<br>Price: ${cur_price:.3f}"
                        + (f"<br>Decay: {r1*100:.2f} $/d (hist)" if r1 else "")
                        + (f"<br>Decay: {r2*100:.2f} $/d (fwd)" if r2 else "")},
                {"x": expiry.isoformat(), "y": 0,
                 "tip": f"Expiry {row['Expiry']}<br>Price: $0.00"},
            ],
        })

    # ── candidate series ─────────────────────────────────────────────────────
    candidate_series = []
    exp_dates = sorted({r["Date"] for r in candidates})
    for exp_date in exp_dates:
        subset = [r for r in candidates if r["Date"] == exp_date]
        for srow in subset:
            gc = strike_color(srow["Strike"])
            r = _daily_return(srow["Bid"], 0, today, exp_date)
            candidate_series.append({
                "label": f"${srow['Strike']:.0f} exp {exp_date}",
                "color": gc,
                "points": [
                    {"x": today.isoformat(), "y": round(srow["Bid"], 4),
                     "tip": f"Strike ${srow['Strike']:.0f} · exp {exp_date}<br>"
                             f"Bid: ${srow['Bid']:.2f}"
                             + (f"<br>Decay: {r*100:.2f} $/d" if r else "")},
                    {"x": exp_date.isoformat(), "y": 0,
                     "tip": f"Expiry {exp_date}<br>Price: $0.00"},
                ],
            })

    all_series_json = json.dumps(position_series)
    cand_series_json = json.dumps(candidate_series)
    today_iso = today.isoformat()

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<style>
  :root {{
    --bg:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
    --grid:#e1e0d9; --base:#c3c2b7;
  }}
  .viz {{ font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
          font-size:13px; background:var(--bg);
          padding:20px 24px 16px; border-radius:8px; width:800px; position:relative; overflow:visible; }}
  .title {{ font-size:15px; font-weight:600; color:var(--ink); margin-bottom:3px; }}
  .sub   {{ font-size:12px; color:var(--ink2); margin-bottom:14px; }}
  .legend {{ display:flex; flex-wrap:wrap; gap:8px 18px; margin-bottom:12px; }}
  .li {{ display:flex; align-items:center; gap:6px; font-size:11px; color:var(--ink2); cursor:pointer; user-select:none; }}
  .li .swatch {{ width:22px; height:2px; border-radius:1px; flex-shrink:0; }}
  .li.dim {{ opacity:.35; }}
  svg text {{ font-family:inherit; }}
  #tt {{ position:absolute; background:var(--bg); border:1px solid var(--grid);
         border-radius:6px; padding:8px 11px; font-size:12px; color:var(--ink);
         pointer-events:none; display:none;
         box-shadow:0 2px 8px rgba(0,0,0,.12); min-width:170px; max-width:240px; line-height:1.6; }}
</style>
</head>
<body>
<div class="viz" id="viz">
  <div class="title">Option Position Price Timeline</div>
  <div class="sub">Open → Today → Expiry &nbsp;|&nbsp; Candidates: Today → Expiry</div>
  <div class="legend" id="legend"></div>
  <svg id="chart" width="740" height="680" style="display:block;overflow:visible;"></svg>
  <div id="tt"></div>
</div>
<script>
const POS   = {all_series_json};
const CANDS = {cand_series_json};
const TODAY = "{today_iso}";

const W=740, H=680, M={{top:10,right:20,bottom:44,left:54}};
const PW=W-M.left-M.right, PH=H-M.top-M.bottom;

const allX = [...POS,...CANDS].flatMap(s=>s.points.map(p=>new Date(p.x)));
const xMin=new Date(Math.min(...allX)), xMax=new Date(Math.max(...allX));
xMin.setDate(xMin.getDate()-2); xMax.setDate(xMax.getDate()+2);

const allY = [...POS,...CANDS].flatMap(s=>s.points.map(p=>p.y));
const yMax = Math.max(...allY)*1.15;

function xs(d){{ return M.left+(new Date(d)-xMin)/(xMax-xMin)*PW; }}
function ys(v){{ return M.top+PH-(v/yMax)*PH; }}

const svg=document.getElementById("chart");
svg.setAttribute("viewBox",`0 0 ${{W}} ${{H}}`);

function el(tag,a={{}},p=null){{
  const e=document.createElementNS("http://www.w3.org/2000/svg",tag);
  for(const[k,v]of Object.entries(a))e.setAttribute(k,v);
  if(p)p.appendChild(e); return e;
}}

const d0=new Date(xMin);
while(d0<=xMax){{
  if(d0.getDay()===6){{
    const sat=new Date(d0); sat.setHours(-12);
    const mon=new Date(d0); mon.setDate(mon.getDate()+2); mon.setHours(-12);
    el("rect",{{x:xs(sat),y:M.top,width:xs(mon)-xs(sat),height:PH,fill:"#f0f0f0",opacity:.7}},svg);
  }}
  d0.setDate(d0.getDate()+1);
}}

for(let i=0;i<=5;i++){{
  const v=yMax*i/5, y=ys(v);
  el("line",{{x1:M.left,x2:M.left+PW,y1:y,y2:y,stroke:i===0?"#c3c2b7":"#e1e0d9","stroke-width":i===0?1.5:1}},svg);
  el("text",{{x:M.left-6,y:y+4,"text-anchor":"end",fill:"#898781","font-size":"11"}},svg).textContent=`$${{v.toFixed(2)}}`;
}}

const cur=new Date(xMin);
while(cur<=xMax){{
  if(cur.getDay()===1){{
    const x=xs(cur);
    el("line",{{x1:x,x2:x,y1:M.top+PH,y2:M.top+PH+5,stroke:"#c3c2b7","stroke-width":1}},svg);
    const t=el("text",{{x,y:M.top+PH+16,"text-anchor":"middle",fill:"#898781","font-size":"11"}},svg);
    t.textContent=(cur.getMonth()+1).toString().padStart(2,"0")+"."
                  +cur.getDate().toString().padStart(2,"0");
  }}
  const x2=xs(cur);
  el("line",{{x1:x2,x2:x2,y1:M.top+PH,y2:M.top+PH+3,stroke:"#cccccc","stroke-width":.8}},svg);
  cur.setDate(cur.getDate()+1);
}}

const tx=xs(TODAY);
el("line",{{x1:tx,x2:tx,y1:M.top,y2:M.top+PH,stroke:"#898781","stroke-width":1,"stroke-dasharray":"4 3"}},svg);
el("text",{{x:tx+4,y:M.top+11,fill:"#898781","font-size":"11"}},svg).textContent="Today";

const yl=el("text",{{x:13,y:M.top+PH/2,transform:`rotate(-90,13,${{M.top+PH/2}})`,
  "text-anchor":"middle",fill:"#52514e","font-size":"12"}},svg);
yl.textContent="Price ($)";

const candEls=[];
CANDS.forEach(s=>{{
  const pts=s.points.map(p=>[xs(p.x),ys(p.y)]);
  const d=pts.map((p,j)=>(j===0?"M":"L")+p[0].toFixed(1)+","+p[1].toFixed(1)).join(" ");
  const path=el("path",{{d,stroke:s.color,"stroke-width":"1",fill:"none",opacity:"1",style:"cursor:pointer"}},svg);
  const hit=el("path",{{d,stroke:"transparent","stroke-width":"8",fill:"none",style:"cursor:pointer"}},svg);
  candEls.push({{s,path,hit}});
  el("circle",{{cx:pts[0][0],cy:pts[0][1],r:"3",fill:s.color,opacity:".6"}},svg);
}});

const posEls=[];
POS.forEach((s,i)=>{{
  const pts=s.points.map(p=>[xs(p.x),ys(p.y)]);
  const segs=[{{pts:[pts[0],pts[1]],color:s.color}},{{pts:[pts[1],pts[2]],color:s.color}}];
  const paths=[];
  segs.forEach(seg=>{{
    const d="M"+seg.pts[0][0].toFixed(1)+","+seg.pts[0][1].toFixed(1)
            +" L"+seg.pts[1][0].toFixed(1)+","+seg.pts[1][1].toFixed(1);
    paths.push(el("path",{{d,stroke:seg.color,"stroke-width":"3.5",fill:"none","stroke-linecap":"round",style:"cursor:pointer"}},svg));
  }});
  const dFull=pts.map((p,j)=>(j===0?"M":"L")+p[0].toFixed(1)+","+p[1].toFixed(1)).join(" ");
  const hit=el("path",{{d:dFull,stroke:"transparent","stroke-width":"10",fill:"none",style:"cursor:pointer"}},svg);
  pts.forEach(p=>{{
    el("circle",{{cx:p[0],cy:p[1],r:"6",fill:"#fcfcfb"}},svg);
    el("circle",{{cx:p[0],cy:p[1],r:"4.5",fill:s.color}},svg);
  }});
  posEls.push({{s,paths,hit}});
}});

const legendEl=document.getElementById("legend");
const hidden=new Set();
POS.forEach((s,i)=>{{
  const item=document.createElement("div"); item.className="li";
  item.innerHTML=`<span class="swatch" style="background:${{s.color}}"></span>${{s.label}}`;
  item.addEventListener("click",()=>{{
    const {{paths}}=posEls[i];
    if(hidden.has("p"+i)){{hidden.delete("p"+i);paths.forEach(p=>p.style.opacity="");item.classList.remove("dim");}}
    else{{hidden.add("p"+i);paths.forEach(p=>p.style.opacity="0");item.classList.add("dim");}}
  }});
  legendEl.appendChild(item);
}});
const seenColors=new Set();
CANDS.forEach((s,i)=>{{
  if(seenColors.has(s.color))return; seenColors.add(s.color);
  const expDate=s.points[1].x;
  const item=document.createElement("div"); item.className="li";
  item.innerHTML=`<span class="swatch" style="background:${{s.color}};height:1px"></span>Candidates ${{expDate}}`;
  item.addEventListener("click",()=>{{
    const key="c"+s.color;
    const isHidden=hidden.has(key);
    if(isHidden)hidden.delete(key); else hidden.add(key);
    item.classList.toggle("dim",!isHidden);
    candEls.filter(e=>e.s.color===s.color).forEach(e=>{{
      e.path.style.opacity=isHidden?"0.55":"0";
    }});
  }});
  legendEl.appendChild(item);
}});

const tt=document.getElementById("tt");
const vizEl=document.getElementById("viz");

function showTip(e,html){{
  tt.innerHTML=html; tt.style.display="block";
  const vr=vizEl.getBoundingClientRect();
  let lx=e.clientX-vr.left+14, ly=e.clientY-vr.top-20;
  if(lx+250>780)lx-=264;
  tt.style.left=lx+"px"; tt.style.top=ly+"px";
}}
function hideTip(){{ tt.style.display="none"; }}

let activePaths=[], activeWidths=[];
function highlightPaths(paths, boldWidth){{
  // restore previous
  activePaths.forEach((p,i)=>p.setAttribute("stroke-width", activeWidths[i]));
  activePaths=[]; activeWidths=[];
  paths.forEach(p=>{{
    activePaths.push(p);
    activeWidths.push(p.getAttribute("stroke-width"));
    p.setAttribute("stroke-width", boldWidth);
  }});
}}
function clearHighlight(){{
  activePaths.forEach((p,i)=>p.setAttribute("stroke-width", activeWidths[i]));
  activePaths=[]; activeWidths=[];
}}

function distToSeg(mx,my,x1,y1,x2,y2){{
  const dx=x2-x1, dy=y2-y1, len2=dx*dx+dy*dy;
  if(len2===0) return {{dist:Math.hypot(mx-x1,my-y1),t:0}};
  const t=Math.max(0,Math.min(1,((mx-x1)*dx+(my-y1)*dy)/len2));
  return {{dist:Math.hypot(mx-x1-t*dx,my-y1-t*dy),t:t}};
}}

function interpTip(s,segIdx,t){{
  const a=s.points[segIdx], b=s.points[segIdx+1];
  return `<b>${{s.label}}</b><hr style="margin:4px 0;border-color:#e1e0d9">${{a.tip}}<hr style="margin:4px 0;border-color:#e1e0d9">${{b.tip}}`;
}}

candEls.forEach(({{s,path,hit}})=>{{
  hit.addEventListener("mousemove",e=>{{
    const r=svg.getBoundingClientRect();
    const mx=(e.clientX-r.left)*W/r.width;
    const my=(e.clientY-r.top)*H/r.height;
    let bestDist=Infinity, bestSeg=0, bestT=0;
    for(let i=0;i<s.points.length-1;i++){{
      const x1=xs(s.points[i].x),   y1=ys(s.points[i].y);
      const x2=xs(s.points[i+1].x), y2=ys(s.points[i+1].y);
      const _r=distToSeg(mx,my,x1,y1,x2,y2),dist=_r.dist,t=_r.t;
      if(dist<bestDist){{bestDist=dist;bestSeg=i;bestT=t;}}
    }}
    if(bestDist>12){{hideTip();clearHighlight();return;}}
    highlightPaths([path], 2.5);
    showTip(e,interpTip(s,bestSeg,bestT));
  }});
  hit.addEventListener("mouseleave",()=>{{hideTip();clearHighlight();}});
}});

posEls.forEach(({{s,paths,hit}})=>{{
  hit.addEventListener("mousemove",e=>{{
    const r=svg.getBoundingClientRect();
    const mx=(e.clientX-r.left)*W/r.width;
    const my=(e.clientY-r.top)*H/r.height;
    let bestDist=Infinity, bestSeg=0, bestT=0;
    for(let i=0;i<s.points.length-1;i++){{
      const x1=xs(s.points[i].x),   y1=ys(s.points[i].y);
      const x2=xs(s.points[i+1].x), y2=ys(s.points[i+1].y);
      const _r=distToSeg(mx,my,x1,y1,x2,y2),dist=_r.dist,t=_r.t;
      if(dist<bestDist){{bestDist=dist;bestSeg=i;bestT=t;}}
    }}
    if(bestDist>12){{hideTip();clearHighlight();return;}}
    highlightPaths(paths, 6);
    showTip(e,interpTip(s,bestSeg,bestT));
  }});
  hit.addEventListener("mouseleave",()=>{{hideTip();clearHighlight();}});
}});
</script>
</body></html>"""

    js_match = re.search(r"<script>(.*?)</script>", html, re.DOTALL)
    js = js_match.group(1) if js_match else ""
    html_only = re.sub(r"<script>.*?</script>", "", html, flags=re.DOTALL)
    display(HTML(html_only))
    display(Javascript(js))
