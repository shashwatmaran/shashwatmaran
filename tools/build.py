#!/usr/bin/env python3
"""Generates the SVG panels in ../assets used by the profile README.

The look mirrors https://www.shashwatmanimaran.tech/ : near-black panels,
Aspekta for headings and body, a mono face for uppercase labels, and the
site's deep-blue accent. Fonts are subset per panel and embedded, so the
panels render the same for every viewer.

    pip install fonttools brotli
    python tools/build.py
"""

import base64
import io
import re
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "assets"
ICONS = ROOT / "icons"

W = 840
PAD = 40

# Site palette (see --c-* variables on shashwatmanimaran.tech)
BG = "#010101"
WHITE = "#ffffff"
W80 = "#ffffffcc"
W62 = "#ffffff9e"
W60 = "#ffffff99"
W45 = "#ffffff73"
LINE = "#ffffff1a"
ACCENT = "#0943a0"
ACCENT_L = "#0055df"
INDEX = "#4a8eff"

FONTS = {
    "sans": {"file": "Aspekta-400.woff2", "family": "Aspekta", "fallback": "Arial, sans-serif"},
    "mono": {"file": "GeistMono.woff2", "family": "SiteMono", "fallback": "ui-monospace, Menlo, Consolas, monospace",
             "axes": {"wght": 400}},
}


def _load(key):
    spec = FONTS[key]
    font = TTFont(ROOT / "fonts" / spec["file"])
    if "axes" in spec:
        font = instancer.instantiateVariableFont(font, spec["axes"])
    return font


_FONT_CACHE = {k: _load(k) for k in FONTS}
_CMAP = {k: f.getBestCmap() for k, f in _FONT_CACHE.items()}
_UPEM = {k: f["head"].unitsPerEm for k, f in _FONT_CACHE.items()}


def has_glyph(font, ch):
    return ord(ch) in _CMAP[font]


def runs(s, font):
    """Split text into (font, text) runs, falling back to the other face for missing glyphs."""
    other = "sans" if font == "mono" else "mono"
    out = []
    for ch in s:
        f = font if (ch == " " or has_glyph(font, ch) or not has_glyph(other, ch)) else other
        if out and out[-1][0] == f:
            out[-1][1] += ch
        else:
            out.append([f, ch])
    return out


def measure(s, font="sans", size=16, ls=0.0):
    total = 0
    for f, part in runs(s, font):
        hmtx = _FONT_CACHE[f]["hmtx"]
        for ch in part:
            gname = _CMAP[f].get(ord(ch))
            adv = hmtx[gname][0] if gname else _UPEM[f] * 0.5
            total += adv / _UPEM[f] * size
    return total + ls * size * len(s)


