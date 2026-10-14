#!/usr/bin/env python3
"""Builds the "07 Activity" panel from live GitHub data.

Runs daily in .github/workflows/profile.yml. Only public data is read, so the
workflow's default GITHUB_TOKEN is enough (no personal access token needed).

    GITHUB_TOKEN=... python tools/activity.py dist/activity.svg
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from build import ACCENT_L, INDEX, PAD, W, W45, W60, WHITE, Svg, section_head

USER = os.environ.get("GITHUB_USER", "shashwatmaran")
TOKEN = os.environ["GITHUB_TOKEN"]
HIDDEN_LANGS = {"HTML", "CSS", "SCSS", "Jupyter Notebook", "Makefile", "CMake", "Dockerfile", "Shell",
                "PowerShell", "Batchfile", "Procfile"}


def request(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USER}-profile-readme",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch():
    q = """query($login: String!) { user(login: $login) { contributionsCollection {
        totalCommitContributions
        contributionCalendar { totalContributions weeks { contributionDays { contributionCount } } } } } }"""
    res = request("https://api.github.com/graphql", {"query": q, "variables": {"login": USER}})
    if res.get("errors"):
        raise SystemExit(f"GraphQL error: {res['errors']}")
    cc = res["data"]["user"]["contributionsCollection"]

    repos = [r for r in request(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner")
             if not r["fork"] and r["name"] != USER]
    langs = {}
    for r in repos:
        for lang, size in request(r["languages_url"]).items():
            if lang not in HIDDEN_LANGS:
                langs[lang] = langs.get(lang, 0) + size
    return {
        "contributions": cc["contributionCalendar"]["totalContributions"],
        "commits": cc["totalCommitContributions"],
        "active_days": sum(1 for w in cc["contributionCalendar"]["weeks"] for day in w["contributionDays"]
                           if day["contributionCount"]),
        "repos": len(repos),
        "stars": sum(r["stargazers_count"] for r in repos),
        "langs": sorted(langs.items(), key=lambda kv: -kv[1]),
    }


def render(d):
    svg = Svg(f"On GitHub: {d['contributions']} contributions in the last year, {d['commits']} commits, "
              f"{d['active_days']} active days, {d['repos']} public repositories. Top languages: "
              + ", ".join(name for name, _ in d["langs"][:6]) + ".")
    y = section_head(svg, "07", "Activity", "On GitHub") + 34

    # Stat tiles
    tiles = [(f"{d['contributions']:,}", "Contributions in the last year"), (f"{d['commits']:,}", "Commits"),
             (f"{d['active_days']:,}", "Active days"), (f"{d['repos']:,}", "Public repositories"),
             (f"{d['stars']:,}", "Stars earned")]
    cw = (W - 2 * PAD) / len(tiles)
    svg.hline(PAD, W - PAD, y)
    bottom = y
    for i, (val, label) in enumerate(tiles):
        x = PAD + i * cw
        if i:
            svg.add(f'<line x1="{x - 12:.1f}" y1="{y + 18}" x2="{x - 12:.1f}" y2="{y + 96}" stroke="#ffffff1a"/>')
        svg.text(x, y + 48, val, "sans", 30, WHITE, ls=-0.03, cls="fu", style=f"animation-delay:{i * .06:.2f}s")
        b = svg.para(x, y + 72, label.upper(), cw - 26, "mono", 9.5, lh=1.55, fill=W45, ls=0.06)
        bottom = max(bottom, b)
    y = bottom + 30

    # Top languages: ranked single-hue bars, share of bytes across public repos
    top = d["langs"][:6]
    total = sum(size for _, size in d["langs"]) or 1
    svg.hline(PAD, W - PAD, y)
    svg.text(PAD, y + 34, "TOP LANGUAGES", "mono", 10.5, W60, ls=0.1)
    svg.text(W - PAD, y + 34, "SHARE OF CODE IN PUBLIC REPOS", "mono", 9.5, W45, anchor="end", ls=0.08)
    y += 62
    cols, colgap, row_h = 2, 48, 46
    colw = (W - 2 * PAD - colgap) / cols
    label_w, val_w = 104, 54
    track_w = colw - label_w - val_w
    peak = top[0][1] if top else 1
    rows = (len(top) + cols - 1) // cols
    for i, (name, size) in enumerate(top):
        c, r = divmod(i, rows)
        x, ry = PAD + c * (colw + colgap), y + r * row_h
        pct = size / total * 100
        svg.text(x, ry + 4, name.upper(), "mono", 10.5, WHITE, ls=0.06)
        tx = x + label_w
        bw = max(6, track_w * size / peak)
        svg.add(f'<rect x="{tx}" y="{ry - 3}" width="{track_w:.1f}" height="6" rx="3" fill="#ffffff12"/>'
                f'<rect x="{tx}" y="{ry - 3}" width="{bw:.1f}" height="6" rx="3" fill="{ACCENT_L if i else INDEX}"/>')
        svg.text(x + colw, ry + 4, f"{pct:.1f}%", "mono", 10.5, W60, anchor="end")
    y += rows * row_h + 4

    svg.hline(PAD, W - PAD, y)
    stamp = datetime.now(timezone.utc).strftime("%d %b %Y").upper()
    svg.text(PAD, y + 30, f"UPDATED {stamp} · REFRESHED DAILY BY GITHUB ACTIONS", "mono", 9.5, W45, ls=0.08)
    return svg.render(y + 54)


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/activity.svg")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(fetch()), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
