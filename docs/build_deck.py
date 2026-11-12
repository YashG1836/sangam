"""Pitch deck (16:9) -> site/Sangam_Pitch_Deck.pdf. Numbers come from results/summary.json."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs"))
from build_docs import N, T, SW, TEAM, CHROME, FONT, p, fmt_up, drop_txt, fall_txt, top_gainers  # noqa: E402

DOCS, SITE = ROOT / "docs", ROOT / "site"
fig = lambda n: f"../site/figures/{n}.png"
k = TEAM["members"][1]
kinst = k["institution"] if k["institution"] != "TO_FILL" else ""
sweep_mid = next((r for r in SW if r["scenario"] == "none" and r["fair_max"] == 4.0), None)

CSS = """
@page { size: 1280px 720px; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: Inter, sans-serif; color: #0f1115; }
.s { width: 1280px; height: 720px; padding: 64px 72px; position: relative; overflow: hidden; page-break-after: always; background: #fbfaf7; }
.s.dark { background: #0f1a2b; color: #f0efec; }
.kick { font-size: 15px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: #2a78d6; margin-bottom: 14px; }
.dark .kick { color: #86b6ef; }
h1 { font-size: 56px; line-height: 1.05; letter-spacing: -.025em; margin: 0 0 20px; }
h2 { font-size: 38px; line-height: 1.12; letter-spacing: -.02em; margin: 0 0 26px; max-width: 1000px; }
p.lede { font-size: 22px; line-height: 1.45; color: #4a4b50; max-width: 940px; margin: 0; }
.dark p.lede { color: #c3c2b7; }
.foot { position: absolute; bottom: 26px; left: 72px; right: 72px; display: flex; justify-content: space-between; font-size: 13px; color: #7a7b80; }
.dark .foot { color: #8f8e86; }
.row { display: grid; gap: 22px; }
.c3 { grid-template-columns: repeat(3, 1fr); } .c4 { grid-template-columns: repeat(4, 1fr); } .c2 { grid-template-columns: 1fr 1fr; }
.card { background: #fff; border: 1px solid #e4e3df; border-radius: 18px; padding: 26px; }
.dark .card { background: #172539; border-color: #24364f; }
.big { font-size: 46px; font-weight: 700; letter-spacing: -.02em; line-height: 1.05; margin-bottom: 10px; }
.card h3 { font-size: 20px; margin: 0 0 8px; }
.card p { font-size: 16px; line-height: 1.45; color: #4a4b50; margin: 0; }
.dark .card p { color: #c3c2b7; }
.src { font-size: 12px; color: #7a7b80; margin-top: 12px; }
.blue { color: #2a78d6; } .dark .blue { color: #86b6ef; } .orange { color: #eb6834; }
img.fig { width: 100%; border-radius: 12px; border: 1px solid #e4e3df; background: #fff; }
.take { font-size: 20px; line-height: 1.45; }
.take b { color: #1c5cab; }
.flow { display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; margin-top: 10px; }
.flow .card { position: relative; }
.flow .n { width: 34px; height: 34px; border-radius: 50%; background: #e6f0fc; color: #1c5cab; display: grid; place-items: center; font-weight: 700; margin-bottom: 14px; }
.flow .card:not(:last-child)::after { content: "→"; position: absolute; right: -16px; top: 42%; font-size: 22px; color: #a3a29c; }
table { border-collapse: collapse; width: 100%; font-size: 16px; }
th, td { padding: 11px 12px; border-bottom: 1px solid #e4e3df; text-align: center; }
th { font-size: 13px; text-transform: uppercase; letter-spacing: .04em; color: #7a7b80; font-weight: 600; }
td:first-child, th:first-child { text-align: left; }
tr.ours td { background: #e6f0fc; font-weight: 700; }
.y { color: #0c8a0c; font-weight: 700; } .n { color: #c9c8c2; }
.pill { display: inline-block; padding: 4px 12px; border-radius: 99px; background: #e6f0fc; color: #1c5cab; font-weight: 600; font-size: 14px; margin-right: 8px; }
.wave { position: absolute; right: -60px; top: 40px; opacity: .9; }
"""

WAVE = '<svg class="wave" width="520" height="520" viewBox="0 0 24 24" fill="none"><path d="M3 6c4 0 5 6 9 6s5-6 9-6M3 18c4 0 5-6 9-6s5 6 9 6" stroke="#2a78d6" stroke-width="1.1" stroke-linecap="round" opacity=".55"/></svg>'


def foot(n):
    return f'<div class="foot"><span>Sangam · GIFT FutureLab Grand Challenge 2026–27</span><span>{n}</span></div>'


def Y(b):
    return '<span class="y">✓</span>' if b else '<span class="n">—</span>'


slides = []
slides.append(f"""<div class="s dark">{WAVE}
<div class="kick" style="margin-top:90px">GIFT FutureLab Grand Challenge 2026–27</div>
<h1 style="font-size:84px">Sangam</h1>
<p class="lede" style="font-size:28px;max-width:760px">Banks stop mule accounts together, without sharing a single customer record. Federated, fair to senior citizens, and resilient to compromised participants.</p>
<p class="lede" style="margin-top:56px;font-size:19px">Yash Goyal (IIT Gandhinagar) · {k['name']}{(' (' + kinst + ')') if kinst else ''}</p>
<div class="foot"><span>Cybersecurity, fraud prevention &amp; risk management</span><span>1</span></div></div>""")

slides.append(f"""<div class="s"><div class="kick">The problem</div>
<h2>Mule accounts are the plumbing of digital fraud, and they are opened one bank at a time.</h2>
<div class="row c3">
<div class="card"><div class="big">₹36,014 cr</div><h3>involved in bank frauds, FY 2024-25</h3><p>The amount tripled even as the number of cases fell.</p><div class="src">RBI Annual Report 2024-25</div></div>
<div class="card"><div class="big">~20,000</div><h3>mule accounts flagged per month</h3><p>by RBIH's MuleHunter.AI. AI works, but each bank still learns only from its own customers.</p><div class="src">RBI Governor, Nov 2025</div></div>
<div class="card"><div class="big orange">{N['fed_mult']:.1f}×</div><h3>more genuine seniors wrongly flagged</h3><p>by a standard fraud model on the public BAF benchmark ({p(N['fed_fs'])} vs {p(N['fed_fn'])}).</p><div class="src">Our measurement, BAF (NeurIPS 2022)</div></div>
</div>{foot(2)}</div>""")

slides.append(f"""<div class="s"><div class="kick">Why today's approach falls short</div>
<h2>Four walls stand between banks and a shared defence.</h2>
<div class="row c4">
<div class="card"><h3>Silos</h3><p>A fraud ring opens accounts across many banks. Each bank sees one slice of the pattern.</p></div>
<div class="card"><h3>Privacy law</h3><p>The DPDP Rules 2025 and banking secrecy rightly prevent pooling customer data.</p></div>
<div class="card"><h3>Untrusted peers</h3><p>In a shared model, one compromised member can poison everyone's defence.</p></div>
<div class="card"><h3>Blunt models</h3><p>Base-rate-driven models over-flag genuine senior citizens, which works against financial inclusion.</p></div>
</div>
<p class="lede" style="margin-top:40px">Federated learning solves the first two. <b>Sangam solves all four.</b></p>{foot(3)}</div>""")

slides.append(f"""<div class="s"><div class="kick">Sangam (संगम): the confluence</div>
<h2>One shared fraud model. No shared data. Two safeguards that make it deployable.</h2>
<div class="row c3">
<div class="card"><div class="big blue">{fmt_up(N['up_sg'])}</div><h3>more fraud caught</h3><p>than banks working alone ({p(N['loc'])} → {p(N['sg'])} at a 5% false-alarm budget). Every bank improves.</p></div>
<div class="card"><div class="big blue">{p(N['fed_fs'])} → {p(N['sg_fs'])}</div><h3>genuine seniors wrongly flagged</h3><p>Standard federated model vs Sangam. Fairness ratio {N['fed_ratio']:.2f} → {N['sg_ratio']:.2f}.</p></div>
<div class="card"><div class="big blue">4 of 7</div><h3>banks compromised, still {p(N['maj_sg'], 0)}</h3><p>fraud caught. FedAvg, Median, Trimmed-Mean and Krum catch {fall_txt(N['maj_best_dist'])}.</p></div>
</div>
<p class="lede" style="margin-top:34px;font-size:18px">Benchmark: 1,000,000 bank-account-opening applications (BAF, NeurIPS 2022) · 7 simulated banks · 12 methods · 7 attack scenarios · 3 seeds.</p>{foot(4)}</div>""")

slides.append(f"""<div class="s"><div class="kick">How it works</div>
<h2>A federated round, plus a trust check and a fairness controller.</h2>
<div class="flow">
<div class="card"><div class="n">1</div><h3>Train at each bank</h3><p>Every bank trains the shared model on its own account-opening data. Only weight updates leave the bank.</p></div>
<div class="card"><div class="n">2</div><h3>Segment-level trust</h3><p>The operator test-applies each update to a small reference set and checks every customer segment <b>separately</b>. Any update that harms a segment gets zero weight.</p></div>
<div class="card"><div class="n">3</div><h3>Fairness controller</h3><p>The operator measures false alarms for ages 50+ vs under 50 and re-weights training to equalise them. This extends our DCA-FW research.</p></div>
<div class="card"><div class="n">4</div><h3>Audit trail</h3><p>Each round logs every bank's trust score and the fairness gap, ready for supervisors and for fair cost sharing.</p></div>
</div>
<p class="lede" style="margin-top:34px;font-size:18px"><b>Key design insight:</b> trust comes from a neutral reference set, checked segment by segment, not from agreement between banks. That is why Sangam survives a compromised majority <i>and</i> catches poison aimed at one customer group.</p>{foot(5)}</div>""")

slides.append(f"""<div class="s"><div class="kick">Live demo</div>
<h2 style="margin-bottom:18px">The consortium simulator: pick an attack and a defence, then watch 30 rounds.</h2>
<img class="fig" src="sim.png" style="height:470px;width:auto;max-width:100%;display:block">
{foot(6)}</div>""")

slides.append(f"""<div class="s"><div class="kick">Result 1 · Collaboration</div>
<h2>Every bank catches more fraud inside the consortium.</h2>
<div class="row" style="grid-template-columns:1.45fr 1fr;align-items:center">
<img class="fig" src="{fig('bank_uplift')}">
<div class="take">Federated training matches pooling all data centrally ({p(N['fed'])} vs {p(N['cen'])}), <b>without moving a single record</b>.<br><br>Every bank gains, by <b>+{100*N['bank_up_min']:.0f} to +{100*N['bank_up_max']:.0f} points</b>. The largest gains go to {top_gainers()}.</div>
</div>{foot(7)}</div>""")

trade = (f"<br><br>The operator tunes this: at λ<sub>max</sub> = 4, false alarms are near-equal (ratio {sweep_mid['fpr_ratio'][0]:.2f}) with {p(sweep_mid['tpr'][0])} fraud caught." if sweep_mid else "")
slides.append(f"""<div class="s"><div class="kick">Result 2 · Fairness</div>
<h2>Same alert budget, shared fairly: far fewer genuine seniors wrongly flagged.</h2>
<div class="row" style="grid-template-columns:1.3fr 1fr;align-items:center">
<img class="fig" src="{fig('fairness')}">
<div class="take">Genuine seniors wrongly flagged: <b>{p(N['fed_fs'])} → {p(N['sg_fs'])}</b>. Under-50s: {p(N['fed_fn'])} → {p(N['sg_fn'])}, because the alert budget is shared more evenly.<br><br>The price is fraud capture: {p(N['sgt'])} → {p(N['sg'])}. That is still <b>{fmt_up(N['up_sg'])}</b> above banks working alone. {trade}</div>
</div>{foot(8)}</div>""")

slides.append(f"""<div class="s"><div class="kick">Result 3 · Robustness</div>
<h2>Defences based on agreement between banks collapse once most participants are compromised.</h2>
<img class="fig" src="{fig('robustness')}" style="height:372px;width:auto;max-width:100%">
<p class="lede" style="margin-top:14px;font-size:18px">Reference-anchored defences (FLTrust, Sangam) survive every scenario. Across all six attacks, Sangam never gave attackers more than {p(N['sg_max_aw'], 0)} of the influence; FLTrust gave up to {p(N['flt_max_aw'], 0)}.</p>{foot(9)}</div>""")

slides.append(f"""<div class="s"><div class="kick">Result 4 · Stealthy attack on senior citizens</div>
<h2>Poison hidden in one customer segment fools average-based checks. Sangam inspects every segment.</h2>
<div class="row" style="grid-template-columns:1.5fr 1fr;align-items:center">
<img class="fig" src="{fig('targeted')}">
<div class="take">Four banks quietly teach the model to ignore fraud on seniors' accounts.<br><br>FedAvg loses <b>{100*N['tg_fed_drop']:.0f} pts</b> of senior fraud capture, Multi-Krum <b>{100*N['tg_krum_drop']:.0f}</b>, FLTrust <b>{100*N['tg_flt_drop']:.0f}</b>. With fairness on, FLTrust's fairness collapses ({N['clean_fltf_ratio']:.2f} → {N['tg_fltf_ratio']:.2f}).<br><br><b>Sangam gives attackers {p(N['tg_sg_aw'], 0)} of the influence and stays fair ({N['tg_sg_ratio']:.2f}).</b></div>
</div>{foot(10)}</div>""")

slides.append(f"""<div class="s"><div class="kick">What is new</div>
<h2>The only approach in our comparison that delivers all six properties together.</h2>
<table>
<tr><th>Approach</th><th>Learns across banks</th><th>No raw data shared</th><th>Survives majority compromise</th><th>Catches segment-targeted poison</th><th>Fair to seniors</th><th>Audit trail</th></tr>
<tr><td>Each bank alone (status quo)</td><td>{Y(0)}</td><td>{Y(1)}</td><td>{Y(1)}</td><td>{Y(1)}</td><td>{Y(0)}</td><td>{Y(0)}</td></tr>
<tr><td>Pool data centrally</td><td>{Y(1)}</td><td>{Y(0)}</td><td>{Y(0)}</td><td>{Y(0)}</td><td>{Y(0)}</td><td>{Y(0)}</td></tr>
<tr><td>Standard federated learning (FedAvg)</td><td>{Y(1)}</td><td>{Y(1)}</td><td>{Y(0)}</td><td>{Y(0)}</td><td>{Y(0)}</td><td>{Y(0)}</td></tr>
<tr><td>Robust FL: Krum, Median, Trimmed-Mean</td><td>{Y(1)}</td><td>{Y(1)}</td><td>{Y(0)}</td><td>{Y(0)}</td><td>{Y(0)}</td><td>{Y(0)}</td></tr>
<tr><td>Reference-anchored FL (FLTrust)</td><td>{Y(1)}</td><td>{Y(1)}</td><td>{Y(1)}</td><td><span style="color:#eb6834;font-weight:700">partial</span></td><td>{Y(0)}</td><td>{Y(1)}</td></tr>
<tr class="ours"><td>Sangam</td><td>{Y(1)}</td><td>{Y(1)}</td><td>{Y(1)}</td><td>{Y(1)}</td><td>{Y(1)}</td><td>{Y(1)}</td></tr>
</table>
<p class="lede" style="margin-top:20px;font-size:16px">Judged on our benchmark results. "Each bank alone" cannot be poisoned by peers, but it also learns nothing from them.</p>{foot(11)}</div>""")

slides.append(f"""<div class="s"><div class="kick">Path to deployment at GIFT City</div>
<h2>Built to walk IFSCA's 2026 FinTech Sandbox path.</h2>
<div class="row c4">
<div class="card"><div class="kick" style="margin:0 0 8px">Dec 2026</div><h3>Open benchmark</h3><p>Code and results released; mentoring through the Grand Challenge.</p></div>
<div class="card"><div class="kick" style="margin:0 0 8px">Q1 2027</div><h3>Innovation sandbox</h3><p>Replay on historical data from 2–3 IFSC Banking Units.</p></div>
<div class="card"><div class="kick" style="margin:0 0 8px">Q2–Q3 2027</div><h3>Shadow mode</h3><p>Score live applications alongside existing checks, with no automated action.</p></div>
<div class="card"><div class="kick" style="margin:0 0 8px">Q4 2027</div><h3>Live consortium</h3><p>Regulatory-sandbox live test, with published fairness and robustness audits.</p></div>
</div>
<div class="row c3" style="margin-top:22px">
<div class="card"><h3>Banks</h3><p>A stronger mule defence for every member, and no customer data leaves the bank.</p></div>
<div class="card"><h3>Regulators</h3><p>An auditable consortium with measurable fairness and an attack log.</p></div>
<div class="card"><h3>Customers</h3><p>Fewer frauds, and fewer genuine senior citizens wrongly blocked.</p></div>
</div>{foot(12)}</div>""")

kdesc = k["programme"] if k["programme"] != "TO_FILL" else ""
slides.append(f"""<div class="s dark"><div class="kick">Team</div>
<h2>Built at IIT Gandhinagar for the future of trusted finance.</h2>
<div class="row c2" style="max-width:980px">
<div class="card"><h3>Yash Goyal · Team lead</h3><p>B.Tech CSE, IIT Gandhinagar (CPI 8.80). Federated-learning fairness research (DCA-FW); semantic retrieval at scale; algorithmic-trading backtesting; Barclays Mentorship Programme 2026.</p></div>
<div class="card"><h3>{k['name']}</h3><p>{kdesc or 'Co-developer'}{(' · ' + kinst) if kinst else ''}. {k['contribution']}</p></div>
</div>
<p class="lede" style="margin-top:40px;font-size:22px"><b>Our ask:</b> mentorship and introductions to 2–3 IFSC Banking Units and the IFSCA sandbox team, for a historical-data pilot in Q1 2027.</p>
<div class="foot"><span>Sangam · GIFT FutureLab Grand Challenge 2026–27</span><span>13</span></div></div>""")

html = f"<!doctype html><html><head><meta charset='utf-8'>{FONT}<style>{CSS}</style><title>Sangam pitch deck</title></head><body>{''.join(slides)}</body></html>"
(DOCS / "deck.html").write_text(html)

# simulator screenshot for slide 6
subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1180,700",
                "--virtual-time-budget=6000", f"--screenshot={DOCS / 'sim.png'}",
                (SITE / "index.html").as_uri() + "#embed-sim"], check=True, capture_output=True)
subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=8000",
                f"--print-to-pdf={SITE / 'Sangam_Pitch_Deck.pdf'}", (DOCS / "deck.html").as_uri()], check=True, capture_output=True)
print("wrote", SITE / "Sangam_Pitch_Deck.pdf")
