"""Build dashboard.html from discover-us.json + git history (7-day growth)."""
import html
import json
import subprocess
from datetime import datetime

REPO = None  # run from repo root (the .bat cd's here)


def sh(*args):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def parse_sections(doc):
    """Return (creators, hashtags, sounds) lists from a discover-us.json dict."""
    creators, hashtags, sounds = [], [], []
    for section in doc.get("body") or []:
        for it in section.get("exploreList") or []:
            c = it.get("cardItem") or {}
            e = c.get("extraInfo") or {}
            t = c.get("type")
            if t == 2:
                creators.append({"name": c.get("title", ""), "handle": c.get("subTitle", ""),
                                 "fans": e.get("fans", 0), "link": c.get("link", "")})
            elif t == 3:
                hashtags.append({"name": c.get("title", ""), "views": e.get("views", 0),
                                 "link": c.get("link", "")})
            elif t == 1:
                sounds.append({"name": c.get("title", ""), "artist": c.get("description", ""),
                               "posts": e.get("posts", 0), "link": c.get("link", "")})
    return creators, hashtags, sounds


def fmt(n):
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= div:
            v = n / div
            return f"{v:.1f}{suf}" if v < 100 else f"{v:.0f}{suf}"
    return str(n)


def growth_map(old_items, key):
    return {i["name"]: i[key] for i in old_items if i.get(key)}


def with_growth(items, old, key):
    """Attach pct (float) or None (new) to each item."""
    prev = growth_map(old, key)
    for i in items:
        before = prev.get(i["name"])
        i["pct"] = None if not before else (i[key] - before) / before * 100
    return items


def main():
    doc = json.load(open("discover-us.json", encoding="utf-8"))
    creators, hashtags, sounds = parse_sections(doc)

    data_date = sh("git", "log", "-1", "--format=%cd", "--date=format:%b %d %Y %H:%M",
                   "--", "discover-us.json")
    old_sha = sh("git", "log", "-1", "--format=%H", "--before=7 days ago", "--", "discover-us.json")
    old_date = ""
    if old_sha:
        old_raw = sh("git", "show", f"{old_sha}:discover-us.json")
        old_date = sh("git", "log", "-1", "--format=%cd", "--date=format:%b %d", old_sha)
        try:
            oc, oh, os_ = parse_sections(json.loads(old_raw))
        except json.JSONDecodeError:
            oc, oh, os_ = [], [], []
    else:
        oc, oh, os_ = [], [], []

    with_growth(hashtags, oh, "views")
    with_growth(sounds, os_, "posts")
    with_growth(creators, oc, "fans")

    # "Upcoming" = hashtags + sounds ranked by 7-day growth; brand-new entries first.
    rising = [dict(i, kind="tag", metric=i["views"]) for i in hashtags] + \
             [dict(i, kind="sound", metric=i["posts"]) for i in sounds]
    rising.sort(key=lambda i: (i["pct"] is not None, -(i["pct"] or 0)))
    rising = [i for i in rising if i["pct"] is None or i["pct"] > 0][:10]

    print(f"data: {data_date} | baseline: {old_date or 'none'} | "
          f"{len(hashtags)} tags, {len(sounds)} sounds, {len(creators)} creators")
    open("dashboard.html", "w", encoding="utf-8").write(
        render(rising, hashtags, sounds, creators, data_date, old_date))
    print("wrote dashboard.html")


def esc(s):
    return html.escape(str(s))


def delta_html(pct):
    if pct is None:
        return '<span class="badge new">NEW</span>'
    cls = "up" if pct >= 0 else "down"
    arrow = "▲" if pct >= 0 else "▼"
    p = f"{abs(pct):.0f}%" if abs(pct) >= 10 else f"{abs(pct):.1f}%"
    return f'<span class="delta {cls}">{arrow} {p}</span>'


def bar_rows(items, key, label_fn, sub_fn=None):
    mx = max((i[key] for i in items), default=1) or 1
    rows = []
    for i in items:
        w = max(i[key] / mx * 100, 0.5)
        sub = f'<span class="sub">{esc(sub_fn(i))}</span>' if sub_fn else ""
        rows.append(
            f'<a class="row" href="https://www.tiktok.com{esc(i["link"])}" target="_blank" '
            f'title="{esc(label_fn(i))}: {i[key]:,}">'
            f'<span class="lbl">{esc(label_fn(i))}{sub}</span>'
            f'<span class="track"><span class="bar" style="width:{w:.1f}%"></span></span>'
            f'<span class="val">{fmt(i[key])}</span>{delta_html(i.get("pct"))}</a>')
    return "\n".join(rows)


