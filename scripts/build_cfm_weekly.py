#!/usr/bin/env python3
import json
import re
import sys
from datetime import date, datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.churchofjesuschrist.org"
MANUAL_PATH = "/study/manual/come-follow-me-for-home-and-church-old-testament-2026/{week:02d}?lang=eng"

OUT_JSON = "data/come_follow_me_this_week.json"


def iso_week_number(d: date) -> int:
    # ISO week can be 1..53. Your manual is 1..52.
    wk = d.isocalendar().week
    return min(wk, 52)


def absolute_url(u: str) -> str:
    if not u:
        return ""
    return urljoin(BASE, u)


def pick_first_image(soup: BeautifulSoup) -> str:
    """
    The page often uses a <figure> with an <img> (sometimes id="img1" or "figure1_img1").
    We'll try common patterns and fall back to first <img>.
    """
    # 1) First figure image
    fig = soup.find("figure")
    if fig:
        img = fig.find("img")
        if img and img.get("src"):
            return absolute_url(img["src"])

    # 2) Common ids
    for img_id in ["img1", "figure1_img1"]:
        img = soup.find("img", {"id": img_id})
        if img and img.get("src"):
            return absolute_url(img["src"])

    # 3) Any img with a src
    img = soup.find("img", src=True)
    if img and img.get("src"):
        return absolute_url(img["src"])

    return ""


def get_text_or_empty(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


def scrape_week(week: int) -> dict:
    url = BASE + MANUAL_PATH.format(week=week)

    r = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; SnowCanyonWardBot/1.0; +https://github.com/kdidso)"
        },
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    # Small red heading: seen as <p class="title-number" id="title_number1">...</p>
    small_heading = soup.select_one("p.title-number") or soup.select_one("#title_number1")

    # Big heading: <h1 id="title1">...</h1> (or first h1)
    big_heading = soup.select_one("h1#title1") or soup.find("h1")

    image_url = pick_first_image(soup)

    # If the image is present but lazy-loaded via srcset only, try to grab a decent srcset candidate
    if not image_url:
        img = soup.find("img", srcset=True)
        if img and img.get("srcset"):
            # pick the largest width in srcset
            candidates = []
            for part in img["srcset"].split(","):
                part = part.strip()
                m = re.match(r"(\S+)\s+(\d+)w", part)
                if m:
                    candidates.append((int(m.group(2)), m.group(1)))
            if candidates:
                candidates.sort()
                image_url = absolute_url(candidates[-1][1])

    data = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "week_number": week,
        "source_url": url,
        "image_url": image_url,
        "small_heading": get_text_or_empty(small_heading),
        "big_heading": get_text_or_empty(big_heading),
    }

    return data


def main():
    today = date.today()
    week = iso_week_number(today)

    try:
        payload = scrape_week(week)
    except Exception as e:
        print(f"ERROR scraping week {week}: {e}", file=sys.stderr)
        raise

    # Ensure output dir exists
    import os

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT_JSON} for week {week}: {payload['big_heading']}")


if __name__ == "__main__":
    main()
