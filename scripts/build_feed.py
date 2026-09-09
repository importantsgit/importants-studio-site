#!/usr/bin/env python3
"""apex 매거진 홈의 feed.json 과 index.html 을 만든다.

apex 는 Hugo 가 아니라 정적 HTML 한 장이다. 처음에는 화면이 feed.json 을 자바스크립트로
읽어 그리게 했는데, 그러면 크롤러가 보는 HTML 이 82자뿐이었다. 애드센스가 이 도메인을
"가치가 별로 없는 콘텐츠" 로 막은 마당에 그건 더 나쁘다. 그래서 여기서 HTML 까지 만들어
index.template.html 에 박아 index.html 로 낸다. 화면은 자바스크립트 없이 완성된다.

블로그는 각자 Hugo 가 내는 index.xml(RSS)을 읽는다. 심심풀이는 글이 없어서 게임과
도구 목록을 코드에 둔다.

돈의문법과 여행의밑줄은 HTTPS 인증서가 아직 안 붙어서 http 로 읽는다. 이 파일이
서버(GitHub Actions)에서 돌아 결과만 https 로 서빙되므로 혼합 콘텐츠 문제는 없다.
인증서가 붙으면 http 를 지우면 된다.
"""
import io
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

PER_BLOG = 5
PLAY_COLOR = "#6c4cf1"
KST = timezone(timedelta(hours=9))
TIMEOUT = 20

BLOGS = [
    ("hyetaek",   "혜택줍줍",   "#0e9f6e", "blog",      "정부 지원금과 세금 환급을 매일 정리합니다"),
    # 혜택줍줍과 같은 초록을 쓰면 매거진 홈에서 두 블로그가 구분되지 않는다. 청록으로 뗀다.
    ("chagok",    "차곡차곡",   "#0d8a8a", "car",       "자동차세, 보험료, 검사 기한을 챙깁니다"),
    ("homelog",   "홈로그",     "#d9527a", "home",      "결혼과 육아에 드는 돈과 제도를 정리합니다"),
    ("leisurely", "느긋하게",   "#2c4a7c", "leisurely", "연금과 건강보험, 은퇴 뒤의 살림을 정리합니다"),
    ("money",     "돈의문법",   "#2f6fdb", "money",     "뉴스의 숫자가 무슨 뜻인지 풀어 씁니다"),
    ("travel",    "여행의밑줄", "#e07b39", "travel",    "떠나기 전에 확인해야 할 것을 짚습니다"),
]

# 심심풀이는 글이 없다. 게임과 도구가 콘텐츠다.
SIMSIM = "https://simsim.importants-studio.com"
PLAY = [
    ("게임", "사다리타기",   "/games/ladder/"),
    ("게임", "룰렛",         "/games/roulette/"),
    ("게임", "주사위",       "/games/dice/"),
    ("게임", "폭탄 돌리기",  "/games/bomb/"),
    ("게임", "서바이벌",     "/games/survival/"),
    ("게임", "롤링 보드",    "/games/roll-board/"),
    ("도구", "날짜 뽑기",    "/tools/date-pick/"),
    ("도구", "연차 계산기",  "/tools/yeoncha/"),
    ("도구", "정산기",       "/tools/settle/"),
]

PROFILE = {
    "url": "/profile/",
    "label": "만든 사람과 앱",
}

