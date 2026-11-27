"""Build outputs/Dashboard.html: one self-contained interactive page from the same tables
that feed the workbook. Rebuilt by run_all, so figures cannot drift from the analysis.

Filters (vessels, category, period) are applied in the browser to the monthly fact rows,
so every chart and KPI recomputes from source-level data, not from pasted totals.
"""
import json

import pandas as pd

from . import config

VESSEL_LEVEL_COLS = ["Vessel_Name", "Vessel_Type", "Management_Status", "Open_Issues", "Overdue_Issues",
                     "Deferred_Exposure_USD", "Handover_Risk", "Has_Handover_Record",
                     "Overdue_Exceeds_Open"]


def _clean(df: pd.DataFrame) -> list:
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime("%Y-%m")
    out = out.astype(object).where(out.notna(), None)
    return json.loads(out.to_json(orient="records"))


def build_payload(fact, tables, bt, latest, evidence, controls, snapshot) -> dict:
    f = fact.copy()
    f["P"] = f["Period"].dt.strftime("%Y-%m")
    rows = [[r.Vessel_Name.replace("Vessel-", ""), r.P, r.Cost_Category,
             round(r.Budget_USD, 2), round(r.Actual_USD, 2), round(r.NonBudgeted_Spend_USD, 2)]
            for r in f.itertuples()]
    sc = bt["scored"]
    sc = sc[sc["History_Months"] >= config.EW_MIN_HISTORY_MONTHS].copy()
    ew = [[r.Vessel_Name.replace("Vessel-", ""), r.Period.strftime("%Y-%m"), r.Level,
           None if pd.isna(r.Var_Pct_3m) else round(r.Var_Pct_3m, 4),
           round(r.NonBudgeted_3m_USD, 0), r.Reasons or ""] for r in sc.itertuples()]
    ho = tables["handover"].copy()
    ho["Vessel_Name"] = ho["Vessel_Name"].str.replace("Vessel-", "", regex=False)
    cols = ["Vessel_Name", "Management_Status", "Variance_Pct", "Variance_USD", "NonBudgeted_Spend_USD",
            "Cost_Band", "Has_Handover_Record", "Open_Issues", "Overdue_Issues",
            "Overdue_Exceeds_Open", "Deferred_Exposure_USD", "Handover_Risk"]
    metrics = bt["metrics"][["Method", "Period", "Flags", "Precision", "Recall", "False_Alarm_Rate"]]
    fa = bt["fleet_alerts"][["Quarter", "Cost_Category", "Variance_Pct", "Baseline_Pct", "Fleet_Alert"]]
    return {
        "snapshot": f"{snapshot['file']} (modified {snapshot['modified']})" if isinstance(snapshot, dict) else str(snapshot),
        "rows": rows,
        "ew": ew,
        "handover": _clean(ho[cols]),
        "metrics": _clean(metrics),
        "fleet_alerts": _clean(fa),
        "evidence": _clean(evidence[["ID", "Claim", "Figure", "Type", "Confidence", "Caveat"]]),
        "controls": _clean(controls),
        "thresholds": {"watch": config.EW_WATCH_VAR3_PCT, "escalate": config.EW_ESCALATE_VAR3_PCT,
                       "nb": config.EW_NONBUDGET_ESCALATE_USD},
        "partial_year": config.PARTIAL_YEAR,
    }


def build_dashboard(path, payload: dict) -> None:
    html = TEMPLATE.replace("/*__DATA__*/null", json.dumps(payload, separators=(",", ":")))
    path.write_text(html, encoding="utf-8")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vessel Cost Control Dashboard</title>
