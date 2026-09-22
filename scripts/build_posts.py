#!/usr/bin/env python3
"""posts/*.md 를 /guide/ 목록과 /guide/<slug>/ 글 페이지로 낸다.

apex 는 Hugo 가 아니라 정적 HTML 이다. 파이썬 표준 라이브러리만 쓰는 제약이 있어
(워크플로에 pip install 단계가 없다) 마크다운도 여기서 최소한만 직접 처리한다.
제목, 문단, 목록, 표, 인용, 코드, 링크, 굵게, 인라인 코드까지가 전부다.
그 이상이 필요해지면 Hugo 를 들이는 게 맞다.

build_feed.py 가 이 파일을 불러 쓴다. 두 시간마다 도는 잡이 글 페이지와 사이트맵을
같이 다시 만든다.
"""
import html
import io
import os
import re
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
BASE = "https://importants-studio.com"


def esc(s):
    return html.escape(s or "", quote=True)


def parse(path):
    raw = io.open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
    if not m:
        raise ValueError("%s: 프런트매터가 없다" % path)
    head, body = m.groups()
    meta = {}
    for line in head.split("\n"):
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip().strip('"')
    for key in ("title", "date", "slug", "summary"):
        if not meta.get(key):
            raise ValueError("%s: %s 가 없다" % (path, key))
    meta["body"] = body.strip()
    return meta


def inline(s):
    """링크·굵게·인라인 코드만 처리한다. 순서가 중요하다."""
    out = []
    pos = 0
    for m in re.finditer(r"`([^`]+)`", s):
        out.append((pos, m.start(), s[pos:m.start()]))
        pos = m.end()
        out.append((m.start(), m.end(), "<code>%s</code>" % esc(m.group(1)), True))
    parts = []
    last = 0
    for m in re.finditer(r"`([^`]+)`", s):
        parts.append(("text", s[last:m.start()]))
        parts.append(("code", m.group(1)))
        last = m.end()
    parts.append(("text", s[last:]))

    res = []
    for kind, chunk in parts:
        if kind == "code":
            res.append("<code>%s</code>" % esc(chunk))
            continue
        t = esc(chunk)
        t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
                   lambda m: '<a href="%s"%s>%s</a>' % (
                       m.group(2),
                       ' target="_blank" rel="noopener"' if m.group(2).startswith("http") else "",
                       m.group(1)), t)
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        res.append(t)
    return "".join(res)


def render_md(md):
    lines = md.split("\n")
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()

        if not s:
            i += 1
            continue

        if s.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>%s</code></pre>" % esc("\n".join(buf)))
            continue

        if s.startswith("### "):
            out.append("<h3>%s</h3>" % inline(s[4:].strip()))
            i += 1
            continue
        if s.startswith("## "):
            out.append("<h2>%s</h2>" % inline(s[3:].strip()))
            i += 1
            continue

        if re.match(r"^-{3,}$", s):
            out.append("<hr>")
            i += 1
            continue

        if s.startswith("|"):
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            if len(rows) >= 2 and all(re.match(r"^:?-{2,}:?$", c) for c in rows[1]):
                head, body_rows = rows[0], rows[2:]
            else:
                head, body_rows = None, rows
            t = ["<table>"]
            if head:
                t.append("<thead><tr>%s</tr></thead>"
                         % "".join("<th>%s</th>" % inline(c) for c in head))
            t.append("<tbody>%s</tbody>" % "".join(
                "<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r)
                for r in body_rows))
            t.append("</table>")
            out.append("".join(t))
            continue

        if s.startswith("> "):
            buf = []
            while i < n and lines[i].strip().startswith("> "):
                buf.append(lines[i].strip()[2:])
                i += 1
            out.append("<blockquote><p>%s</p></blockquote>" % inline(" ".join(buf)))
            continue

        if re.match(r"^(-|\*) ", s) or re.match(r"^\d+\. ", s):
            ordered = bool(re.match(r"^\d+\. ", s))
            items = []
            while i < n:
                cur = lines[i].strip()
                if ordered and re.match(r"^\d+\. ", cur):
                    items.append(re.sub(r"^\d+\. ", "", cur))
                elif not ordered and re.match(r"^(-|\*) ", cur):
                    items.append(cur[2:])
                else:
                    break
                i += 1
            tag = "ol" if ordered else "ul"
            out.append("<%s>%s</%s>" % (
                tag, "".join("<li>%s</li>" % inline(x) for x in items), tag))
            continue

        buf = [s]
        i += 1
        while i < n and lines[i].strip() and not re.match(
                r"^(#{2,3} |```|\||> |-{3,}$|(-|\*) |\d+\. )", lines[i].strip()):
            buf.append(lines[i].strip())
            i += 1
        out.append("<p>%s</p>" % inline(" ".join(buf)))

    return "\n".join(out)


