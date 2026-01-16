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
    Prefer the header hero image first (img#img1).
    Use the LARGEST srcset candidate if available (best quality).
    If not found, fall back to first figure image, then any img.
    """

    img = soup.select_one("img#img1")
    if img:
        # Prefer largest srcset candidate (best quality)
        srcset = img.get("srcset", "")
        if srcset:
            candidates = []
            for part in srcset.split(","):
                part = part.strip()
                m = re.match(r"(\S+)\s+(\d+)w", part)
                if m:
                    candidates.append((int(m.group(2)), m.group(1)))
            if candidates:
                candidates.sort(key=lambda x: x[0])
                return absolute_url(candidates[-1][1])

        # Fallback to src if no srcset
        src = img.get("src", "")
        if src:
            return absolute_url(src)

    # 2) Fallback: first <figure> image
    fig_img = soup.select_one("figure img")
    if fig_img:
        # same idea: prefer srcset if present
        srcset = fig_img.get("srcset", "")
        if srcset:
            candidates = []
            for part in srcset.split(","):
                part = part.strip()
                m = re.match(r"(\S+)\s+(\d+)w", part)
                if m:
                    candidates.append((int(m.group(2)), m.group(1)))
            if candidates:
                candidates.sort(key=lambda x: x[0])
                return absolute_url(candidates[-1][1])

        src = fig_img.get("src", "")
        if src:
            return absolute_url(src)

    # 3) Fallback: any img
    any_img = soup.find("img")
    if any_img:
        srcset = any_img.get("srcset", "")
        if srcset:
            candidates = []
            for part in srcset.split(","):
                part = part.strip()
                m = re.match(r"(\S+)\s+(\d+)w", part)
                if m:
                    candidates.append((int(m.group(2)), m.group(1)))
            if candidates:
                candidates.sort(key=lambda x: x[0])
                return absolute_url(candidates[-1][1])

        src = any_img.get("src", "")
        if src:
            return absolute_url(src)

    return ""


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

    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    # ---- SCRAPE PARTS ----
    small_heading_el = soup.select_one("p.title-number")
    big_heading_el = soup.select_one("h1")

    small_heading = get_text_or_empty(small_heading_el)
    big_heading = get_text_or_empty(big_heading_el)

    image_url = pick_first_image(soup)

    # ---- FALLBACK IMAGE (only if pick_first_image returned nothing) ----
    if not image_url:
        img = soup.find("img", srcset=True)
        if img and img.get("srcset"):
            candidates = []
            for part in img["srcset"].split(","):
                part = part.strip()
                m = re.match(r"(\S+)\s+(\d+)w", part)
                if m:
                    candidates.append((int(m.group(2)), m.group(1)))
            if candidates:
                candidates.sort()
                image_url = absolute_url(candidates[-1][1])

    # ---- RETURN DATA (single, final return) ----
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "week_number": week,
        "source_url": url,
        "image_url": image_url,
        "small_heading": small_heading,
        "big_heading": big_heading,
    }


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