def wrap(s, width, font="sans", size=16, ls=0.0):
    lines, cur = [], ""
    for word in s.split(" "):
        trial = f"{cur} {word}" if cur else word
        if cur and measure(trial, font, size, ls) > width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Svg:
    def __init__(self, title, width=W):
        self.title = title
        self.w = width
        self.parts = []
        self.defs = []
        self.css = []
        self.used = {k: set() for k in FONTS}

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, font="sans", size=16, fill=WHITE, anchor="start", ls=0.0, cls="", style=""):
        attrs = f'x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}"'
        if anchor != "start":
            attrs += f' text-anchor="{anchor}"'
        if ls:
            attrs += f' letter-spacing="{ls}em"'
        classes = " ".join(c for c in [font[0], cls] if c)
        attrs += f' class="{classes}"'
        if style:
            attrs += f' style="{style}"'
        inner = ""
        for f, part in runs(s, font):
            self.used[f].update(part)
            inner += esc(part) if f == font else f'<tspan class="{f[0]}">{esc(part)}</tspan>'
        self.add(f"<text {attrs}>{inner}</text>")

    def rich(self, x, y, pieces, font="sans", size=16, ls=0.0, anchor="start", cls="", style=""):
        """One line made of (text, fill) pieces."""
        attrs = f'x="{x:.1f}" y="{y:.1f}" font-size="{size}"'
        if anchor != "start":
            attrs += f' text-anchor="{anchor}"'
        if ls:
            attrs += f' letter-spacing="{ls}em"'
        attrs += f' class="{" ".join(c for c in [font[0], cls] if c)}"'
        if style:
            attrs += f' style="{style}"'
        inner = ""
        for s, fill in pieces:
            for f, part in runs(s, font):
                self.used[f].update(part)
                fam = f' class="{f[0]}"' if f != font else ""
                inner += f'<tspan fill="{fill}"{fam}>{esc(part)}</tspan>'
        self.add(f"<text {attrs}>{inner}</text>")

    def para(self, x, y, s, width, font="sans", size=16, lh=1.6, fill=W60, ls=0.0, cls="", style=""):
        """Wrapped paragraph whose first baseline is y; returns the y after the last line."""
        lines = wrap(s, width, font, size, ls)
        for i, line in enumerate(lines):
            self.text(x, y + i * size * lh, line, font, size, fill, ls=ls, cls=cls, style=style)
        return y + len(lines) * size * lh

    def hline(self, x1, x2, y, color=LINE):
        self.add(f'<line x1="{x1}" y1="{y + 0.5}" x2="{x2}" y2="{y + 0.5}" stroke="{color}"/>')

    def chip(self, x, y, label, size=10.5, h=26, solid=False):
        label = label.upper()
        w = measure(label, "mono", size, 0.05) + 24
        fill = ACCENT if solid else "#ffffff0a"
        stroke = ACCENT_L if solid else "#ffffff1f"
        self.add(f'<rect x="{x + .5}" y="{y + .5}" width="{w - 1:.1f}" height="{h - 1}" rx="{h / 2}" '
                 f'fill="{fill}" stroke="{stroke}"/>')
        self.text(x + w / 2, y + h / 2 + size * 0.36, label, "mono", size, W80, anchor="middle", ls=0.05)
        return w

    def chips(self, x, y, labels, width, gap=8, h=26, size=10.5):
        """Flowing row of pill tags; returns the y below the last row."""
        cx, cy = x, y
        for label in labels:
            w = measure(label.upper(), "mono", size, 0.05) + 24
            if cx + w > x + width:
                cx, cy = x, cy + h + gap
            self.chip(cx, cy, label, size, h)
            cx += w + gap
        return cy + h

    def font_css(self):
        css = []
        for key, chars in self.used.items():
            if not chars:
                continue
            spec = FONTS[key]
            font = _load(key)
            opts = subset.Options()
            opts.flavor = "woff2"
            opts.layout_features = ["kern", "liga", "calt", "tnum"]
            sub = subset.Subsetter(opts)
            sub.populate(text="".join(sorted(chars)))
            sub.subset(font)
            font.flavor = "woff2"
            buf = io.BytesIO()
            font.save(buf)
            data = base64.b64encode(buf.getvalue()).decode()
            css.append(f"@font-face{{font-family:'{spec['family']}';"
                       f"src:url(data:font/woff2;base64,{data}) format('woff2');}}")
        for key, spec in FONTS.items():
            css.append(f".{key[0]}{{font-family:'{spec['family']}',{spec['fallback']}}}")
        return "".join(css)

    def render(self, h, rounded=True):
        rx = 14 if rounded else 0
        base_css = (
            "@keyframes fu{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}"
            ".fu{animation:fu .9s cubic-bezier(.2,.7,.2,1) both}"
            "@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}"
            ".blink{animation:blink 1.1s steps(1) infinite}"
            "@keyframes pulse{0%{r:3.5px;opacity:.7}100%{r:11px;opacity:0}}"
            ".pulse{animation:pulse 2s ease-out infinite}"
            "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
            "text{white-space:pre}"
        )
        body = "\n".join(self.parts)
        defs = "".join(self.defs)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{h:.0f}" '
            f'viewBox="0 0 {self.w} {h:.0f}" xml:space="preserve" role="img" aria-label="{esc(self.title)}">\n'
            f"<title>{esc(self.title)}</title>\n"
            f"<defs><clipPath id=\"panel\"><rect width=\"{self.w}\" height=\"{h:.0f}\" rx=\"{rx}\"/></clipPath>{defs}</defs>\n"
            f"<style>{self.font_css()}{base_css}{''.join(self.css)}</style>\n"
            f'<g clip-path="url(#panel)">\n'
            f'<rect width="{self.w}" height="{h:.0f}" fill="{BG}"/>\n'
            f"{body}\n</g>\n"
            f'<rect x=".5" y=".5" width="{self.w - 1}" height="{h - 1:.0f}" rx="{rx}" fill="none" stroke="#ffffff1c"/>\n'
            f"</svg>\n"
        )


def save(name, svg, h, **kw):
    path = OUT / f"{name}.svg"
    path.write_text(svg.render(h, **kw), encoding="utf-8")
    print(f"  {path.name:28} {path.stat().st_size / 1024:6.1f} KB")


def delay(i, step=0.08, start=0.0):
    return f"animation-delay:{start + i * step:.2f}s"


def section_head(svg, idx, label, title, y=PAD + 8, intro=None):
    tag = "   " + label.upper()
    svg.rich(PAD, y, [(idx, INDEX), (tag, W60)], "mono", 11.5, ls=0.08, cls="fu")
    svg.hline(PAD + measure(idx + tag, "mono", 11.5, 0.08) + 18, W - PAD, y - 4)
    y += 50
    svg.text(PAD, y, title, "sans", 34, WHITE, ls=-0.03, cls="fu", style=delay(1))
    y += 16
    if intro:
        y = svg.para(PAD, y + 22, intro, W - 2 * PAD - 80, size=15.5, lh=1.6, cls="fu", style=delay(2)) - 6
    return y


# --------------------------------------------------------------------------- panels