def kdate(d):
    y, m, dd = d.split("-")
    return "%s년 %d월 %d일" % (y, int(m), int(dd))


def load_all(posts_dir="posts"):
    if not os.path.isdir(posts_dir):
        return []
    metas = []
    for f in sorted(os.listdir(posts_dir)):
        if f.endswith(".md"):
            metas.append(parse(os.path.join(posts_dir, f)))
    metas.sort(key=lambda m: (m["date"], m["slug"]), reverse=True)
    return metas


def render(posts_dir="posts", out_dir="guide",
           post_tpl="post.template.html", list_tpl="guide.template.html"):
    metas = load_all(posts_dir)
    if not metas:
        return []

    ptpl = io.open(post_tpl, encoding="utf-8").read()
    ltpl = io.open(list_tpl, encoding="utf-8").read()
    os.makedirs(out_dir, exist_ok=True)

    total = len(metas)
    for idx, m in enumerate(metas):
        newer = metas[idx - 1] if idx > 0 else None
        older = metas[idx + 1] if idx + 1 < total else None
        nav = []
        if older:
            nav.append('지난 글: <a href="/guide/%s/">%s</a>' % (esc(older["slug"]), esc(older["title"])))
        if newer:
            nav.append('다음 글: <a href="/guide/%s/">%s</a>' % (esc(newer["slug"]), esc(newer["title"])))
        nav.append('<a href="/guide/">목록으로</a>')

        schema = (
            '{"@context":"https://schema.org","@type":"BlogPosting",'
            '"headline":%s,"description":%s,"datePublished":"%sT09:00:00+09:00",'
            '"author":{"@type":"Organization","name":"Importants Studio"},'
            '"publisher":{"@type":"Organization","name":"Importants Studio"},'
            '"mainEntityOfPage":"%s/guide/%s/"}'
            % (_json_str(m["title"]), _json_str(m["summary"]), m["date"], BASE, m["slug"]))

        s = ptpl
        s = s.replace("<!--TITLE-->", esc(m["title"]))
        s = s.replace("<!--SUMMARY-->", esc(m["summary"]))
        s = s.replace("<!--SLUG-->", esc(m["slug"]))
        s = s.replace("<!--DATE-->", kdate(m["date"]))
        s = s.replace("<!--ISODATE-->", "%sT09:00:00+09:00" % m["date"])
        s = s.replace("<!--SCHEMA-->", schema)
        s = s.replace("<!--BODY-->", render_md(m["body"]))
        s = s.replace("<!--TAIL-->", "<br>".join(nav))

        d = os.path.join(out_dir, m["slug"])
        os.makedirs(d, exist_ok=True)
        io.open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(s)

    items = []
    for idx, m in enumerate(metas):
        items.append(
            '<a class="item" href="/guide/%s/">'
            '<div class="itop"><span class="inum">%02d</span>'
            '<span class="idate">%s</span></div>'
            '<div class="ititle">%s</div><p class="isum">%s</p></a>'
            % (esc(m["slug"]), total - idx, esc(m["date"]),
               esc(m["title"]), esc(m["summary"])))
    io.open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8").write(
        ltpl.replace("<!--POSTS-->", "\n".join(items)))

    return metas


def _json_str(s):
    return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


if __name__ == "__main__":
    ms = render()
    print("글 %d편, /guide/ 와 /guide/<slug>/ 생성" % len(ms))