def render(rising, hashtags, sounds, creators, data_date, old_date):
    win = f"vs {old_date}" if old_date else "no baseline in history"

    rising_rows = []
    mx = max((abs(i["pct"]) for i in rising if i["pct"] is not None), default=1) or 1
    for i in rising:
        icon = "#" if i["kind"] == "tag" else "♪"
        if i["pct"] is None:
            bar = '<span class="track"><span class="bar newbar" style="width:100%"></span></span>'
        else:
            w = max(abs(i["pct"]) / mx * 100, 1)
            bar = f'<span class="track"><span class="bar" style="width:{w:.1f}%"></span></span>'
        rising_rows.append(
            f'<a class="row" href="https://www.tiktok.com{esc(i["link"])}" target="_blank" '
            f'title="{esc(i["name"])}: {i["metric"]:,} now">'
            f'<span class="lbl"><span class="kind">{icon}</span>{esc(i["name"])}</span>'
            f'{bar}<span class="val">{fmt(i["metric"])}</span>{delta_html(i["pct"])}</a>')

    tag_rows = "\n".join(
        f'<a class="trow" href="https://www.tiktok.com{esc(t["link"])}" target="_blank">'
        f'<span class="rank">{n}</span><span class="lbl">{esc(t["name"])}</span>'
        f'<span class="val">{fmt(t["views"])}</span>{delta_html(t["pct"])}</a>'
        for n, t in enumerate(sorted(hashtags, key=lambda x: -x["views"]), 1))

    sound_rows = bar_rows(sorted(sounds, key=lambda x: -x["posts"]), "posts",
                          lambda i: i["name"], lambda i: i["artist"])
    creator_rows = bar_rows(sorted(creators, key=lambda x: -x["fans"])[:15], "fans",
                            lambda i: i["name"], lambda i: i["handle"])

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TikTok Trends</title>
<style>
  :root {{
    color-scheme: light;
    --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e;
    --muted:#898781; --grid:#e1e0d9; --ring:rgba(11,11,11,.10);
    --series:#2a78d6; --up:#006300; --down:#d03b3b; --newc:#0ca30c;
  }}
  @media (prefers-color-scheme: dark) {{ :root {{
    color-scheme: dark;
    --page:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink2:#c3c2b7;
    --muted:#898781; --grid:#2c2c2a; --ring:rgba(255,255,255,.10);
    --series:#3987e5; --up:#0ca30c; --down:#e66767; --newc:#0ca30c;
  }} }}
  * {{ box-sizing:border-box }}
  body {{ margin:0; background:var(--page); color:var(--ink);
    font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif; padding:24px }}
  header {{ max-width:1200px; margin:0 auto 20px }}
  h1 {{ font-size:22px; margin:0 0 4px }}
  .meta {{ color:var(--ink2); font-size:13px }}
  .grid {{ max-width:1200px; margin:0 auto; display:grid; gap:16px;
    grid-template-columns:repeat(auto-fit,minmax(430px,1fr)) }}
  .card {{ background:var(--surface); border:1px solid var(--ring); border-radius:10px;
    padding:16px 18px }}
  .card h2 {{ font-size:15px; margin:0 0 2px }}
  .card .sub2 {{ color:var(--muted); font-size:12px; margin:0 0 12px }}
  .row,.trow {{ display:grid; align-items:center; gap:10px; padding:5px 6px;
    border-radius:6px; text-decoration:none; color:var(--ink) }}
  .row {{ grid-template-columns:minmax(140px,1.1fr) 1fr 52px 62px }}
  .trow {{ grid-template-columns:22px 1fr 60px 62px }}
  .row:hover,.trow:hover {{ background:var(--grid) }}
  .lbl {{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap }}
  .sub {{ color:var(--muted); font-size:12px; margin-left:6px }}
  .kind {{ color:var(--muted); margin-right:6px; font-size:12px }}
  .rank {{ color:var(--muted); font-size:12px; text-align:right }}
  .track {{ height:14px; background:transparent; position:relative }}
  .bar {{ display:block; height:100%; background:var(--series); border-radius:3px;
    min-width:2px }}
  .bar.newbar {{ background:repeating-linear-gradient(45deg,var(--series),var(--series) 4px,
    transparent 4px,transparent 8px) }}
  .val {{ font-variant-numeric:tabular-nums; text-align:right; color:var(--ink2) }}
  .delta {{ font-size:12px; font-variant-numeric:tabular-nums; text-align:right }}
  .delta.up {{ color:var(--up) }} .delta.down {{ color:var(--down) }}
  .badge.new {{ font-size:11px; font-weight:600; color:var(--newc);
    border:1px solid var(--newc); border-radius:4px; padding:0 4px; text-align:center }}
  footer {{ max-width:1200px; margin:16px auto 0; color:var(--muted); font-size:12px }}
</style></head><body>
<header>
  <h1>TikTok Trends &mdash; US Discover</h1>
  <div class="meta">Data snapshot: {esc(data_date)} UTC &middot; growth {esc(win)} &middot;
  click any row to open on TikTok</div>
</header>
<div class="grid">
  <div class="card"><h2>Upcoming &mdash; fastest growing (7 days)</h2>
    <p class="sub2">Hashtags (#) and sounds (&#9834;) by view/post growth; striped bar = new this week. Bar = growth&nbsp;%.</p>
    {''.join(rising_rows)}</div>
  <div class="card"><h2>Trending hashtags</h2>
    <p class="sub2">By total views (curated Discover list)</p>
    {tag_rows}</div>
  <div class="card"><h2>Trending sounds</h2>
    <p class="sub2">By videos using the sound. Bar = share of top sound.</p>
    {sound_rows}</div>
  <div class="card"><h2>Top featured creators</h2>
    <p class="sub2">By followers. Bar = share of top creator.</p>
    {creator_rows}</div>
</div>
<footer>Generated by build_dashboard.py from discover-us.json &middot; run run-dashboard.bat to refresh</footer>
</body></html>"""


if __name__ == "__main__":
    main()
