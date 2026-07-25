#!/usr/bin/env python3
"""
scripts/update.py

هر بار که اجرا میشه: قیمت‌ها رو از tgju.org اسکرپ می‌کنه، به آرشیو تاریخی اضافه می‌کنه،
README و نمودار SVG و بج (badge) رو آپدیت می‌کنه.

نکته‌ی مهم: هر آیتم زیر یه صفحه‌ی profile جدا روی tgju داره. فقط اسلاگ
price_dollar_rl تست و تأیید شده. بقیه (geram18, sekee, ons) رو خودت با
curl + grep چک کن؛ اگه اسلاگ فرق داشت، همین‌جا توی PAGES اصلاحش کن.
"""

import csv
import json
import os
import re
import sys
import time as time_module
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

PAGES = [
    {"key": "usd", "url": "https://www.tgju.org/profile/price_dollar_rl", "label": "دلار (ریال)"},
    {"key": "gram18", "url": "https://www.tgju.org/profile/geram18", "label": "طلای ۱۸ عیار (ریال)"},
    {"key": "sekkeh", "url": "https://www.tgju.org/profile/sekee", "label": "سکه امامی (ریال)"},
    {"key": "ounce", "url": "https://www.tgju.org/profile/ons", "label": "اونس جهانی طلا (دلار)"},
]

SELECTOR = 'span.price[data-col="info.last_trade.PDrCotVal"]'
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
KEYS = [p["key"] for p in PAGES]


def fetch_price(page):
    res = requests.get(page["url"], headers={"User-Agent": USER_AGENT}, timeout=15)
    if res.status_code != 200:
        raise RuntimeError(f'{page["label"]} ({page["url"]}) → HTTP {res.status_code}')

    soup = BeautifulSoup(res.text, "html.parser")
    el = soup.select_one(SELECTOR)
    if el is None or not el.text.strip():
        raise RuntimeError(
            f'{page["label"]}: سلکتور "{SELECTOR}" چیزی پیدا نکرد. '
            "احتمالاً اسلاگ URL یا ساختار صفحه عوض شده."
        )

    raw = el.text.strip()
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        raise RuntimeError(f'{page["label"]}: مقدار "{raw}" عدد معتبر نیست.')


def fetch_latest():
    results = {}
    for page in PAGES:
        try:
            results[page["key"]] = fetch_price(page)
        except RuntimeError as err:
            print(f"⚠️ {err}", file=sys.stderr)
            results[page["key"]] = None
        time_module.sleep(1.5)  # مکث کوتاه، فشار کمتر به سرور
    return results


def tehran_time(dt):
    # ساعت به وقت تهران (Asia/Tehran)، فرمت HH:MM
    return dt.astimezone(ZoneInfo("Asia/Tehran")).strftime("%H:%M")


def to_row(data):
    now = datetime.now(timezone.utc)
    row = {
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": int(now.timestamp()),
        "time": tehran_time(now),
    }
    for page in PAGES:
        row[page["key"]] = data.get(page["key"], "")
    return row


def append_to_history(row):
    csv_path = os.path.join("data", "history.csv")
    os.makedirs("data", exist_ok=True)
    is_new = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["date", "timestamp"] + KEYS)
        writer.writerow([row["date"], row["timestamp"]] + [row[k] for k in KEYS])
    return csv_path


def fa(n):
    try:
        return f"{float(n):,.0f}"
    except (TypeError, ValueError):
        return str(n)


def update_readme(row):
    readme_path = "README.md"
    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()

    block = f"""<!-- LATEST:START -->
_آخرین بروزرسانی: {row['date']} — ساعت {row['time']} به وقت تهران_

| شاخص | مقدار | ساعت بروزرسانی |
|---|---|---|
| 💵 دلار (بازار آزاد) | {fa(row['usd'])} ریال | {row['time']} |
| 🥇 اونس جهانی طلا | {fa(row['ounce'])} دلار | {row['time']} |
| 🟡 طلای ۱۸ عیار (هر گرم) | {fa(row['gram18'])} ریال | {row['time']} |
| 🪙 سکه امامی | {fa(row['sekkeh'])} ریال | {row['time']} |

![USD Trend](assets/usd-trend.svg)
![Gold Trend](assets/gold-trend.svg)
<!-- LATEST:END -->"""

    readme = re.sub(r"<!-- LATEST:START -->[\s\S]*<!-- LATEST:END -->", block, readme)
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme)


def update_badge(row):
    with open("data/badge.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "schemaVersion": 1,
                "label": "USD/IRR",
                "message": f"{fa(row['usd'])} rial",
                "color": "brightgreen",
            },
            f,
            ensure_ascii=False,
        )


def sparkline(values, color):
    w, h, pad = 640, 160, 12
    vmin, vmax = min(values), max(values)
    rng = (vmax - vmin) or 1
    n = len(values)
    points = []
    for i, v in enumerate(values):
        x = pad + (i * (w - 2 * pad)) / max(n - 1, 1)
        y = h - pad - ((v - vmin) / rng) * (h - 2 * pad)
        points.append(f"{x:.1f},{y:.1f}")
    points_str = " ".join(points)
    last = values[-1]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="sans-serif">\n'
        f'  <polyline fill="none" stroke="{color}" stroke-width="2.5" points="{points_str}" />\n'
        f'  <text x="{w - pad}" y="16" text-anchor="end" font-size="14" fill="{color}">{last:,.0f}</text>\n'
        f"</svg>"
    )


def generate_charts(csv_path):
    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))[1:]  # بدون هدر
    rows = rows[-60:]
    if len(rows) < 2:
        return
    os.makedirs("assets", exist_ok=True)

    def col(idx):
        vals = []
        for r in rows:
            try:
                vals.append(float(r[idx]))
            except (ValueError, IndexError):
                pass
        return vals

    # ترتیب ستون‌ها: date,timestamp,usd,gram18,sekkeh,ounce
    usd = col(2)
    gold = col(3)

    if len(usd) > 1:
        with open("assets/usd-trend.svg", "w", encoding="utf-8") as f:
            f.write(sparkline(usd, "#e63946"))
    if len(gold) > 1:
        with open("assets/gold-trend.svg", "w", encoding="utf-8") as f:
            f.write(sparkline(gold, "#d4a017"))


def main():
    data = fetch_latest()
    row = to_row(data)
    csv_path = append_to_history(row)
    update_readme(row)
    update_badge(row)
    generate_charts(csv_path)
    print("✅ بروزرسانی انجام شد:", row)


if __name__ == "__main__":
    main()