def hero():
    svg = Svg("Shashwat Manimaran, Software Engineer. Building across systems, security and full-stack. "
              "Real-time C++ pipelines, raw-disk forensics tools, and secure products deployed on AWS.")
    H = 420

    # Faint hexdump of an NTFS boot sector and its first $MFT record, with a scanning bar.
    rows = [
        ("00000000", "EB 52 90 4E 54 46 53 20  20 20 20 00 02 08 00 00", "4E 54 46 53"),
        ("00000010", "00 00 00 00 00 F8 00 00  3F 00 FF 00 00 08 00 00", None),
        ("00000020", "00 00 00 00 80 00 80 00  FF 37 2A 07 00 00 00 00", None),
        ("00000030", "00 00 0C 00 00 00 00 00  02 00 00 00 00 00 00 00", "00 00 0C 00"),
        ("00000040", "F6 00 00 00 01 00 00 00  4A 1F 6C 2E 9B 6C 2E 70", None),
        ("00000050", "00 00 00 00 FA 33 C0 8E  D0 BC 00 7C FB 68 C0 07", None),
        ("00000060", "1F 1E 68 66 00 CB 88 16  0E 00 66 81 3E 03 00 4E", None),
        ("*", "", None),
        ("000001F0", "00 00 00 00 00 00 00 00  00 00 00 00 00 00 55 AA", "55 AA"),
        ("", "", None),
        ("C0000000", "46 49 4C 45 30 00 03 00  9A 2B 1F 05 00 00 00 00", "46 49 4C 45"),
        ("C0000010", "01 00 01 00 38 00 01 00  A0 01 00 00 00 04 00 00", None),
        ("C0000020", "00 00 00 00 00 00 00 00  06 00 00 00 00 00 00 00", None),
        ("C0000030", "10 00 00 00 60 00 00 00  00 00 18 00 00 00 00 00", None),
    ]
    svg.defs.append(
        '<linearGradient id="fadeX" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset=".45" stop-color="#fff" stop-opacity="1"/></linearGradient>'
        '<linearGradient id="fadeY" x1="0" x2="0" y1="0" y2="1"><stop offset=".55" stop-color="#fff"/>'
        '<stop offset="1" stop-color="#000"/></linearGradient>'
        '<mask id="hexmask"><rect x="500" y="80" width="340" height="300" fill="url(#fadeX)"/></mask>'
        '<linearGradient id="scan" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#0055df" stop-opacity="0"/>'
        '<stop offset="1" stop-color="#0055df" stop-opacity=".45"/></linearGradient>'
        '<radialGradient id="glow" cx=".85" cy="0" r=".9"><stop offset="0" stop-color="#0943a0" stop-opacity=".35"/>'
        '<stop offset="1" stop-color="#0943a0" stop-opacity="0"/></radialGradient>'
    )
    svg.css.append("@keyframes scan{from{transform:translateY(0)}to{transform:translateY(238px)}}"
                   ".scan{animation:scan 4.5s cubic-bezier(.45,0,.55,1) infinite alternate}")
    svg.add(f'<rect width="{W}" height="{H}" fill="url(#glow)"/>')
    svg.add('<g mask="url(#hexmask)">')
    svg.add('<rect class="scan" x="400" y="84" width="440" height="18" fill="url(#scan)"/>')
    hx, hy = 438, 98
    for i, (off, data, hl) in enumerate(rows):
        y = hy + i * 17
        if not off:
            continue
        pieces = [(off.ljust(10), "#4a8eff55")]
        if hl and hl in data:
            a, b = data.split(hl, 1)
            pieces += [(a, "#ffffff22"), (hl, "#4a8effcc"), (b, "#ffffff22")]
        else:
            pieces.append((data, "#ffffff22"))
        svg.rich(hx, y, pieces, "mono", 10.5)
    svg.add("</g>")

    # Navbar
    svg.text(PAD, 44, "SHASHWAT MANIMARAN", "mono", 11, W80, ls=0.08, cls="fu")
    svg.text(W - PAD, 44, "ABOUT   SKILLS   EXPERIENCE   PROJECTS   RECOGNITION", "mono", 11, W45,
             anchor="end", ls=0.08, cls="fu")
    svg.hline(0, W, 66)

    # Hero copy
    svg.add(f'<circle class="pulse" cx="{PAD + 4}" cy="120" r="3.5" fill="{ACCENT_L}"/>'
            f'<circle cx="{PAD + 4}" cy="120" r="3.5" fill="{ACCENT_L}"/>')
    svg.text(PAD + 18, 124, "SOFTWARE ENGINEER", "mono", 12, W60, ls=0.08, cls="fu", style=delay(1))
    svg.text(PAD - 3, 196, "Shashwat Manimaran", "sans", 64, WHITE, ls=-0.04, cls="fu", style=delay(2))
    l1, l2 = "Building across systems,", "security and full-stack."
    svg.text(PAD, 246, l1, "sans", 30, W62, ls=-0.02, cls="fu", style=delay(3))
    svg.text(PAD, 284, l2, "sans", 30, W62, ls=-0.02, cls="fu", style=delay(4))
    cx = PAD + measure(l2, "sans", 30, -0.02) + 6
    svg.add(f'<rect class="blink" x="{cx:.1f}" y="261" width="13" height="27" fill="{ACCENT_L}"/>')
    svg.para(PAD, 328, "Real-time C++ pipelines, raw-disk forensics tools, and secure products deployed on AWS.",
             420, size=15.5, lh=1.55, fill=W60, cls="fu", style=delay(5))

    # Footer strip
    svg.hline(0, W, 368)
    svg.text(PAD, 398, "BANGALORE, INDIA", "mono", 10.5, W45, ls=0.08)
    svg.text(W / 2, 398, "SYSTEMS · EMBEDDED · SECURITY", "mono", 10.5, W45, anchor="middle", ls=0.08)
    svg.add(f'<circle cx="{W - PAD - 150}" cy="394.5" r="3" fill="#2fbf71"/>')
    svg.text(W - PAD, 398, "OPEN TO SWE ROLES", "mono", 10.5, W60, anchor="end", ls=0.08)
    save("hero", svg, H)


def button(name, label, primary=False):
    size, h = 13, 44
    w = measure(label, "mono", size) + 44
    svg = Svg(label, width=round(w))
    fill, stroke, color = (ACCENT, ACCENT_L, WHITE) if primary else (BG, "#ffffff33", W80)
    svg.add(f'<rect width="{w}" height="{h}" fill="{fill}"/>')
    svg.text(w / 2, h / 2 + size * 0.36, label, "mono", size, color, anchor="middle")
    # Buttons are pills: override the panel's corner radius and stroke.
    out = svg.render(h).replace(f'rx="14"', f'rx="{h / 2}"').replace('stroke="#ffffff1c"', f'stroke="{stroke}"')
    (OUT / f"{name}.svg").write_text(out, encoding="utf-8")
    print(f"  {name + '.svg':28} {len(out) / 1024:6.1f} KB")


