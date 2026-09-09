#!/usr/bin/env python3
"""apex 매거진 홈이 읽을 feed.json 을 만든다.

apex 는 Hugo 가 아니라 정적 HTML 한 장이다. 화면은 디자이너가 만들고, 이 스크립트는
데이터만 낸다. 그래야 디자인 작업과 안 부딪힌다.

블로그는 각자 Hugo 가 내는 index.xml(RSS)을 읽는다. 심심풀이는 글이 없어서 게임과
도구 목록을 코드에 둔다.

돈의문법과 여행의밑줄은 HTTPS 인증서가 아직 안 붙어서 http 로 읽는다. 이 파일이
서버(GitHub Actions)에서 돌아 결과만 https 로 서빙되므로 혼합 콘텐츠 문제는 없다.
인증서가 붙으면 http 를 지우면 된다.
"""
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

PER_BLOG = 5
TIMEOUT = 20

BLOGS = [
    ("hyetaek",   "혜택줍줍",   "#0e9f6e", "blog",      "정부 지원금과 세금 환급을 매일 정리합니다"),
    ("chagok",    "차곡차곡",   "#0e9f6e", "car",       "자동차세, 보험료, 검사 기한을 챙기는 곳입니다"),
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
            "tagline": "심심할 때 눌러보는 것들",
            "items": [{"kind": k, "name": n, "url": SIMSIM + u} for k, n, u in PLAY],
        },
        "profile": PROFILE,
        "links": LINKS,
    }

    out = sys.argv[1] if len(sys.argv) > 1 else "feed.json"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    total = sum(len(b["posts"]) for b in blogs)
    print("%s · 블로그 %d개 글 %d개 · 놀거리 %d개"
          % (out, len(blogs), total, len(PLAY)))
    for w in warn:
        print("  ⚠ %s" % w)


if __name__ == "__main__":
    main()