<style>
:root{--bg:#f9f9f9;--surface:#fff;--ink:#191919;--ink2:#666;--grid:#e7e7e7;--axis:#c2c2c2;
--s1:#257de0;--s2:#f47230;--good:#0aac23;--warn:#fbb315;--serious:#f18a59;--crit:#dc3c3d;--over:#f47230;--under:#257de0;--mid:#efefef}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0b0b0b;--surface:#191919;--ink:#efefef;--ink2:#9c9c9c;--grid:#303030;--axis:#474747;--s1:#338ced;--s2:#e76624;--over:#e76624;--under:#338ced;--mid:#383838}}
:root[data-theme=dark]{--bg:#0b0b0b;--surface:#191919;--ink:#efefef;--ink2:#9c9c9c;--grid:#303030;--axis:#474747;--s1:#338ced;--s2:#e76624;--over:#e76624;--under:#338ced;--mid:#383838}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,Segoe UI,sans-serif}
header{padding:16px;max-width:1200px;margin:0 auto}h1{font-size:20px;margin:0 0 2px}.sub{color:var(--ink2);font-size:12px}
.wrap{max-width:1200px;margin:0 auto;padding:0 16px 40px}
.filters{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;background:var(--surface);border:1px solid var(--grid);border-radius:8px;padding:10px 12px;margin-bottom:12px}
.filters label{font-size:11px;color:var(--ink2);display:flex;flex-direction:column;gap:3px}
select,button,input{font:inherit;color:var(--ink);background:var(--surface);border:1px solid var(--axis);border-radius:6px;padding:4px 8px}
button{cursor:pointer}button.on{background:var(--ink);color:var(--surface)}
.vchips{display:flex;flex-wrap:wrap;gap:4px}.vchips button{padding:2px 7px;font-size:12px}
nav{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:12px}nav button{border-radius:16px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:12px}
.kpi,.card{background:var(--surface);border:1px solid var(--grid);border-radius:8px;padding:12px}
.kpi .l{font-size:11px;color:var(--ink2)}.kpi .v{font-size:22px;font-weight:600}.kpi .n{font-size:11px;color:var(--ink2)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:12px}
@media(max-width:480px){.grid{grid-template-columns:1fr}}
.card h2{font-size:14px;margin:0 0 2px}.card .d{font-size:12px;color:var(--ink2);margin-bottom:6px}
svg{width:100%;height:auto;display:block;overflow:visible}svg text{fill:var(--ink2);font-size:11px}
.tip{position:fixed;pointer-events:none;background:var(--surface);color:var(--ink);border:1px solid var(--axis);border-radius:6px;padding:6px 8px;font-size:12px;box-shadow:0 2px 8px #0003;display:none;z-index:9;max-width:280px}
table{border-collapse:collapse;width:100%;font-size:12px}th,td{text-align:left;padding:5px 6px;border-bottom:1px solid var(--grid);vertical-align:top}th{color:var(--ink2);font-weight:600;position:sticky;top:0;background:var(--surface)}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}.scroll{max-height:460px;overflow:auto}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--ink2);margin:4px 0}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px}
.pill{border-radius:10px;padding:0 7px;font-size:11px;border:1px solid var(--axis)}
.note{font-size:12px;color:var(--ink2);margin:8px 0}.hide{display:none}
</style></head><body>
<header><h1>Vessel cost control dashboard</h1>
<div class="sub" id="sub"></div></header>
<div class="wrap">
<div class="filters" id="filters"></div>
<nav id="tabs"></nav>
<div id="view"></div>
<div class="note">Synthetic data. Every figure is recomputed in the browser from the monthly vessel-category rows, using the current filters. 2026 is a partial year (to July), so compare years on rates, not dollar totals.</div>
</div>
<div class="tip" id="tip"></div>
<script>
const D=/*__DATA__*/null;
const $=s=>document.querySelector(s);
const fmtU=v=>(v<0?"-":"")+"$"+Math.abs(Math.round(v)).toLocaleString("en-US");
const fmtK=v=>{const a=Math.abs(v);return (v<0?"-":"")+"$"+(a>=1e6?(a/1e6).toFixed(2)+"M":a>=1e3?Math.round(a/1e3)+"k":Math.round(a))};
const fmtP=(v,d=1)=>v==null||isNaN(v)?"n/a":(v>0?"+":"")+(v*100).toFixed(d)+"%";
const esc=s=>String(s??"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const VES=[...new Set(D.rows.map(r=>r[0]))].sort(), CATS=[...new Set(D.rows.map(r=>r[2]))].sort();
const MONTHS=[...new Set(D.rows.map(r=>r[1]))].sort();
const st={tab:decodeURIComponent(location.hash.slice(1))||"Overview",ves:new Set(VES),cat:"All",from:MONTHS[0],to:MONTHS.at(-1)};
const TABS=["Overview","Vessels","Categories","Handover","Early warning","Evidence","Controls"];

function sel(){return D.rows.filter(r=>st.ves.has(r[0])&&(st.cat==="All"||r[2]===st.cat)&&r[1]>=st.from&&r[1]<=st.to)}
function agg(rows,keyf){const m=new Map();for(const r of rows){const k=keyf(r);let a=m.get(k);if(!a){a={k,b:0,a:0,nb:0,n:0};m.set(k,a)}a.b+=r[3];a.a+=r[4];a.nb+=r[5];a.n++}
 return [...m.values()].map(a=>({...a,v:a.a-a.b,p:(a.a-a.b)/a.b,gap:(a.a-a.nb)-a.b}))}
const tip=$("#tip");
function showTip(e,html){tip.innerHTML=html;tip.style.display="block";const w=tip.offsetWidth;tip.style.left=Math.min(e.clientX+12,innerWidth-w-8)+"px";tip.style.top=(e.clientY+12)+"px"}
function hideTip(){tip.style.display="none"}
function bind(root){root.querySelectorAll("[data-tip]").forEach(el=>{el.addEventListener("mousemove",e=>showTip(e,el.dataset.tip));el.addEventListener("mouseleave",hideTip);el.addEventListener("focus",e=>{const b=el.getBoundingClientRect();showTip({clientX:b.x,clientY:b.y},el.dataset.tip)});el.addEventListener("blur",hideTip)})}

/* ---------- chart helpers (SVG strings) ---------- */
function barsH(items,{w=520,rowH=24,label=60,fmt=fmtK,color=d=>d.v>=0?css("--over"):css("--under"),tipf}={}){
 const max=Math.max(1,...items.map(d=>Math.abs(d.v))),min=Math.min(0,...items.map(d=>d.v)),maxp=Math.max(0,...items.map(d=>d.v));
 const span=maxp-min||1,pw=w-label-70,x0=label+(-min/span)*pw,h=items.length*rowH+4;
 let s=`<svg viewBox="0 0 ${w} ${h}" role="img">`;
 items.forEach((d,i)=>{const y=i*rowH+2,bw=Math.abs(d.v)/span*pw,x=d.v>=0?x0:x0-bw;
  s+=`<text x="${label-6}" y="${y+rowH/2+3}" text-anchor="end">${esc(d.k)}</text>
  <rect x="${x}" y="${y+3}" width="${Math.max(bw,1)}" height="${rowH-8}" rx="3" fill="${color(d)}" tabindex="0" data-tip="${esc(tipf?tipf(d):d.k+": "+fmt(d.v))}"/>
  <text x="${d.v>=0?x+bw+4:x0+4}" y="${y+rowH/2+3}" text-anchor="start">${fmt(d.v)}</text>`});
 return s+`<line x1="${x0}" x2="${x0}" y1="0" y2="${h}" stroke="${css("--axis")}"/></svg>`}

function lines(series,months,{w=520,h=220,fmt=fmtP,zero=true,refs=[]}={}){
 const L=44,R=10,T=8,B=22,all=series.flatMap(s=>s.pts.filter(v=>v!=null));
 let lo=Math.min(zero?0:Infinity,...all,...refs.map(r=>r.y)),hi=Math.max(...all,...refs.map(r=>r.y),0.001);const pad=(hi-lo)*.08;lo-=pad;hi+=pad;
 const X=i=>L+i*(w-L-R)/Math.max(1,months.length-1),Y=v=>T+(hi-v)/(hi-lo)*(h-T-B);
 let s=`<svg viewBox="0 0 ${w} ${h}" role="img">`;
 for(let k=0;k<=4;k++){const v=lo+(hi-lo)*k/4;s+=`<line x1="${L}" x2="${w-R}" y1="${Y(v)}" y2="${Y(v)}" stroke="${css("--grid")}"/><text x="${L-4}" y="${Y(v)+3}" text-anchor="end">${fmt(v)}</text>`}
 if(lo<0&&hi>0)s+=`<line x1="${L}" x2="${w-R}" y1="${Y(0)}" y2="${Y(0)}" stroke="${css("--axis")}"/>`;
 refs.forEach(r=>s+=`<line x1="${L}" x2="${w-R}" y1="${Y(r.y)}" y2="${Y(r.y)}" stroke="${css("--ink2")}" stroke-dasharray="4 3"/><text x="${w-R}" y="${Y(r.y)-3}" text-anchor="end">${r.label}</text>`);
 const step=Math.ceil(months.length/8);months.forEach((m,i)=>{if(i%step===0)s+=`<text x="${X(i)}" y="${h-6}" text-anchor="middle">${m.slice(2)}</text>`});
 series.forEach(se=>{let d="",pen=false;se.pts.forEach((v,i)=>{if(v==null){pen=false;return}d+=(pen?"L":"M")+X(i).toFixed(1)+" "+Y(v).toFixed(1);pen=true});
  s+=`<path d="${d}" fill="none" stroke="${se.color}" stroke-width="2" stroke-linejoin="round"/>`});
 s+=`<rect id="hit" x="${L}" y="${T}" width="${w-L-R}" height="${h-T-B}" fill="transparent"/><line id="cross" y1="${T}" y2="${h-B}" stroke="${css("--axis")}" style="display:none"/></svg>`;
 return {svg:s,months,series,fmt,X,L,R,w}}
function hookLines(root,c){const svg=root.querySelector("svg:last-of-type"),hit=svg.querySelector("#hit"),cr=svg.querySelector("#cross");
 hit.addEventListener("mousemove",e=>{const b=svg.getBoundingClientRect(),sx=c.w/b.width,x=(e.clientX-b.left)*sx;
  let i=Math.round((x-c.L)/((c.w-c.L-c.R)/Math.max(1,c.months.length-1)));i=Math.max(0,Math.min(c.months.length-1,i));
  cr.setAttribute("x1",c.X(i));cr.setAttribute("x2",c.X(i));cr.style.display="";
  showTip(e,`<b>${c.months[i]}</b>`+c.series.map(s=>`<br><span style="color:${s.color}">&#9632;</span> ${esc(s.name)}: ${s.pts[i]==null?"n/a":c.fmt(s.pts[i])}`).join(""))});
 hit.addEventListener("mouseleave",()=>{cr.style.display="none";hideTip()})}
function legend(items){return `<div class="legend">`+items.map(([c,t])=>`<span><i style="background:${c}"></i>${t}</span>`).join("")+`</div>`}

/* diverging colour for rates: under = blue, over = orange, grey mid */
function divColor(p,cap=0.12){const t=Math.max(-1,Math.min(1,p/cap)),mid=css("--mid");
 const base=t>=0?css("--over"):css("--under");return `color-mix(in srgb, ${base} ${Math.round(Math.abs(t)*100)}%, ${mid})`}

/* ---------- views ---------- */
function vOverview(){
 const rows=sel(),tot=agg(rows,()=>1)[0]||{b:0,a:0,nb:0,v:0,p:0,gap:0};
 const months=MONTHS.filter(m=>m>=st.from&&m<=st.to);
 const byM=new Map(agg(rows,r=>r[1]).map(a=>[a.k,a])),nM=months.length||1;
 const years=agg(rows,r=>r[1].slice(0,4)).sort((a,b)=>a.k<b.k?-1:1);
 const nbV=agg(rows,r=>r[0]).filter(a=>a.nb>0).length;
 const k=(l,v,n)=>`<div class="kpi"><div class="l">${l}</div><div class="v">${v}</div><div class="n">${n||""}</div></div>`;
 let h=`<div class="kpis">`+k("Budget",fmtK(tot.b),nM+" months")+k("Actual",fmtK(tot.a))+k("Variance",fmtK(tot.v),fmtP(tot.p))
  +k("Non-budgeted spend",fmtK(tot.nb),nbV+" vessels with any")+k("Budgeted lines vs budget",fmtK(tot.gap),"variance = non-budgeted + this")
  +k("Variance per month",fmtK(tot.v/nM),"pace, comparable across years")+`</div><div class="grid">`;
 const bridge=years.map(y=>{const m=MONTHS.filter(x=>x.startsWith(y.k)&&x>=st.from&&x<=st.to).length;return {k:y.k+(+y.k===D.partial_year?" ("+m+"m)":""),v:y.v,tipf:()=>`<b>${y.k}</b> (${m} months)<br>Variance ${fmtU(y.v)} (${fmtP(y.p)})<br>Non-budgeted ${fmtU(y.nb)}<br>Budgeted lines ${fmtU(y.gap)}<br>Per month ${fmtU(y.v/m)}`}});
 const nbBars=years.map(y=>({k:y.k,v:y.nb,tipf:()=>`<b>${y.k}</b><br>Non-budgeted ${fmtU(y.nb)}`}));
 h+=`<div class="card"><h2>Variance by year</h2><div class="d">Dollar totals. 2026 has fewer months.</div>${barsH(bridge,{})}</div>`;
 h+=`<div class="card"><h2>Non-budgeted spend by year</h2><div class="d">Larger than the variance in every year.</div>${barsH(nbBars,{color:()=>css("--s1")})}</div>`;
 const pts=months.map(m=>byM.get(m)?.p??null),nb=months.map(m=>byM.get(m)?(byM.get(m).nb/byM.get(m).b):null);
 const c=lines([{name:"Variance %",color:css("--over"),pts},{name:"Non-budgeted % of budget",color:css("--s1"),pts:nb}],months,{});
 h+=`<div class="card" id="c-line"><h2>Monthly variance rate</h2><div class="d">Variance and non-budgeted spend as a share of budget.</div>${legend([[css("--over"),"Variance %"],[css("--s1"),"Non-budgeted % of budget"]])}${c.svg}</div></div>`;
 $("#view").innerHTML=h;bind($("#view"));hookLines($("#c-line"),c)}

function vVessels(){
 const rows=sel(),a=agg(rows,r=>r[0]).sort((x,y)=>y.v-x.v);
 let h=`<div class="grid"><div class="card"><h2>Variance by vessel</h2><div class="d">Net of non-budgeted spend and budgeted-line result. Hover for the split.</div>${barsH(a.map(d=>({...d,tipf:d=>`<b>${d.k}</b><br>Variance ${fmtU(d.v)} (${fmtP(d.p)})<br>Non-budgeted ${fmtU(d.nb)}<br>Budgeted lines ${fmtU(d.gap)}`})),{rowH:26})}</div>`;
 const b=[...a].sort((x,y)=>y.nb-x.nb).map(d=>({k:d.k,v:d.nb,tipf:()=>`<b>${d.k}</b><br>Non-budgeted ${fmtU(d.nb)}<br>Budgeted lines vs budget ${fmtU(d.gap)}`}));
 h+=`<div class="card"><h2>Non-budgeted spend by vessel</h2><div class="d">Only five vessels have any.</div>${barsH(b,{rowH:26,color:()=>css("--s1")})}</div></div>`;
 // heatmap vessel x year
 const ys=[...new Set(rows.map(r=>r[1].slice(0,4)))].sort(),vs=a.map(d=>d.k);
 const cell=new Map(agg(rows,r=>r[0]+"|"+r[1].slice(0,4)).map(x=>[x.k,x]));
 const cw=70,ch=24,L=50,w=L+ys.length*cw+10,hh=vs.length*ch+24;
 let s=`<svg viewBox="0 0 ${w} ${hh}" role="img" style="max-width:${w*1.6}px">`;ys.forEach((y,j)=>s+=`<text x="${L+j*cw+cw/2}" y="12" text-anchor="middle">${y}</text>`);
 vs.forEach((v,i)=>{s+=`<text x="${L-6}" y="${24+i*ch+ch/2+3}" text-anchor="end">${v}</text>`;
  ys.forEach((y,j)=>{const c=cell.get(v+"|"+y);if(!c)return;const t=c.p;
   s+=`<rect x="${L+j*cw+1}" y="${24+i*ch+1}" width="${cw-2}" height="${ch-2}" rx="3" fill="${divColor(t)}" tabindex="0" data-tip="<b>${v} ${y}</b><br>${fmtP(t)} (${fmtU(c.v)})<br>Non-budgeted ${fmtU(c.nb)}"/><text x="${L+j*cw+cw/2}" y="${24+i*ch+ch/2+3}" text-anchor="middle" style="fill:var(--ink)">${fmtP(t)}</text>`})});
 h+=`<div class="card" style="margin-top:12px"><h2>Variance rate by vessel and year</h2><div class="d">Orange is over budget, blue is under, grey is near zero. Colour scale caps at 12%.</div>${s}</svg></div>`;
 $("#view").innerHTML=h;bind($("#view"))}

function vCategories(){
 const rows=D.rows.filter(r=>st.ves.has(r[0])&&r[1]>=st.from&&r[1]<=st.to);
 const a=agg(rows,r=>r[2]).sort((x,y)=>y.v-x.v);
 const qk=m=>m.slice(0,4)+"Q"+Math.ceil(+m.slice(5)/3);
 const q=agg(rows.filter(r=>["Repairs & Maintenance","Safety & Compliance"].includes(r[2])),r=>r[2]+"|"+qk(r[1]));
 const qs=[...new Set(q.map(x=>x.k.split("|")[1]))].sort(),get=(c,k)=>q.find(x=>x.k===c+"|"+k);
 const mk=c=>qs.map(k=>get(c,k)?.p??null);
 const base24=c=>{const x=agg(rows.filter(r=>r[2]===c&&r[1].startsWith("2024")),()=>1)[0];return x?x.p:null};
 const ch=lines([{name:"Repairs & Maintenance",color:css("--s1"),pts:mk("Repairs & Maintenance")},{name:"Safety & Compliance",color:css("--s2"),pts:mk("Safety & Compliance")}],qs,{});
 let h=`<div class="grid"><div class="card"><h2>Variance by category</h2><div class="d">Crew wages nets to zero because non-budgeted wages offset budgeted underspend. Hover for the split.</div>${barsH(a.map(d=>({...d,tipf:d=>`<b>${d.k}</b><br>Variance ${fmtU(d.v)} (${fmtP(d.p)})<br>Non-budgeted ${fmtU(d.nb)}<br>Budgeted lines ${fmtU(d.gap)}`})),{rowH:26,label:130,w:600})}</div>`;
 h+=`<div class="card" id="c-q"><h2>Repairs and safety, quarterly rate</h2><div class="d">Both ran above their 2024 rates (repairs ${fmtP(base24("Repairs & Maintenance"))}, safety ${fmtP(base24("Safety & Compliance"))}). The last quarter may be a single month.</div>${legend([[css("--s1"),"Repairs & Maintenance"],[css("--s2"),"Safety & Compliance"]])}${ch.svg}</div></div>`;
 const fa=D.fleet_alerts.filter(r=>r.Fleet_Alert!=="Baseline year");
 h+=`<div class="card" style="margin-top:12px"><h2>Fleet alert (full fleet, not filtered)</h2><div class="d">Alert when a quarter is more than 2 points above the 2024 rate.</div><div class="scroll"><table><tr><th>Quarter</th><th>Category</th><th class="n">Rate</th><th class="n">2024 rate</th><th>Status</th></tr>${fa.map(r=>`<tr><td>${r.Quarter}</td><td>${r.Cost_Category}</td><td class="n">${fmtP(r.Variance_Pct)}</td><td class="n">${fmtP(r.Baseline_Pct)}</td><td>${r.Fleet_Alert==="Alert"?"&#9650; Alert":"&#10003; OK"}</td></tr>`).join("")}</table></div></div>`;
 $("#view").innerHTML=h;bind($("#view"));hookLines($("#c-q"),ch)}

function vHandover(){
 const H=D.handover.filter(r=>st.ves.has(r.Vessel_Name)),rec=H.filter(r=>r.Has_Handover_Record);
 const w=520,h=320,L=50,R=20,T=10,B=34,xs=H.map(r=>r.Variance_Pct),xmax=Math.max(0.1,...xs),xmin=Math.min(-0.02,...xs),ymax=Math.max(...rec.map(r=>r.Deferred_Exposure_USD),1)*1.1;
 const X=v=>L+(v-xmin)/(xmax-xmin)*(w-L-R),Y=v=>T+(1-v/ymax)*(h-T-B);
 let s=`<svg viewBox="0 0 ${w} ${h}" role="img"><line x1="${L}" x2="${w-R}" y1="${h-B}" y2="${h-B}" stroke="${css("--axis")}"/><line x1="${X(0)}" x2="${X(0)}" y1="${T}" y2="${h-B}" stroke="${css("--axis")}"/>
 <line x1="${L}" x2="${w-R}" y1="${Y(120000)}" y2="${Y(120000)}" stroke="${css("--grid")}" stroke-dasharray="4 3"/><text x="${L+2}" y="${Y(120000)-3}">$120k material</text>
 <text x="${(L+w-R)/2}" y="${h-2}" text-anchor="middle">Cost variance % (whole history)</text><text transform="translate(12 ${(T+h-B)/2}) rotate(-90)" text-anchor="middle">Deferred exposure</text>`;
 rec.forEach(r=>{s+=`<circle cx="${X(r.Variance_Pct)}" cy="${Y(r.Deferred_Exposure_USD)}" r="7" fill="${r.Variance_Pct>=0.04?css("--over"):r.Variance_Pct>=0.02?css("--warn"):css("--s1")}" stroke="${css("--surface")}" stroke-width="2" tabindex="0" data-tip="<b>${r.Vessel_Name}</b> (${r.Management_Status})<br>Cost ${fmtP(r.Variance_Pct)}<br>Deferred ${fmtU(r.Deferred_Exposure_USD)}<br>Risk label: ${r.Handover_Risk}"/><text x="${X(r.Variance_Pct)+10}" y="${Y(r.Deferred_Exposure_USD)+4}">${r.Vessel_Name}</text>`});
 for(let k=0;k<=4;k++){const v=xmin+(xmax-xmin)*k/4;s+=`<text x="${X(v)}" y="${h-B+14}" text-anchor="middle">${fmtP(v,0)}</text>`;const yv=ymax*k/4;s+=`<text x="${L-4}" y="${Y(yv)+3}" text-anchor="end">${fmtK(yv)}</text>`}
 s+="</svg>";
 const rowsT=H.map(r=>`<tr><td>${r.Vessel_Name}</td><td>${r.Management_Status}</td><td class="n">${fmtP(r.Variance_Pct)}</td><td class="n">${fmtK(r.NonBudgeted_Spend_USD)}</td><td>${r.Has_Handover_Record?r.Handover_Risk:"<span class=pill>no record</span>"}</td><td class="n">${r.Has_Handover_Record?fmtK(r.Deferred_Exposure_USD):"unknown"}</td><td class="n">${r.Has_Handover_Record?r.Open_Issues+" / "+r.Overdue_Issues+(r.Overdue_Exceeds_Open?" &#9888;":""):"unknown"}</td></tr>`).join("");
 $("#view").innerHTML=`<div class="grid"><div class="card"><h2>Cost performance against deferred exposure</h2><div class="d">Cost variance here is the whole-history figure for the vessel, not filtered by period. Colour: cost band (orange 4%+, yellow 2-4%, blue under 2%). Vessels with no handover record are not plotted.</div>${s}</div>
 <div class="card"><h2>Handover table</h2><div class="d">&#9888; = overdue issues exceed open issues (K56), so its counts are unreliable. Missing record means unknown, not low risk. Deferred exposure has no method or as-of date.</div><div class="scroll"><table><tr><th>Vessel</th><th>Status</th><th class="n">Cost</th><th class="n">Non-budg.</th><th>Risk label</th><th class="n">Deferred</th><th class="n">Open / overdue</th></tr>${rowsT}</table></div></div></div>`;bind($("#view"))}

function vEarly(){
 const E=D.ew.filter(r=>st.ves.has(r[0])&&r[1]>=st.from&&r[1]<=st.to),ms=[...new Set(E.map(r=>r[1]))].sort(),vs=VES.filter(v=>st.ves.has(v));
 const cw=22,ch=22,L=40,w=L+ms.length*cw+6,h=vs.length*ch+28,map=new Map(E.map(r=>[r[0]+"|"+r[1],r]));
 const col={Escalate:css("--over"),Watch:css("--warn"),None:css("--mid")};
 let s=`<svg viewBox="0 0 ${w} ${h}" role="img" style="max-width:${w*1.8}px">`;ms.forEach((m,j)=>{if(j%3===0)s+=`<text x="${L+j*cw}" y="12">${m.slice(2)}</text>`});
 vs.forEach((v,i)=>{s+=`<text x="${L-6}" y="${28+i*ch+ch/2+3}" text-anchor="end">${v}</text>`;ms.forEach((m,j)=>{const r=map.get(v+"|"+m);if(!r)return;
  s+=`<rect x="${L+j*cw+1}" y="${28+i*ch+1}" width="${cw-2}" height="${ch-2}" rx="3" fill="${col[r[2]]||col.None}" tabindex="0" data-tip="<b>${v} ${m}</b><br>${r[2]}<br>3-month variance ${fmtP(r[3])}<br>Non-budgeted (3m) ${fmtU(r[4])}<br>${esc(r[5])}"/>`})});
 s+="</svg>";
 const perM=ms.map(m=>({m,e:E.filter(r=>r[1]===m&&r[2]==="Escalate").length,w:E.filter(r=>r[1]===m&&r[2]==="Watch").length}));
 const avgE=(perM.reduce((a,b)=>a+b.e,0)/(perM.length||1)).toFixed(1);
 const last=ms.at(-1),now=E.filter(r=>r[1]===last&&r[2]!=="None").sort((a,b)=>(a[2]==="Escalate"?0:1)-(b[2]==="Escalate"?0:1));
 const M=D.metrics.filter(r=>["All evaluated months","2026 (Jan-Apr)"].includes(r.Period)&&!/variance-only/.test(r.Method));
 const pc=v=>v==null?"n/a":Math.round(v*100)+"%";
 $("#view").innerHTML=`<div class="grid"><div class="card" style="grid-column:1/-1"><h2>Escalation timeline</h2><div class="d">Level per vessel and month, using only data up to that month. Average ${avgE} vessels escalated per month. First scored month is June 2024 (six months of history).</div>${legend([[col.Escalate,"Escalate"],[col.Watch,"Watch"],[col.None,"None"]])}${s}</div>
 <div class="card"><h2>Latest month (${last||"n/a"})</h2><div class="d">Escalate: 3-month variance above ${D.thresholds.escalate*100}% or more than ${fmtU(D.thresholds.nb)} non-budgeted in 3 months.</div><table><tr><th>Vessel</th><th>Level</th><th>Why</th></tr>${now.map(r=>`<tr><td>${r[0]}</td><td>${r[2]==="Escalate"?"&#9650; Escalate":"&#9679; Watch"}</td><td>${esc(r[5])}</td></tr>`).join("")||"<tr><td colspan=3>No flags</td></tr>"}</table></div>
 <div class="card"><h2>Backtest</h2><div class="d">Precision: share of flags right. Recall: share of bad outcomes caught. Small test: 56 vessel-months, mostly five persistent vessels, so differences are within chance. Not filtered.</div><div class="scroll"><table><tr><th>Method</th><th>Period</th><th class="n">Flags</th><th class="n">Prec.</th><th class="n">Recall</th><th class="n">False alarm</th></tr>${M.map(r=>`<tr><td>${esc(r.Method)}</td><td>${r.Period}</td><td class="n">${r.Flags}</td><td class="n">${pc(r.Precision)}</td><td class="n">${pc(r.Recall)}</td><td class="n">${pc(r.False_Alarm_Rate)}</td></tr>`).join("")}</table></div></div></div>`;bind($("#view"))}

function vTable(rows,cols,title,desc,filterKey){
 $("#view").innerHTML=`<div class="card"><h2>${title}</h2><div class="d">${desc}</div><input id="q" placeholder="Search" style="margin-bottom:8px;width:240px"><div class="scroll"><table id="t"></table></div></div>`;
 const draw=q=>{$("#t").innerHTML="<tr>"+cols.map(c=>`<th>${c.replace(/_/g," ")}</th>`).join("")+"</tr>"+rows.filter(r=>!q||JSON.stringify(r).toLowerCase().includes(q)).map(r=>"<tr>"+cols.map(c=>`<td>${esc(r[c])}</td>`).join("")+"</tr>").join("")};
 draw("");$("#q").oninput=e=>draw(e.target.value.toLowerCase())}

const VIEWS={"Overview":vOverview,"Vessels":vVessels,"Categories":vCategories,"Handover":vHandover,"Early warning":vEarly,
 "Evidence":()=>vTable(D.evidence,["ID","Claim","Figure","Type","Confidence","Caveat"],"Evidence register","Each claim is a fact, an interpretation or open. Not filtered."),
 "Controls":()=>vTable(D.controls,["ID","Decision_Type","Control","Trigger","Frequency","Owner_Function","Evidence","Data_Needed"],"Control register","Continue, change, monitor or new control. Each points to evidence. Not filtered.")};

/* ---------- chrome ---------- */
function drawFilters(){
 const f=$("#filters");
 f.innerHTML=`<label>Vessels<div class="vchips" id="vc"></div></label>
 <label>Category<select id="cat"><option>All</option>${CATS.map(c=>`<option>${c}</option>`).join("")}</select></label>
 <label>From<select id="from">${MONTHS.map(m=>`<option>${m}</option>`).join("")}</select></label>
 <label>To<select id="to">${MONTHS.map(m=>`<option>${m}</option>`).join("")}</select></label>
 <label>Preset<span><button data-p="all">All</button> <button data-p="2024">2024</button> <button data-p="2025">2025</button> <button data-p="2026">2026</button></span></label>
 <label>Theme<button id="th">Light/dark</button></label>`;
 const vc=$("#vc");vc.innerHTML=`<button data-v="*">All</button><button data-v="!">Focus five</button>`+VES.map(v=>`<button data-v="${v}">${v}</button>`).join("");
 const FOCUS=new Set(D.ew.filter(r=>r[2]==="Escalate").map(r=>r[0]).filter((v,i,a)=>a.indexOf(v)===i).filter(v=>D.rows.some(r=>r[0]===v&&r[5]>0)));
 vc.onclick=e=>{const v=e.target.dataset.v;if(!v)return;if(v==="*")st.ves=new Set(VES);else if(v==="!")st.ves=new Set([...FOCUS]);else{st.ves.has(v)?st.ves.delete(v):st.ves.add(v);if(!st.ves.size)st.ves=new Set(VES)}render()};
 $("#cat").onchange=e=>{st.cat=e.target.value;render()};
 $("#from").onchange=e=>{st.from=e.target.value;if(st.from>st.to)st.to=st.from;render()};
 $("#to").onchange=e=>{st.to=e.target.value;if(st.to<st.from)st.from=st.to;render()};
 f.querySelector("[data-p]").parentElement.onclick=e=>{const p=e.target.dataset.p;if(!p)return;if(p==="all"){st.from=MONTHS[0];st.to=MONTHS.at(-1)}else{const m=MONTHS.filter(x=>x.startsWith(p));st.from=m[0];st.to=m.at(-1)}render()};
 $("#th").onclick=()=>{const r=document.documentElement,d=r.dataset.theme==="dark"||(!r.dataset.theme&&matchMedia("(prefers-color-scheme:dark)").matches);r.dataset.theme=d?"light":"dark";render()};
}
function render(){
 $("#cat").value=st.cat;$("#from").value=st.from;$("#to").value=st.to;
 document.querySelectorAll("#vc button").forEach(b=>b.classList.toggle("on",b.dataset.v!=="*"&&b.dataset.v!=="!"&&st.ves.has(b.dataset.v)));
 $("#tabs").innerHTML=TABS.map(t=>`<button class="${t===st.tab?"on":""}" data-t="${t}">${t}</button>`).join("");
 $("#tabs").onclick=e=>{if(e.target.dataset.t){st.tab=e.target.dataset.t;render()}};
 $("#sub").textContent=`${st.ves.size} of ${VES.length} vessels · ${st.cat} · ${st.from} to ${st.to} · source snapshot: ${D.snapshot}`;
 hideTip();VIEWS[st.tab]()}
drawFilters();render();
</script></body></html>
"""