def about():
    svg = Svg("About me. Integrated M.Tech (Software Engineering) student at VIT with a 9.45 CGPA, "
              "Software Engineering Intern at HCLTech, co-inventor on two published Indian patent applications, "
              "AWS Certified Cloud Practitioner.")
    y = section_head(svg, "01", "About me", "From raw disk sectors to production.")
    paras = [
        "I'm an Integrated M.Tech (Software Engineering) student at VIT. As an intern at HCLTech I built a "
        "real-time C++20 weather data pipeline and a low-latency Linux alerting service.",
        "My own projects range from a raw-disk NTFS forensics toolkit written in pure Python, to a full-stack "
        "expense platform with a native Android client deployed on AWS, to an offline learning platform for "
        "schools without internet that runs on a Raspberry Pi. I'm most interested in systems software, "
        "semiconductors and security.",
    ]
    y += 30
    for i, p in enumerate(paras):
        y = svg.para(PAD, y, p, W - 2 * PAD - 40, size=16, lh=1.6, cls="fu", style=delay(2 + i)) + 12
    y += 14
    facts = [
        ("9.45", "CGPA · Integrated M.Tech, Software Engineering, VIT"),
        ("2", "Published Indian patent applications in AI governance and LLM security"),
        ("AWS", "Certified Cloud Practitioner"),
        ("HCLTech", "Software Engineering Intern, 2026"),
    ]
    cw = (W - 2 * PAD) / 4
    svg.hline(PAD, W - PAD, y)
    bottom = y
    for i, (val, label) in enumerate(facts):
        x = PAD + i * cw
        if i:
            svg.add(f'<line x1="{x - 12:.1f}" y1="{y + 18}" x2="{x - 12:.1f}" y2="{y + 112}" stroke="{LINE}"/>')
        svg.text(x, y + 52, val, "sans", 32, WHITE, ls=-0.03, cls="fu", style=delay(i, start=0.4))
        b = svg.para(x, y + 78, label.upper(), cw - 30, "mono", 10, lh=1.55, fill=W45, ls=0.06,
                     cls="fu", style=delay(i, start=0.45))
        bottom = max(bottom, b)
    save("about", svg, bottom + PAD - 6)


SKILL_ICONS = [
    ("C", "c-original"), ("C++", "cplusplus-original"), ("Python", "python-original"), ("Go", "go-original"),
    ("Kotlin", "kotlin-original"), ("TypeScript", "typescript-original"), ("Linux", "linux-plain"),
    ("Raspberry Pi", "raspberrypi-original"), ("React", "react-original"), ("Next.js", "nextjs-original"),
    ("Android", "android-original"), ("PostgreSQL", "postgresql-original"), ("MongoDB", "mongodb-original"),
    ("Redis", "redis-original"), ("SQLite", "sqlite-original"), ("AWS", "amazonwebservices-plain-wordmark"),
    ("Docker", "docker-original"), ("Terraform", "terraform-original"), ("GitHub Actions", "githubactions-original"),
    ("Prometheus", "prometheus-original"), ("Grafana", "grafana-original"), ("OpenCV", "opencv-original"),
    ("Git", "git-original"),
]
WHITE_ICONS = {"nextjs-original": "invert", "amazonwebservices-plain-wordmark": "white", "linux-plain": "white"}

SKILL_GROUPS = [
    ("Languages", ["C++ (C++20)", "Python", "Go", "Kotlin", "TypeScript", "JavaScript", "Java", "SQL"]),
    ("Systems & low-level", ["Linux system programming", "Embedded Linux (Raspberry Pi)", "Multithreading",
                             "Lock-free data structures", "Real-time scheduling (SCHED_FIFO)",
                             "On-disk format parsing (NTFS)", "Cross-compilation", "gdb"]),
    ("Security", ["Digital forensics ($MFT, USN journal, ADS)", "Timestomping detection", "Auth hardening",
                  "Rate limiting & CSP", "HMAC", "AES-GCM / Android Keystore", "LLM prompt-injection defence"]),
    ("Cloud & DevOps", ["AWS (ECS Fargate, ALB, IAM, Secrets Manager, CloudWatch)", "Docker", "Docker Compose",
                        "Terraform", "GitHub Actions", "systemd", "Vercel"]),
    ("Web & mobile", ["React", "Next.js", "Node.js", "TanStack Query", "Tailwind CSS", "Auth.js", "REST APIs",
                      "Android (Jetpack Compose, Hilt, Retrofit)"]),
    ("Data", ["TimescaleDB / PostgreSQL", "MongoDB", "SQLite", "Redis", "IndexedDB"]),
    ("Observability", ["Prometheus", "Grafana", "Sentry", "CloudWatch"]),
    ("AI / ML", ["llama.cpp (on-device inference)", "OpenCV", "OpenAI-compatible LLM APIs"]),
    ("Testing & tools", ["pytest", "Vitest", "Paparazzi", "MockWebServer", "Contract testing", "Git", "PyInstaller"]),
]


def icon_uri(name):
    raw = (ICONS / f"{name}.svg").read_text(encoding="utf-8")
    raw = re.sub(r"\s+", " ", raw).strip()
    return "data:image/svg+xml;base64," + base64.b64encode(raw.encode()).decode()