LINKS = {
    "instagram": [
        {"name": "혜택줍줍",  "handle": "jupjup.money",     "url": "https://www.instagram.com/jupjup.money/"},
        {"name": "차곡차곡",  "handle": "chagok.car",       "url": "https://www.instagram.com/chagok.car/"},
        {"name": "홈로그",    "handle": "homelog.family",   "url": "https://www.instagram.com/homelog.family/"},
        {"name": "느긋하게",  "handle": "leisurely.retire", "url": "https://www.instagram.com/leisurely.retire/"},
    ],
    "email": "contact@importants-studio.com",
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "importants-feed/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def strip_tags(t):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t or "")).strip()


def read_rss(host):
    """https 로 먼저, 안 되면 http 로. 인증서가 늦게 붙는 도메인이 있다."""
    for scheme in ("https", "http"):
        url = "%s://%s.importants-studio.com/index.xml" % (scheme, host)
        try:
            return ET.fromstring(fetch(url)), scheme
        except Exception:
            continue
    return None, None


def items_of(root, site):
    out = []
    for it in root.iter("item"):
        def g(tag):
            e = it.find(tag)
            return (e.text or "").strip() if e is not None and e.text else ""
        link = g("link")
        # RSS 에는 개인정보처리방침 같은 단일 페이지도 섞여 나온다. 글만 고른다.
        if not link or "/posts/" not in link:
            continue
        out.append({
            "title": g("title"),
            "url": link,
            "summary": strip_tags(g("description"))[:180],
            "date": g("pubDate"),
        })
        if len(out) >= PER_BLOG:
            break
    return out


def esc(t):
    return (str(t or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def short_date(v):
    """RSS 의 pubDate 를 "9. 8." 로. 못 읽으면 원문 그대로."""
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            d = datetime.strptime(v, fmt)
            return "%d. %d." % (d.month, d.day)
        except Exception:
            pass
    return v or ""


def section_head(name, tagline, url, color):
    return (
        '<a class="sechead" href="%s">'
        '<span class="dot" style="background:%s"></span>'
        '<span class="secname">%s</span>'
        '<span class="sectag">%s</span>'
        '<span class="secmore" style="color:%s">전체 →</span></a>'
        % (esc(url), esc(color), esc(name), esc(tagline), esc(color)))


def render_html(data, template="index.template.html", out="index.html"):
    """크롤러가 자바스크립트 없이 읽을 수 있게 HTML 로 박는다."""
    blogs = []
    for b in data["blogs"]:
        posts = []
        for p in b["posts"][:5]:
            posts.append(
                '<a class="post" href="%s"><span class="ptitle">%s</span>'
                '<span class="psum">%s</span><span class="pdate">%s</span></a>'
                % (esc(p["url"]), esc(p["title"]), esc(p["summary"]),
                   esc(short_date(p["date"]))))
        blogs.append('<section class="sec">%s<div class="posts">%s</div></section>'
                     % (section_head(b["name"], b["tagline"], b["url"], b["color"]),
                        "".join(posts)))

    play = data["play"]
    tiles = "".join(
        '<a class="tile" href="%s"><span class="tkind">%s</span>'
        '<span class="tname">%s</span></a>'
        % (esc(i["url"]), esc(i["kind"]), esc(i["name"])) for i in play["items"])
    play_html = ('<section class="sec">%s<div class="tiles">%s</div></section>'
                 % (section_head(play["name"], play["tagline"], play["url"], PLAY_COLOR),
                    tiles))

    igs = "".join(
        '<a class="ig" href="%s"><span class="igname">%s</span>'
        '<span class="ighandle">%s</span></a>'
        % (esc(i["url"]), esc(i["name"]), esc(i["handle"]))
        for i in data["links"]["instagram"])

    today = datetime.now(KST).strftime("%Y. ") + \
        "%d. %d." % (datetime.now(KST).month, datetime.now(KST).day)

    s = io.open(template, encoding="utf-8").read()
    s = s.replace("<!--TODAY-->", today)
    s = s.replace("<!--BLOGS-->", "\n".join(blogs))
    s = s.replace("<!--PLAY-->", play_html)
    s = s.replace("<!--IGS-->", '<div class="igs">%s</div>' % igs)
    io.open(out, "w", encoding="utf-8").write(s)

    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", s, flags=re.S)
    body = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip()
    return len(body)


def main():
    blogs, warn = [], []
    for key, name, color, host, tagline in BLOGS:
        root, scheme = read_rss(host)
        if root is None:
            warn.append("%s RSS 를 읽지 못했습니다" % name)
            posts = []
        else:
            posts = items_of(root, host)
            if scheme == "http":
                warn.append("%s 는 아직 http 로 읽었습니다 (인증서 대기)" % name)
        blogs.append({
            "key": key, "name": name, "color": color, "tagline": tagline,
            "url": "https://%s.importants-studio.com" % host,
            "posts": posts,
        })

    data = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "blogs": blogs,
        "play": {
            "url": SIMSIM,
            "name": "심심풀이",
            "tagline": "심심할 때 즐겨보세요",
            "items": [{"kind": k, "name": n, "url": SIMSIM + u} for k, n, u in PLAY],
        },
        "profile": PROFILE,
        "links": LINKS,
    }

    out = sys.argv[1] if len(sys.argv) > 1 else "feed.json"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    chars = render_html(data)

    total = sum(len(b["posts"]) for b in blogs)
    print("%s · 블로그 %d개 글 %d개 · 놀거리 %d개 · index.html 본문 %d자"
          % (out, len(blogs), total, len(PLAY), chars))
    for w in warn:
        print("  ⚠ %s" % w)


if __name__ == "__main__":
    main()