def skills():
    svg = Svg("Skills: C, C++20, Python, Go, Kotlin, TypeScript, Linux systems programming, NTFS forensics, "
              "auth hardening, AWS, Docker, Terraform, React, Next.js, Android, PostgreSQL, MongoDB, Redis.")
    svg.defs.append(
        '<filter id="white"><feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 1 0"/></filter>'
        '<filter id="invert"><feColorMatrix values="-1 0 0 0 1  0 -1 0 0 1  0 0 -1 0 1  0 0 0 1 0"/></filter>'
    )
    y = section_head(svg, "02", "Skills", "What I build with",
                     intro="Most of my work sits close to the system: concurrency, on-disk formats and the "
                           "security around them. I carry it through to tested, deployed products.")
    y += 26

    # Tech-stack chips with icons
    h, gap, size, isz = 34, 8, 10.5, 16
    x0, x, cy = PAD, PAD, y
    for i, (label, icon) in enumerate(SKILL_ICONS):
        text = label.upper()
        w = isz + 10 + measure(text, "mono", size, 0.05) + 26
        if x + w > W - PAD:
            x, cy = x0, cy + h + gap
        filt = WHITE_ICONS.get(icon)
        fattr = f' filter="url(#{filt})"' if filt else ""
        svg.add(f'<g class="fu" style="{delay(i, 0.025, 0.3)}">'
                f'<rect x="{x + .5:.1f}" y="{cy + .5:.1f}" width="{w - 1:.1f}" height="{h - 1}" rx="{h / 2}" '
                f'fill="#ffffff08" stroke="#ffffff1c"/>'
                f'<image x="{x + 13:.1f}" y="{cy + (h - isz) / 2:.1f}" width="{isz}" height="{isz}" '
                f'href="{icon_uri(icon)}"{fattr}/>')
        svg.text(x + 13 + isz + 9, cy + h / 2 + size * 0.36, text, "mono", size, W80, ls=0.05)
        svg.add("</g>")
        x += w + gap
    y = cy + h + 40

    # 3 x 3 grid of skill groups
    cols, colgap = 3, 28
    cw = (W - 2 * PAD - colgap * (cols - 1)) / cols
    for r in range(0, len(SKILL_GROUPS), cols):
        svg.hline(PAD, W - PAD, y)
        bottom = y
        for c, (title, items) in enumerate(SKILL_GROUPS[r:r + cols]):
            n = r + c + 1
            x = PAD + c * (cw + colgap)
            svg.text(x, y + 30, f"{n:02d}", "mono", 10.5, INDEX, ls=0.06)
            svg.text(x + 30, y + 30, title, "sans", 17, WHITE, ls=-0.01)
            b = svg.para(x, y + 56, ", ".join(items), cw - 6, size=13.5, lh=1.6, fill=W60)
            bottom = max(bottom, b)
        y = bottom + 14
    save("skills", svg, y + 18)


def marquee():
    svg = Svg("From raw disk sectors to production.")
    H, size = 56, 12.5
    seq = [("FROM RAW DISK SECTORS", W45), ("  →  ", INDEX), ("TO PRODUCTION", WHITE), ("    ●    ", ACCENT_L),
           ("SYSTEMS", W80), ("    ●    ", ACCENT_L), ("EMBEDDED", W80), ("    ●    ", ACCENT_L),
           ("SECURITY", W80), ("    ●    ", ACCENT_L)]
    seq_w = sum(measure(s, "mono", size, 0.1) for s, _ in seq)
    reps = int(W / seq_w) + 2
    svg.css.append(f"@keyframes mq{{from{{transform:translateX(0)}}to{{transform:translateX(-{seq_w:.2f}px)}}}}"
                   ".mq{animation:mq 22s linear infinite}")
    svg.add('<g class="mq">')
    svg.rich(PAD / 2, H / 2 + size * 0.36, seq * reps, "mono", size, ls=0.1)
    svg.add("</g>")
    save("marquee", svg, H)


def experience():
    svg = Svg("Experience: Software Engineering Intern at HCLTech, Chennai, May to July 2026. "
              "Built a real-time C++20 weather data pipeline and a low-latency Linux alerting service.")
    y = section_head(svg, "03", "Experience", "Where I've worked") + 40
    svg.text(PAD, y, "HCLTech", "sans", 28, WHITE, ls=-0.03, cls="fu", style=delay(2))
    svg.text(W - PAD, y - 4, "MAY — JUL 2026", "mono", 11, W45, anchor="end", ls=0.08)
    svg.text(PAD, y + 26, "Software Engineering Intern · Chennai, India", "mono", 12, W60, ls=0.02,
             cls="fu", style=delay(3))
    y += 54

    top = y
    ix, iw = PAD + 24, W - 2 * PAD - 48
    card_at = len(svg.parts)  # the inner card is inserted here once its height is known
    y += 38
    svg.text(ix, y, "PROJECT", "mono", 10.5, INDEX, ls=0.1)
    y += 30
    svg.text(ix, y, "Real-time weather data pipeline & alerting service", "sans", 20, WHITE, ls=-0.015)
    y = svg.para(ix, y + 30, "A C++20 pipeline that ingests live weather data from the Open-Meteo API into "
                             "TimescaleDB in three stages: multithreaded collectors, hierarchical aggregators "
                             "and a batching writer.", iw, size=14.5, lh=1.6) + 8
    bullets = [
        "Fault-tolerant storage layer: transactional writes in batches of 250 rows, duplicate removal, and a "
        "file-based outbox that replays buffered data after database outages.",
        "Memory stays bounded under overload: queues are capped at 4,096 messages, and backpressure events are "
        "exported to Prometheus and shown in Grafana.",
        "Real-time alerting service built on a lock-free ring buffer with SCHED_FIFO scheduling, comparing live "
        "readings against hourly baselines.",
        "Two front ends: a Leaflet map console showing weather hazards and per-segment delays on freight "
        "corridors, and a Chart.js dashboard for historical analysis.",
        "Deployed with Docker Compose and systemd, with architecture and setup documentation.",
    ]
    for b in bullets:
        svg.add(f'<rect x="{ix}" y="{y - 8.5:.1f}" width="8" height="2" fill="{ACCENT_L}"/>')
        y = svg.para(ix + 22, y, b, iw - 22, size=14, lh=1.6, fill=W60) + 6
    y += 10
    y = svg.chips(ix, y, ["C++20", "Multithreading", "Lock-free", "Linux SCHED_FIFO", "TimescaleDB", "Prometheus",
                          "Grafana", "Leaflet", "Chart.js", "Docker Compose", "systemd"], iw) + 26
    svg.parts.insert(card_at, f'<rect x="{PAD + .5}" y="{top + .5:.1f}" width="{W - 2 * PAD - 1}" '
                              f'height="{y - top:.1f}" rx="12" fill="#ffffff05" stroke="#ffffff17"/>')
    save("experience", svg, y + PAD - 8)


def art_forensics(svg, x, y):
    """Cluster-bitmap motif: allocated, free and recovered clusters with a scan column."""
    cols, rows, s, g = 18, 8, 8, 3
    import random
    rnd = random.Random(7)
    recovered = {(3, 2), (4, 2), (5, 2), (11, 5), (12, 5), (14, 1)}
    for r in range(rows):
        for c in range(cols):
            v = rnd.random()
            if (c, r) in recovered:
                fill = ACCENT_L
            elif v < 0.55:
                fill = "#ffffff38"
            else:
                fill = "#ffffff10"
            svg.add(f'<rect x="{x + c * (s + g)}" y="{y + r * (s + g)}" width="{s}" height="{s}" rx="1.5" fill="{fill}"/>')
    span = cols * (s + g)
    svg.css.append(f"@keyframes sweep{{from{{transform:translateX(0)}}to{{transform:translateX({span - 12}px)}}}}"
                   ".sweep{animation:sweep 3.6s cubic-bezier(.45,0,.55,1) infinite alternate}")
    svg.add(f'<rect class="sweep" x="{x - 2}" y="{y - 6}" width="12" height="{rows * (s + g) + 9}" rx="3" '
            f'fill="{ACCENT_L}" fill-opacity=".22" stroke="{ACCENT_L}" stroke-opacity=".6"/>')
    svg.text(x, y + rows * (s + g) + 18, "$BITMAP · RECOVERED CLUSTERS", "mono", 9, W45, ls=0.08)


def art_fintrack(svg, x, y):
    """Debt-simplification motif: a tangle of debts reduced to two settlements."""
    nodes = {"A": (x + 20, y + 20), "B": (x + 170, y + 14), "C": (x + 40, y + 96), "D": (x + 180, y + 92)}
    svg.defs.append(f'<marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" '
                    f'orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" fill="{ACCENT_L}"/></marker>')
    for a, b in [("A", "B"), ("B", "C"), ("C", "D"), ("A", "D"), ("B", "D")]:
        (x1, y1), (x2, y2) = nodes[a], nodes[b]
        svg.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#ffffff22" stroke-dasharray="3 4"/>')
    svg.css.append("@keyframes flow{to{stroke-dashoffset:-24}}.flow{animation:flow 1.2s linear infinite}")
    for a, b in [("A", "D"), ("C", "B")]:
        (x1, y1), (x2, y2) = nodes[a], nodes[b]
        dx, dy = x2 - x1, y2 - y1
        d = (dx * dx + dy * dy) ** 0.5
        ux, uy = dx / d, dy / d
        svg.add(f'<line class="flow" x1="{x1 + ux * 15:.1f}" y1="{y1 + uy * 15:.1f}" x2="{x2 - ux * 16:.1f}" '
                f'y2="{y2 - uy * 16:.1f}" stroke="{ACCENT_L}" stroke-width="1.6" stroke-dasharray="8 4" '
                f'marker-end="url(#arr)"/>')
    for name, (nx, ny) in nodes.items():
        svg.add(f'<circle cx="{nx}" cy="{ny}" r="13" fill="{BG}" stroke="#ffffff55"/>')
        svg.text(nx, ny + 4, name, "mono", 11, W80, anchor="middle")
    svg.text(x, y + 132, "5 DEBTS → 2 SETTLEMENTS", "mono", 9, W45, ls=0.08)


ARUCO = [
    "011010", "100110", "011101", "110001", "001110", "101011",
]
ARUCO2 = [
    "101100", "010011", "110110", "001001", "111010", "010101",
]


def art_tessera(svg, x, y):
    """Two printed ArUco-style programming cards."""
    def marker(mx, my, bits, size, rot):
        cell = size / 8
        cx, cy = mx + size / 2, my + size / 2
        out = [f'<g transform="rotate({rot} {cx} {cy})">',
               f'<rect x="{mx - 6}" y="{my - 6}" width="{size + 12}" height="{size + 30}" rx="5" fill="#f2f2f2"/>',
               f'<rect x="{mx}" y="{my}" width="{size}" height="{size}" fill="{BG}"/>']
        for r, row in enumerate(bits):
            for c, bit in enumerate(row):
                if bit == "1":
                    out.append(f'<rect x="{mx + (c + 1) * cell:.2f}" y="{my + (r + 1) * cell:.2f}" '
                               f'width="{cell + .3:.2f}" height="{cell + .3:.2f}" fill="#f2f2f2"/>')
        svg.add("".join(out))
        return cx, my + size + 16

    # marker() leaves its rotated group open so the caption rotates with the card.
    tx, ty = marker(x + 8, y + 6, ARUCO, 72, -7)
    svg.text(tx, ty, "MOVE ×3", "mono", 9, "#111111", anchor="middle", ls=0.08)
    svg.add("</g>")
    tx, ty = marker(x + 112, y + 2, ARUCO2, 72, 6)
    svg.text(tx, ty, "LOOP", "mono", 9, "#111111", anchor="middle", ls=0.08)
    svg.add("</g>")
    svg.text(x, y + 132, "ARUCO CARDS → JSON AST → GO", "mono", 9, W45, ls=0.08)


def project(name, idx, meta, title, subtitle, desc, stats, tags, art, head=False):
    svg = Svg(f"Project {idx}: {title}, {subtitle}. {desc}")
    y = PAD + 8
    if head:
        y = section_head(svg, "04", "Projects", "Things I've built",
                         intro="A disk forensics toolkit, a deployed fintech platform and an offline classroom "
                               "lab, each taken from idea to tested, working software.") + 40
        svg.hline(PAD, W - PAD, y - 18)
        y += 14
    top = y
    svg.text(PAD, y, idx, "mono", 12, INDEX, ls=0.06, cls="fu")
    svg.text(PAD + 32, y, meta.upper(), "mono", 11, W45, ls=0.08, cls="fu")
    art(svg, W - PAD - 205, top - 8)
    svg.text(PAD - 1, y + 50, title, "sans", 40, WHITE, ls=-0.035, cls="fu", style=delay(1))
    svg.text(PAD, y + 80, subtitle.upper(), "mono", 11.5, W60, ls=0.08, cls="fu", style=delay(2))
    y = svg.para(PAD, max(y + 124, top + 142), desc, W - 2 * PAD - 40, size=16, lh=1.6, cls="fu",
                 style=delay(3)) + 14
    cw = (W - 2 * PAD) / 4
    svg.hline(PAD, W - PAD, y)
    bottom = y
    for i, (val, label) in enumerate(stats):
        x = PAD + i * cw
        if i:
            svg.add(f'<line x1="{x - 12:.1f}" y1="{y + 18}" x2="{x - 12:.1f}" y2="{y + 100}" stroke="{LINE}"/>')
        svg.text(x, y + 46, val, "sans", 28, WHITE, ls=-0.03, cls="fu", style=delay(i, start=0.4))
        b = svg.para(x, y + 70, label.upper(), cw - 30, "mono", 9.5, lh=1.55, fill=W45, ls=0.06,
                     cls="fu", style=delay(i, start=0.45))
        bottom = max(bottom, b)
    y = bottom + 22
    y = svg.chips(PAD, y, tags, W - 2 * PAD)
    save(name, svg, y + PAD - 4)


def projects():
    project(
        "project-forensicalite", "01", "Sep 2025 — Present", "ForensicaLite", "NTFS disk forensics toolkit",
        "A raw-disk NTFS forensic analyzer in pure Python. It recovers deleted files, detects timestomping and "
        "rebuilds file history, without touching the OS file APIs.",
        [("100,159", "MFT records parsed in 5.7 s on a 57 GB volume"), ("300K+", "USN journal records processed"),
         ("0", "Scan errors; layout matched Windows fsutil"), ("156", "Automated tests (pytest + Vitest)")],
        ["Python", "TypeScript", "React", "Tailwind CSS", "Vite", "IndexedDB", "JSON Schema", "tkinter",
         "PyInstaller", "pytest", "Vitest"],
        art_forensics, head=True)
    project(
        "project-fintrack", "02", "Web · Android · AWS", "FinTrack", "Shared expense & settlement platform",
        "A full-stack expense-splitting platform with escrow-style settlements, hardened authentication and a "
        "native Android client, deployed on AWS.",
        [("733", "Automated tests on the web app"), ("5 → 0", "Client-side API calls on dashboard first load"),
         ("~12k", "Lines of Kotlin across 12 screens"), ("28", "Paparazzi screenshot tests")],
        ["Next.js", "React", "TypeScript", "MongoDB", "Redis", "Auth.js", "AWS ECS Fargate", "Terraform",
         "GitHub Actions", "Kotlin", "Jetpack Compose", "Hilt"],
        art_fintrack)
    project(
        "project-tessera", "03", "Offline-first · Raspberry Pi", "Tessera Quest", "Offline gamified coding & STEM platform",
        "Turns a room of computers with no internet into a working coding lab, using a Raspberry Pi, USB drives, "
        "printed cards and an on-device AI tutor.",
        [("25", "Levels, each automatically checked to be solvable"), ("14", "Printed ArUco programming cards"),
         ("4", "Subjects: coding, chemistry, physics, math"), ("0", "Accounts, cloud services or network needed")],
        ["Go", "React", "TypeScript", "Blockly", "Python", "OpenCV", "SQLite", "llama.cpp", "Raspberry Pi 5"],
        art_tessera)


def recognition():
    svg = Svg("Recognition: co-inventor on two published Indian patent applications, AWS Certified Cloud "
              "Practitioner, AWS Solutions Architect Associate in progress, Treasurer of Toastmasters Club (Fogo).")
    y = section_head(svg, "05", "Recognition", "Patents, certifications & leadership") + 30
    items = [
        ("Patent", "A System and Method for Centralized AI Governance and Orchestration",
         "Co-inventor · Indian Patent Application IN202641075844 A1", "Published Jun 2026"),
        ("Patent", "Prompt-Flow DAG Trust Graph for Multi-Hop Prompt Injection Detection in Multi-Agent LLM Workflows",
         "Co-inventor · Published Indian patent application", "Published"),
        ("Certification", "AWS Certified Cloud Practitioner", "Amazon Web Services", "2026"),
        ("Certification", "AWS Certified Solutions Architect – Associate", "In progress", "Expected Dec 2026"),
        ("Leadership", "Treasurer, Toastmasters Club (Fogo)", "Managed club finances and coordinated meetings.",
         "Oct 2024 — Oct 2025"),
    ]
    mx, mw = PAD + 150, 450
    for i, (kind, title, sub, date) in enumerate(items):
        svg.hline(PAD, W - PAD, y)
        st = delay(i, 0.08, 0.2)
        svg.text(PAD, y + 34, kind.upper(), "mono", 10.5, INDEX, ls=0.1, cls="fu", style=st)
        b = svg.para(mx, y + 34, title, mw, size=17.5, lh=1.45, fill=WHITE, ls=-0.01, cls="fu", style=st)
        b = svg.para(mx, b + 2, sub, mw, size=13.5, lh=1.5, fill=W45, cls="fu", style=st)
        svg.text(W - PAD, y + 34, date.upper(), "mono", 10.5, W60, anchor="end", ls=0.08, cls="fu", style=st)
        y = b + 12
    save("recognition", svg, y + PAD - 18)


def now():
    svg = Svg("Currently: a bare-metal AArch64 kernel for the Raspberry Pi 4B, prompt-injection detection with an "
              "evaluation harness, and studying for AWS Solutions Architect Associate.")
    y = section_head(svg, "06", "Now", "Currently working on") + 34
    items = [
        ("BUILDING", "Bare-metal AArch64 kernel for the Raspberry Pi 4B", "boot · UART · MMU · interrupts · scheduler"),
        ("RESEARCH", "Prompt-injection detection for multi-agent LLM workflows", "with a proper evaluation harness"),
        ("STUDYING", "AWS Certified Solutions Architect – Associate", "expected December 2026"),
    ]
    for i, (tag, line, sub) in enumerate(items):
        st = delay(i, 0.12, 0.2)
        svg.rich(PAD, y, [("› ", INDEX), (line, WHITE)], "sans", 17, ls=-0.01, cls="fu", style=st)
        svg.text(PAD + 16, y + 24, sub, "mono", 11.5, W45, ls=0.02, cls="fu", style=st)
        w = measure(tag, "mono", 10, 0.1) + 22
        svg.add(f'<g class="fu" style="{st}"><rect x="{W - PAD - w + .5:.1f}" y="{y - 17.5}" width="{w - 1:.1f}" '
                f'height="25" rx="12.5" fill="#0943a033" stroke="#0055df88"/>')
        svg.text(W - PAD - w / 2, y - 1, tag, "mono", 10, "#9cc1ff", anchor="middle", ls=0.1)
        svg.add("</g>")
        y += 64
    svg.hline(PAD, W - PAD, y - 18)
    prompt = "shashwat@pi4b:~/kernel $ make run"
    svg.text(PAD, y + 16, prompt, "mono", 12, W60)
    cx = PAD + measure(prompt, "mono", 12) + 6
    svg.add(f'<rect class="blink" x="{cx:.1f}" y="{y + 4}" width="8" height="15" fill="{ACCENT_L}"/>')
    save("now", svg, y + 44)


def contact():
    svg = Svg("Let's talk. I'm looking for software engineering roles in systems, embedded and security. "
              "Email shashwatmanimaran@gmail.com. Based in Bangalore, India.")
    svg.defs.append('<radialGradient id="cglow" cx=".1" cy="1" r=".9"><stop offset="0" stop-color="#0943a0" '
                    'stop-opacity=".4"/><stop offset="1" stop-color="#0943a0" stop-opacity="0"/></radialGradient>')
    H = 360
    svg.add(f'<rect width="{W}" height="{H}" fill="url(#cglow)"/>')
    svg.rich(PAD, PAD + 8, [("08", INDEX), ("   CONTACT", W60)], "mono", 11.5, ls=0.08)
    svg.hline(PAD + 130, W - PAD, PAD + 4)
    svg.text(PAD - 3, 136, "Let's talk", "sans", 68, WHITE, ls=-0.045, cls="fu", style=delay(1))
    svg.para(PAD, 180, "I'm looking for software engineering roles in systems, embedded and security. If you're "
                       "hiring, or want to talk about something I've built, send me a message.",
             470, size=16, lh=1.6, cls="fu", style=delay(2))
    cols = [("Direct email", "shashwatmanimaran@gmail.com"), ("Based in", "Bangalore, India"),
            ("Find me on", "GitHub · LinkedIn · Résumé")]
    y = 266
    svg.hline(PAD, W - PAD, y)
    xs = [PAD, PAD + 320, PAD + 520]
    for i, ((label, value), x) in enumerate(zip(cols, xs)):
        svg.text(x, y + 30, label.upper(), "mono", 10, W45, ls=0.1, cls="fu", style=delay(i, start=0.3))
        svg.text(x, y + 56, value, "mono", 13, WHITE, cls="fu", style=delay(i, start=0.35))
    save("contact", svg, H)


def main():
    OUT.mkdir(exist_ok=True)
    print(f"Writing panels to {OUT}")
    hero()
    button("btn-portfolio", "View portfolio ↗", primary=True)
    button("btn-resume", "Résumé ↗")
    button("btn-linkedin", "LinkedIn ↗")
    button("btn-email", "Get in touch →")
    about()
    skills()
    marquee()
    experience()
    projects()
    recognition()
    now()
    contact()


if __name__ == "__main__":
    main()
