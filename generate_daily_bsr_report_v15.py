#!/usr/bin/env python3
"""
Vinci Books — Daily BSR & Revenue Report Generator (v2)
========================================================
Pulls live data from Publisher Champ API + Supabase BSR data via MCP.
Generates a premium executive HTML dashboard.

Usage:
    python3 generate_daily_bsr_report_v2.py              # Use cached data
    python3 generate_daily_bsr_report_v2.py --extract    # Pull fresh data from APIs
"""

import json
import sys
import os
import time
import base64
import statistics
import subprocess
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict

try:
    import requests
except ImportError:
    print("Installing requests...")
    os.system("pip3 install requests")
    import requests

# ─── Configuration ───────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data_v2"
SNAPSHOTS_DIR = SCRIPT_DIR / "snapshots"
OUTPUT_FILE = SCRIPT_DIR / "Vinci_Daily_BSR_Report_v2.html"

DATA_DIR.mkdir(exist_ok=True)
SNAPSHOTS_DIR.mkdir(exist_ok=True)

# Publisher Champ API
PC_API_KEY = "60cff9fa-ca6c-4d3f-9f9e-bca9cee1539f"
PC_ACCOUNT_ID = "4ae94411-df98-4441-b57a-dabbbebde761"
PC_BASE_URL = "https://www.publisherchamp.com/api/v1"

# Supabase (via MCP)
SUPABASE_PROJECT_ID = "objjtsqeselgjwtmzpsz"

# Brand colors
BRAND_BLACK = "#000000"
BRAND_GOLD = "#F5C518"
BRAND_WHITE = "#FFFFFF"

# Readthrough benchmarks
RT_BENCHMARK_BOOK1_TO_2 = 50  # 50%+ is good
RT_BENCHMARK_SUBSEQUENT = 70  # 70%+ between subsequent books
RT_BENCHMARK_AFTER_BOOK2 = 80  # 80%+ after Book 2 is excellent
RT_AMBER_THRESHOLD = 10  # Within 10 points of benchmark = amber


# ─── API Data Extraction ─────────────────────────────────────────────────────

def fetch_publisher_champ(endpoint, start_date, end_date, max_retries=3):
    """Fetch data from Publisher Champ API with retry logic."""
    url = f"{PC_BASE_URL}/{endpoint}/"
    params = {
        "api_key": PC_API_KEY,
        "account_id": PC_ACCOUNT_ID,
        "start_date": start_date,
        "end_date": end_date,
    }
    
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=300)
            if resp.status_code == 200:
                return resp.json()
            else:
                print(f"  ⚠ HTTP {resp.status_code} on attempt {attempt+1}")
        except requests.exceptions.Timeout:
            print(f"  ⚠ Timeout on attempt {attempt+1}")
        except Exception as e:
            print(f"  ⚠ Error on attempt {attempt+1}: {e}")
        
        if attempt < max_retries - 1:
            time.sleep(5)
    
    return None


def extract_all_data():
    """Pull fresh data from all sources."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    ninety_days_ago = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
    
    print(f"📅 Date range: 30-day ({thirty_days_ago} → {today}), 90-day ({ninety_days_ago} → {today})")
    
    # 30-day book stats
    print("📚 Fetching 30-day book stats...")
    data_30 = fetch_publisher_champ("bookStatsAPI", thirty_days_ago, today)
    if data_30:
        with open(DATA_DIR / "pc_30day.json", "w") as f:
            json.dump(data_30, f)
        print(f"   → {len(data_30.get('table_data', []))} books")
    
    time.sleep(3)
    
    # 90-day book stats
    print("📚 Fetching 90-day book stats...")
    data_90 = fetch_publisher_champ("bookStatsAPI", ninety_days_ago, today)
    if data_90:
        with open(DATA_DIR / "pc_90day.json", "w") as f:
            json.dump(data_90, f)
        print(f"   → {len(data_90.get('table_data', []))} books")
    
    time.sleep(3)
    
    # 30-day country stats
    print("🌍 Fetching 30-day country stats...")
    country_30 = fetch_publisher_champ("countryStatsAPI", thirty_days_ago, today)
    if country_30:
        with open(DATA_DIR / "pc_country_30day.json", "w") as f:
            json.dump(country_30, f)
    
    time.sleep(3)
    
    # 90-day country stats
    print("🌍 Fetching 90-day country stats...")
    country_90 = fetch_publisher_champ("countryStatsAPI", ninety_days_ago, today)
    if country_90:
        with open(DATA_DIR / "pc_country_90day.json", "w") as f:
            json.dump(country_90, f)
    
    time.sleep(3)
    
    # 30-day author stats
    print("✍️ Fetching 30-day author stats...")
    author_30 = fetch_publisher_champ("authorStatsAPI", thirty_days_ago, today)
    if author_30:
        with open(DATA_DIR / "pc_author_30day.json", "w") as f:
            json.dump(author_30, f)
        print(f"   → {len(author_30.get('table_data', {}))} authors")
    
    time.sleep(3)
    
    # 30-day ads monitoring
    print("📢 Fetching 30-day ads monitoring...")
    ads_30 = fetch_publisher_champ("adsMonitoringAPI", thirty_days_ago, today)
    if ads_30:
        with open(DATA_DIR / "pc_ads_30day.json", "w") as f:
            json.dump(ads_30, f)
    
    # YTD 2026 book stats
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ytd_start = datetime.now(timezone.utc).strftime("%Y-01-01")
    last_year_end = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")
    last_year_start = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-01-01")
    
    print("📅 Fetching YTD 2026 book stats...")
    data_ytd = fetch_publisher_champ("bookStatsAPI", ytd_start, today_str)
    if data_ytd:
        with open(DATA_DIR / "pc_ytd2026.json", "w") as f:
            json.dump(data_ytd, f)
        print(f"   → {len(data_ytd.get('table_data', []))} books")
    
    time.sleep(3)
    
    # YTD last year same period
    print("📅 Fetching YTD 2025 same-period book stats...")
    data_ytd_ly = fetch_publisher_champ("bookStatsAPI", last_year_start, last_year_end)
    if data_ytd_ly:
        with open(DATA_DIR / "pc_ytd2025_sameperiod.json", "w") as f:
            json.dump(data_ytd_ly, f)
        print(f"   → {len(data_ytd_ly.get('table_data', []))} books")
    
    time.sleep(3)
    
    # FY 2025 (only fetch if file doesn't exist or it's a new year)
    fy2025_file = DATA_DIR / "pc_fy2025.json"
    if not fy2025_file.exists():
        print("📅 Fetching FY 2025 book stats...")
        data_fy25 = fetch_publisher_champ("bookStatsAPI", "2025-01-01", "2025-12-31")
        if data_fy25:
            with open(fy2025_file, "w") as f:
                json.dump(data_fy25, f)
            print(f"   → {len(data_fy25.get('table_data', []))} books")
        time.sleep(3)
    else:
        print("📅 FY 2025 data already cached, skipping fetch")
    
    # FY 2024 (only fetch if file doesn't exist)
    fy2024_file = DATA_DIR / "pc_fy2024.json"
    if not fy2024_file.exists():
        print("📅 Fetching FY 2024 book stats...")
        data_fy24 = fetch_publisher_champ("bookStatsAPI", "2024-01-01", "2024-12-31")
        if data_fy24:
            with open(fy2024_file, "w") as f:
                json.dump(data_fy24, f)
            print(f"   → {len(data_fy24.get('table_data', []))} books")
        time.sleep(3)
    else:
        print("📅 FY 2024 data already cached, skipping fetch")
    
    # MTD 2026 (Month to Date: 1st of current month to today)
    mtd_start = datetime.now(timezone.utc).strftime("%Y-%m-01")
    print(f"📅 Fetching MTD 2026 book stats ({mtd_start} → {today_str})...")
    data_mtd = fetch_publisher_champ("bookStatsAPI", mtd_start, today_str)
    if data_mtd:
        with open(DATA_DIR / "pc_mtd2026.json", "w") as f:
            json.dump(data_mtd, f)
        print(f"   → {len(data_mtd.get('table_data', []))} books")
    time.sleep(3)
    
    # MTD last year same period
    from datetime import date
    ly_mtd_start = (date.today().replace(year=date.today().year - 1, day=1)).strftime("%Y-%m-%d")
    ly_mtd_end = (date.today().replace(year=date.today().year - 1)).strftime("%Y-%m-%d")
    print(f"📅 Fetching MTD 2025 same-period book stats ({ly_mtd_start} → {ly_mtd_end})...")
    data_mtd_ly = fetch_publisher_champ("bookStatsAPI", ly_mtd_start, ly_mtd_end)
    if data_mtd_ly:
        with open(DATA_DIR / "pc_mtd2025.json", "w") as f:
            json.dump(data_mtd_ly, f)
        print(f"   → {len(data_mtd_ly.get('table_data', []))} books")
    time.sleep(3)
    
    # BSR data from Supabase via MCP
    print("📊 Extracting BSR data from Supabase...")
    extract_bsr_data()
    
    print("✅ All data extracted successfully!")


def extract_bsr_data():
    """Extract BSR data from Supabase via MCP."""
    bsr_file = DATA_DIR / "all_bsr_data.json"
    # Check if we have BSR data from v1
    v1_bsr = SCRIPT_DIR / "data" / "all_bsr_data.json"
    if v1_bsr.exists() and not bsr_file.exists():
        import shutil
        shutil.copy(v1_bsr, bsr_file)
        print("   → Copied BSR data from v1")
    elif not bsr_file.exists():
        print("   ⚠ No BSR data available. Run v1 extraction first or use MCP.")


# ─── Data Loading ────────────────────────────────────────────────────────────

def load_book_data(period="30day"):
    """Load Publisher Champ book stats."""
    filepath = DATA_DIR / f"pc_{period}.json"
    if not filepath.exists():
        print(f"⚠ Missing {filepath}")
        return []
    with open(filepath) as f:
        data = json.load(f)
    return data.get("table_data", [])


def load_country_data(period="30day"):
    """Load Publisher Champ country stats."""
    filepath = DATA_DIR / f"pc_country_{period}.json"
    if not filepath.exists():
        return {}
    with open(filepath) as f:
        data = json.load(f)
    return data


def load_author_data():
    """Load Publisher Champ author stats."""
    filepath = DATA_DIR / "pc_author_30day.json"
    if not filepath.exists():
        return {}
    with open(filepath) as f:
        data = json.load(f)
    return data.get("table_data", {})


def load_bsr_data():
    """Load BSR data from Supabase extraction."""
    filepath = DATA_DIR / "all_bsr_data.json"
    if not filepath.exists():
        # Try v1 location
        v1_path = SCRIPT_DIR / "data" / "all_bsr_data.json"
        if v1_path.exists():
            filepath = v1_path
        else:
            return []
    with open(filepath) as f:
        records = json.load(f)
    return [r for r in records if r.get("record_date") and r["record_date"] >= "2026-05-16"]


# ─── Analysis Functions ──────────────────────────────────────────────────────

def compute_portfolio_overview(books_30, books_90, country_30):
    """Compute top-level portfolio metrics with period comparison."""
    # 30-day totals
    total_gross_30 = sum(b["gross_royalty"] for b in books_30)
    total_spend_30 = sum(b["spending"] for b in books_30)
    total_net_30 = total_gross_30 - total_spend_30
    total_kenp_30 = sum(b["total_reads"] for b in books_30)
    total_units_30 = sum(b["ebooks_paid_sold"] for b in books_30)
    
    # 90-day totals (for comparison - divide by 3 for monthly average)
    total_gross_90 = sum(b["gross_royalty"] for b in books_90)
    total_spend_90 = sum(b["spending"] for b in books_90)
    total_net_90 = total_gross_90 - total_spend_90
    total_kenp_90 = sum(b["total_reads"] for b in books_90)
    
    # Monthly averages from 90-day
    avg_gross_monthly = total_gross_90 / 3
    avg_net_monthly = total_net_90 / 3
    avg_kenp_monthly = total_kenp_90 / 3
    
    # Period comparison (30-day vs monthly average)
    gross_change = ((total_gross_30 - avg_gross_monthly) / avg_gross_monthly * 100) if avg_gross_monthly else 0
    net_change = ((total_net_30 - avg_net_monthly) / avg_net_monthly * 100) if avg_net_monthly else 0
    kenp_change = ((total_kenp_30 - avg_kenp_monthly) / avg_kenp_monthly * 100) if avg_kenp_monthly else 0
    
    # Country breakdown from API
    countries = country_30.get("countries", {})
    global_earnings = country_30.get("global_earnings", 0)
    global_spend = country_30.get("global_spend", 0)
    
    return {
        "total_gross_30": total_gross_30,
        "total_spend_30": total_spend_30,
        "total_net_30": total_net_30,
        "total_kenp_30": total_kenp_30,
        "total_units_30": total_units_30,
        "total_books": len(books_30),
        "gross_change_pct": gross_change,
        "net_change_pct": net_change,
        "kenp_change_pct": kenp_change,
        "roi_30": (total_gross_30 / total_spend_30 * 100) if total_spend_30 > 0 else float('inf'),
        "countries": countries,
        "currency": country_30.get("converted_currency", "GBP"),
    }


def compute_portfolio_pulse(bsr_data, readthrough_90, books_30, asin_to_author=None):
    """Compute the 6 Portfolio Pulse KPIs."""
    # ── 1-3: BSR Top 10K counts per market ──
    records = [r for r in bsr_data if r.get('record_date')]
    by_date = defaultdict(list)
    for r in records:
        by_date[r['record_date']].append(r)
    
    us_top10k = uk_top10k = de_top10k = 0
    top_mover = None
    
    if by_date:
        dates = sorted(by_date.keys())
        latest_date = dates[-1]
        prev_date = dates[-2] if len(dates) >= 2 else None
        latest_recs = by_date[latest_date]
        
        us_top10k = sum(1 for r in latest_recs if r.get('bsr_us') and 0 < r['bsr_us'] <= 10000)
        uk_top10k = sum(1 for r in latest_recs if r.get('bsr_uk') and 0 < r['bsr_uk'] <= 10000)
        de_top10k = sum(1 for r in latest_recs if r.get('bsr_de') and 0 < r['bsr_de'] <= 10000)
        
        # ── 6: Top Mover of the Day ──
        # Build ASIN -> book lookup from books_30 for cover image
        asin_to_book = {b.get('asin', ''): b for b in books_30 if b.get('asin')}
        
        if prev_date:
            prev_recs = by_date[prev_date]
            prev_map = {}
            for r in prev_recs:
                key = r.get('title_id') or r.get('asin')
                if key:
                    prev_map[key] = r.get('bsr_us', 0)
            
            movers = []
            for r in latest_recs:
                key = r.get('title_id') or r.get('asin')
                if key and key in prev_map:
                    prev_bsr = prev_map[key]
                    curr_bsr = r.get('bsr_us', 0)
                    if prev_bsr and curr_bsr and prev_bsr > 0 and curr_bsr > 0:
                        improvement = prev_bsr - curr_bsr
                        if improvement > 0:
                            # Try to find cover image and author from books_30
                            asin = r.get('asin', '')
                            book_info = asin_to_book.get(asin, {})
                            # Also try to match by title if ASIN not found
                            if not book_info:
                                title_lower = r.get('title', '').lower()
                                for b in books_30:
                                    if b.get('title', '').lower() == title_lower:
                                        book_info = b
                                        break
                            # Look up author
                            author_name = ''
                            if asin_to_author:
                                author_name = asin_to_author.get(asin, '')
                                if not author_name and book_info.get('asin'):
                                    author_name = asin_to_author.get(book_info['asin'], '')
                            movers.append({
                                'title': r.get('title', 'Unknown'),
                                'asin': asin,
                                'author': author_name,
                                'prev_bsr': prev_bsr,
                                'curr_bsr': curr_bsr,
                                'improvement': improvement,
                                'cover_url': book_info.get('image', ''),
                            })
            movers.sort(key=lambda x: -x['improvement'])
            top_mover = movers[0] if movers else None
    
    # ── 4: Portfolio Avg B1→B2 Readthrough ──
    b1_to_b2_rates = [r['book1_to_2'] for r in readthrough_90 if r.get('book1_to_2', 0) > 0]
    avg_b1_to_b2 = statistics.mean(b1_to_b2_rates) if b1_to_b2_rates else 0
    
    # ── 5: Organic Revenue % ──
    total_gross = sum(b['gross_royalty'] for b in books_30)
    organic_gross = sum(b['gross_royalty'] for b in books_30 if b.get('spending', 0) == 0)
    organic_pct = (organic_gross / total_gross * 100) if total_gross > 0 else 0
    
    return {
        'us_top10k': us_top10k,
        'uk_top10k': uk_top10k,
        'de_top10k': de_top10k,
        'avg_b1_to_b2': avg_b1_to_b2,
        'organic_pct': organic_pct,
        'top_mover': top_mover,
        'latest_date': dates[-1] if by_date else 'N/A',
    }


def compute_author_economics(author_data, books_30):
    """Compute author-level P&L."""
    authors = []
    
    # Build spending lookup from book data (author stats don't include spend)
    # We need to map books to authors
    book_spend = {}
    for b in books_30:
        book_spend[b["asin"]] = b["spending"]
    
    for author_name, books_dict in author_data.items():
        if not isinstance(books_dict, dict):
            continue
        
        total_gross = 0
        total_reads = 0
        total_spend = 0
        book_count = 0
        
        for book_title, book_info in books_dict.items():
            if not isinstance(book_info, dict):
                continue
            book_count += 1
            total_gross += book_info.get("book_royalty", 0) + book_info.get("read_royalty", 0)
            total_reads += book_info.get("reads", 0)
            asin = book_info.get("asin", "")
            total_spend += book_spend.get(asin, 0)
        
        if book_count == 0:
            continue
        
        net = total_gross - total_spend
        roi = (total_gross / total_spend * 100) if total_spend > 0 else float('inf')
        
        authors.append({
            "name": author_name,
            "books": book_count,
            "gross": total_gross,
            "spend": total_spend,
            "net": net,
            "roi": roi,
            "kenp": total_reads,
        })
    
    authors.sort(key=lambda x: -x["gross"])
    return authors


def compute_author_economics_from_books(books_data, asin_to_author):
    """Compute author-level P&L from book-level data (used for 90-day view)."""
    author_map = defaultdict(lambda: {"gross": 0, "spend": 0, "kenp": 0, "units": 0, "book_asins": set()})
    
    for b in books_data:
        asin = b.get("asin", "")
        author = asin_to_author.get(asin, "")
        if not author:
            continue
        author_map[author]["gross"] += b.get("gross_royalty", 0)
        author_map[author]["spend"] += b.get("spending", 0)
        author_map[author]["kenp"] += b.get("total_reads", 0)
        author_map[author]["units"] += b.get("ebooks_paid_sold", 0)
        author_map[author]["book_asins"].add(asin)
    
    authors = []
    for name, d in author_map.items():
        net = d["gross"] - d["spend"]
        roi = (d["gross"] / d["spend"] * 100) if d["spend"] > 0 else float('inf')
        authors.append({
            "name": name,
            "books": len(d["book_asins"]),
            "gross": d["gross"],
            "spend": d["spend"],
            "net": net,
            "roi": roi,
            "kenp": d["kenp"],
        })
    
    authors.sort(key=lambda x: -x["gross"])
    return authors


def build_asin_to_author_map():
    """Build a mapping of ASIN -> author name from author stats data.
    
    Also builds a title-normalised fallback so that books whose ASIN in the
    author stats is a print ISBN (e.g. 1949913139) rather than a B0… ASIN can
    still be resolved when the 90-day stats carry the real Amazon ASIN.
    """
    author_data = load_author_data()
    asin_to_author = {}
    title_to_author = {}  # normalised title -> author (fallback)
    for author_name, books_dict in author_data.items():
        if not isinstance(books_dict, dict):
            continue
        for book_title, book_info in books_dict.items():
            if isinstance(book_info, dict) and "asin" in book_info:
                asin_to_author[book_info["asin"]] = author_name
            # Always index by normalised title as fallback
            norm = book_title.lower().strip()
            if norm and author_name not in title_to_author.get(norm, ""):
                title_to_author[norm] = author_name
    # Second pass: for every book in 90-day data whose ASIN is not yet mapped,
    # try to resolve via title match
    try:
        import json as _json
        _books_90_path = DATA_DIR / "pc_90day.json"
        if _books_90_path.exists():
            _books_90 = _json.load(open(_books_90_path)).get("table_data", [])
            for b in _books_90:
                asin = b.get("asin", "")
                if asin and asin not in asin_to_author:
                    norm = b.get("title", "").lower().strip()
                    if norm in title_to_author:
                        asin_to_author[asin] = title_to_author[norm]
    except Exception:
        pass
    return asin_to_author


DE_SERIES_PREFIXES = ("Der ", "Die ", "Das ")


def is_boxset_or_omnibus(title):
    """Return True if a book title looks like a box set, omnibus, or collection."""
    import re
    t = title.lower()
    keywords = [
        "box set", "boxed set", "boxset", "box-set",
        "omnibus", "collection", "complete series",
        "complete collection", "the complete",
        "trilogy", "duology", "quadrilogy", "pentalogy",
    ]
    for kw in keywords:
        if kw in t:
            return True
    if re.search(r'books?\s+\d+\s*[-–to]+\s*\d+', t):
        return True
    return False


def is_translation_series(series_name):
    """Return True if this series name looks like a German/translated edition."""
    return series_name.startswith(DE_SERIES_PREFIXES)


# Keywords that indicate a book is a prequel, novella, or short story
# rather than a full-length novel in the main series sequence.
PREQUEL_NOVELLA_KEYWORDS = [
    "prequel", "novella", "short story", "short stories",
    "origin story", "origins story", "prelude", "prologue",
    "bonus story", "companion novella", "companion story",
    "starter", "sampler", "free story", "free read",
]

def is_prequel_or_novella(title):
    """Return True if a book title indicates it is a prequel, novella, or short story.
    
    Used to skip non-full-length entries when selecting Book 1 for readthrough analysis.
    Note: 'starter library' or 'starter box set' are box sets, handled separately.
    """
    t = title.lower()
    for kw in PREQUEL_NOVELLA_KEYWORDS:
        if kw in t:
            return True
    return False


def build_series_composition(books_data, en_series_name):
    """Build a composition annotation for a series: EN titles, box sets, DE translations."""
    import re
    # Count EN individual books in this exact series
    en_books = set()
    boxsets = set()
    # Find German counterpart series by looking for series with similar keywords
    # Strategy: any series tagged as a translation prefix that contains words from the EN series name
    en_words = set(en_series_name.lower().replace("'", "").split())
    de_books = set()
    
    for b in books_data:
        title = b.get("title", "")
        for s in b.get("all_series", []):
            if not s.startswith("#"):
                continue
            parts = s.split(" in ", 1)
            if len(parts) != 2:
                continue
            sname = parts[1]
            try:
                num = int(parts[0][1:])
            except ValueError:
                continue
            
            if sname == en_series_name:
                if is_boxset_or_omnibus(title):
                    boxsets.add(b.get("asin", title))
                else:
                    en_books.add(b.get("asin", title))
            elif is_translation_series(sname):
                # Check if this DE series is related to the EN series
                de_words = set(sname.lower().replace("'", "").replace("-", " ").split())
                # Remove German articles
                de_words -= {"der", "die", "das", "reihe", "serie", "krimis", "thriller"}
                overlap = en_words & de_words
                if overlap or sname.replace("Die ", "").replace("Der ", "").replace("Das ", "").lower() in en_series_name.lower():
                    de_books.add(b.get("asin", title))
    
    parts_annotation = []
    if en_books:
        parts_annotation.append(f"{len(en_books)} EN title{'s' if len(en_books) != 1 else ''}")
    if de_books:
        parts_annotation.append(f"{len(de_books)} DE translation{'s' if len(de_books) != 1 else ''}")
    if boxsets:
        parts_annotation.append(f"{len(boxsets)} box set{'s' if len(boxsets) != 1 else ''}")
    return " · ".join(parts_annotation) if parts_annotation else ""


def compute_series_economics(books_data, period_label="30-day", asin_to_author=None):
    """Compute series-level P&L from book stats.
    
    P&L includes ALL editions (individual EN books + box sets + DE/translated editions).
    The 'books' list for readthrough purposes contains only individual EN-numbered books.
    """
    if asin_to_author is None:
        asin_to_author = {}
    
    # Map: series_name -> list of individual EN books (for readthrough)
    series_rt_books = defaultdict(list)
    # Map: series_name -> full P&L totals (including all editions)
    series_pnl = defaultdict(lambda: {"gross": 0, "spend": 0, "kenp": 0, "units": 0})
    # Map: English series name -> German/translated series name (for composition annotation)
    en_to_de_series = defaultdict(set)
    # Map: English series name -> box set ASINs
    en_to_boxsets = defaultdict(set)
    
    # First pass: identify all series and their types
    all_series_names = set()
    for b in books_data:
        for s in b.get("all_series", []):
            if s.startswith("#"):
                parts = s.split(" in ", 1)
                if len(parts) == 2:
                    all_series_names.add(parts[1])
    
    # Build a map of DE series -> potential EN parent series
    de_to_en = {}
    for sname in all_series_names:
        if is_translation_series(sname):
            # Strip German article prefix and normalise
            stripped = sname
            for prefix in ("Der ", "Die ", "Das "):
                stripped = stripped.replace(prefix, "")
            # Find best matching EN series
            stripped_lower = stripped.lower().replace("-", " ").replace("'", "")
            best_match = None
            best_score = 0
            for en_name in all_series_names:
                if is_translation_series(en_name):
                    continue
                en_lower = en_name.lower().replace("'", "")
                # Check if stripped DE name is contained in EN name or vice versa
                if stripped_lower in en_lower or en_lower in stripped_lower:
                    score = len(stripped_lower)
                    if score > best_score:
                        best_score = score
                        best_match = en_name
                else:
                    # Word overlap
                    de_words = set(stripped_lower.split()) - {"reihe", "serie", "krimis", "thriller", "series"}
                    en_words = set(en_lower.split()) - {"the", "series", "thriller", "mystery"}
                    overlap = de_words & en_words
                    if len(overlap) >= 1 and len(overlap) > best_score:
                        best_score = len(overlap)
                        best_match = en_name
            if best_match:
                de_to_en[sname] = best_match
    
    # Second pass: categorise every book entry
    for b in books_data:
        title = b.get("title", "")
        is_box = is_boxset_or_omnibus(title)
        
        for s in b.get("all_series", []):
            if not s.startswith("#"):
                continue
            parts = s.split(" in ", 1)
            if len(parts) != 2:
                continue
            sname = parts[1]
            try:
                num = int(parts[0][1:])
            except ValueError:
                continue
            
            if is_translation_series(sname):
                # This is a DE/translated edition — add revenue to the EN parent series P&L
                en_parent = de_to_en.get(sname)
                if en_parent:
                    series_pnl[en_parent]["gross"] += b.get("gross_royalty", 0)
                    series_pnl[en_parent]["spend"] += b.get("spending", 0)
                    series_pnl[en_parent]["kenp"] += b.get("total_reads", 0)
                    series_pnl[en_parent]["units"] += b.get("ebooks_paid_sold", 0)
                    en_to_de_series[en_parent].add(sname)
                # Also add to the DE series own P&L (for DE series to appear in their own right)
                series_pnl[sname]["gross"] += b.get("gross_royalty", 0)
                series_pnl[sname]["spend"] += b.get("spending", 0)
                series_pnl[sname]["kenp"] += b.get("total_reads", 0)
                series_pnl[sname]["units"] += b.get("ebooks_paid_sold", 0)
                if not is_box:
                    series_rt_books[sname].append({
                        "num": num, "title": title, "asin": b["asin"],
                        "total_reads": b.get("total_reads", 0),
                        "full_reads": b.get("full_reads") or 0,
                        "gross_royalty": b.get("gross_royalty", 0),
                        "spending": b.get("spending", 0),
                        "net_royalty": b.get("net_royalty", 0),
                        "fb_ad_spend": b.get("fb_ad_spend", 0),
                        "amz_ad_spend": b.get("amz_ad_spend", 0),
                        "ebooks_paid_sold": b.get("ebooks_paid_sold") or 0,
                        "paperbacks_sold": b.get("paperbacks_sold") or 0,
                        "image": b.get("image", ""),
                    })
            elif is_box:
                # Box set: add revenue to EN series P&L but NOT to readthrough books list
                series_pnl[sname]["gross"] += b.get("gross_royalty", 0)
                series_pnl[sname]["spend"] += b.get("spending", 0)
                series_pnl[sname]["kenp"] += b.get("total_reads", 0)
                series_pnl[sname]["units"] += b.get("ebooks_paid_sold", 0)
                en_to_boxsets[sname].add(b.get("asin", title))
            else:
                # Regular individual EN book
                series_pnl[sname]["gross"] += b.get("gross_royalty", 0)
                series_pnl[sname]["spend"] += b.get("spending", 0)
                series_pnl[sname]["kenp"] += b.get("total_reads", 0)
                series_pnl[sname]["units"] += b.get("ebooks_paid_sold", 0)
                series_rt_books[sname].append({
                    "num": num, "title": title, "asin": b["asin"],
                    "total_reads": b.get("total_reads", 0),
                    "full_reads": b.get("full_reads") or 0,
                    "gross_royalty": b.get("gross_royalty", 0),
                    "spending": b.get("spending", 0),
                    "net_royalty": b.get("net_royalty", 0),
                    "fb_ad_spend": b.get("fb_ad_spend", 0),
                    "amz_ad_spend": b.get("amz_ad_spend", 0),
                    "ebooks_paid_sold": b.get("ebooks_paid_sold") or 0,
                    "paperbacks_sold": b.get("paperbacks_sold") or 0,
                    "image": b.get("image", ""),
                })
    
    series_results = []
    for name, rt_books in series_rt_books.items():
        if len(rt_books) < 2:
            continue
        
        # Deduplicate by position: keep highest-KENP entry per position number
        pos_map = {}
        for b in rt_books:
            pos = b["num"]
            if pos not in pos_map or b["total_reads"] > pos_map[pos]["total_reads"]:
                pos_map[pos] = b
        books_deduped = list(pos_map.values())
        
        # Secondary filter: remove KENP outliers that are 2.5x+ the median
        if len(books_deduped) >= 3:
            kenp_vals = [b["total_reads"] for b in books_deduped if b["total_reads"] > 0]
            if kenp_vals:
                median_kenp = sorted(kenp_vals)[len(kenp_vals) // 2]
                if median_kenp > 0:
                    books_deduped = [
                        b for b in books_deduped
                        if b["total_reads"] == 0 or b["total_reads"] <= median_kenp * 2.5
                    ]
        
        books_sorted = sorted(books_deduped, key=lambda x: x["num"])
        
        # Use the full P&L (includes box sets + DE editions)
        pnl = series_pnl[name]
        total_gross = pnl["gross"]
        total_spend = pnl["spend"]
        total_net = total_gross - total_spend
        total_kenp = pnl["kenp"]
        total_units = pnl["units"]
        
        # Identify Book 1
        book1 = next((b for b in books_sorted if b["num"] == 1), None)
        book1_spend = book1["spending"] if book1 else 0
        book1_reads = book1["total_reads"] if book1 else 0
        
        # Resolve author from Book 1 ASIN
        book1_for_author = book1 or (books_sorted[0] if books_sorted else None)
        author = asin_to_author.get(book1_for_author["asin"], "—") if book1_for_author else "—"
        
        roi = (total_gross / total_spend * 100) if total_spend > 0 else float('inf')
        
        # Build composition annotation
        de_count = sum(len([b for b in series_rt_books.get(de_sname, [])]) for de_sname in en_to_de_series.get(name, set()))
        boxset_count = len(en_to_boxsets.get(name, set()))
        en_count = len(books_sorted)
        comp_parts = [f"{en_count} EN title{'s' if en_count != 1 else ''}"]
        if de_count:
            comp_parts.append(f"{de_count} DE translation{'s' if de_count != 1 else ''}")
        if boxset_count:
            comp_parts.append(f"{boxset_count} box set{'s' if boxset_count != 1 else ''}")
        composition = " · ".join(comp_parts)
        
        series_results.append({
            "name": name,
            "author": author,
            "books": books_sorted,
            "book_count": len(books_sorted),
            "total_gross": total_gross,
            "total_spend": total_spend,
            "total_net": total_net,
            "total_kenp": total_kenp,
            "total_units": total_units,
            "roi": roi,
            "book1_spend": book1_spend,
            "book1_reads": book1_reads,
            "image": books_sorted[0].get("image", "") if books_sorted else "",
            "composition": composition,
        })
    
    series_results.sort(key=lambda x: -x["total_gross"])
    return series_results


def compute_readthrough(series_data, period_label="90-day"):
    """Compute readthrough funnels for series with 2+ books."""
    readthrough_results = []
    
    for series in series_data:
        books = series["books"]
        if len(books) < 2:
            continue
        
        # Get Book 1 KENP as baseline.
        # Skip entries that are prequels or novellas (identified by title keywords);
        # these are not full-length novels and would distort the readthrough baseline.
        # Also skip position #0 (explicit prequels).
        book1 = next(
            (b for b in books
             if b["num"] == 1 and not is_prequel_or_novella(b["title"])),
            None
        )
        if not book1 or book1["total_reads"] == 0:
            continue
        
        book1_kenp = book1["total_reads"]
        
        # Require meaningful sample size to avoid statistical noise
        if book1_kenp < 5000:
            continue
        
        # Calculate readthrough percentages.
        # Skip position #0 (prequels) and any book tagged as a prequel/novella.
        rt_data = []
        for b in sorted(books, key=lambda x: x["num"]):
            if b["num"] == 0:
                continue
            if is_prequel_or_novella(b["title"]):
                continue  # skip novellas/prequels within the series sequence
            pct_of_book1 = (b["total_reads"] / book1_kenp * 100) if book1_kenp > 0 else 0
            rt_data.append({
                "num": b["num"],
                "title": b["title"],
                "kenp": b["total_reads"],
                "pct_of_book1": pct_of_book1,
            })
        
        if len(rt_data) < 2:
            continue
        
        # Calculate step-by-step retention
        step_retention = []
        for i in range(1, len(rt_data)):
            prev_kenp = rt_data[i-1]["kenp"]
            curr_kenp = rt_data[i]["kenp"]
            if prev_kenp > 0:
                retention = (curr_kenp / prev_kenp * 100)
            else:
                retention = 0
            step_retention.append(retention)
        
        # Book 1→2 retention
        book1_to_2 = step_retention[0] if step_retention else 0
        
        # Average retention after Book 2
        avg_subsequent = statistics.mean(step_retention[1:]) if len(step_retention) > 1 else 0
        
        # Color coding based on benchmarks
        def get_rt_color(value, benchmark):
            if value >= benchmark:
                return "green"
            elif value >= benchmark - RT_AMBER_THRESHOLD:
                return "amber"
            else:
                return "red"
        
        book1_to_2_color = get_rt_color(book1_to_2, RT_BENCHMARK_BOOK1_TO_2)
        
        # Exclude series where B1→B2 > 100%: these are not meaningful for readthrough
        # analysis (Book 2 has more reads than Book 1, typically due to independent ad spend
        # on Book 2 or a perma-free Book 1 that inflates the denominator differently).
        # Box sets are already excluded from the books list in compute_series_economics;
        # this cap handles the remaining cases of genuine inverted funnels.
        if book1_to_2 > 100:
            continue
        
        readthrough_results.append({
            "series_name": series["name"],
            "book_count": len(rt_data),
            "book1_kenp": book1_kenp,
            "rt_data": rt_data,
            "step_retention": step_retention,
            "book1_to_2": book1_to_2,
            "book1_to_2_color": book1_to_2_color,
            "avg_subsequent": avg_subsequent,
            "total_gross": series["total_gross"],
            "total_spend": series["total_spend"],
        })
    
    readthrough_results.sort(key=lambda x: -x["book1_to_2"])
    return readthrough_results


def compute_author_readthrough_ranking(readthrough_90, series_90):
    """Rank authors by average series readthrough retention."""
    # Map series to authors via book data
    series_to_author = {}
    for series in series_90:
        # Try to find author from the series books
        # We'll need to cross-reference with author data
        series_to_author[series["name"]] = series
    
    # Build author → series readthrough mapping
    # We need to load author data to map series to authors
    author_data = load_author_data()
    
    # Build ASIN → author mapping
    asin_to_author = {}
    for author_name, books_dict in author_data.items():
        if not isinstance(books_dict, dict):
            continue
        for book_title, book_info in books_dict.items():
            if isinstance(book_info, dict) and "asin" in book_info:
                asin_to_author[book_info["asin"]] = author_name
    
    # Map series to authors via their Book 1 ASIN
    author_series_rt = defaultdict(list)
    for rt in readthrough_90:
        series_name = rt["series_name"]
        # Find the series in series_90 to get Book 1 ASIN
        matching_series = next((s for s in series_90 if s["name"] == series_name), None)
        if matching_series and matching_series["books"]:
            book1 = next((b for b in matching_series["books"] if b["num"] == 1), None)
            if book1:
                author = asin_to_author.get(book1["asin"], "Unknown")
                author_series_rt[author].append({
                    "series_name": series_name,
                    "book1_to_2": rt["book1_to_2"],
                    "avg_subsequent": rt["avg_subsequent"],
                    "book_count": rt["book_count"],
                })
    
    # Compute author rankings
    author_rankings = []
    for author, series_list in author_series_rt.items():
        if not series_list:
            continue
        
        avg_rt = statistics.mean([s["book1_to_2"] for s in series_list])
        best_rt = max(s["book1_to_2"] for s in series_list)
        best_series = max(series_list, key=lambda x: x["book1_to_2"])["series_name"]
        
        author_rankings.append({
            "author": author,
            "avg_readthrough": avg_rt,
            "best_readthrough": best_rt,
            "best_series": best_series,
            "series_count": len(series_list),
        })
    
    author_rankings.sort(key=lambda x: -x["avg_readthrough"])
    return author_rankings


def compute_ad_efficiency(series_30):
    """Compute ad efficiency metrics for series funnels."""
    funnels = []
    
    for series in series_30:
        if series["total_spend"] <= 0:
            continue
        
        book1 = next((b for b in series["books"] if b["num"] == 1), None)
        if not book1:
            continue
        
        # Cost per reader acquired (correct formula):
        # Total readers = KU complete reads (full_reads) + paid ebook units + paperback units
        # full_reads = KENP pages read / KENPC (i.e., number of people who read the whole book)
        book1_ku_readers = book1.get("full_reads", 0) or 0
        book1_ebook_units = book1.get("ebooks_paid_sold", 0) or 0
        book1_pb_units = book1.get("paperbacks_sold", 0) or 0
        book1_readers = book1_ku_readers + book1_ebook_units + book1_pb_units
        cost_per_reader = (series["total_spend"] / book1_readers) if book1_readers > 0 else float('inf')
        
        # Series ROI
        roi = series["roi"]
        is_profitable = roi >= 200
        
        funnels.append({
            "series_name": series["name"],
            "author": series.get("author", "Unknown"),
            "book1_title": book1["title"],
            "book1_spend": book1["spending"],
            "total_series_spend": series["total_spend"],
            "total_series_gross": series["total_gross"],
            "series_net": series["total_net"],
            "roi": roi,
            "is_profitable": is_profitable,
            "cost_per_reader": cost_per_reader,
            "book1_readers": book1_readers,
            "book_count": series["book_count"],
            "image": series.get("image", ""),
        })
    
    funnels.sort(key=lambda x: -x["roi"])
    return funnels


def compute_organic_winners(books_30):
    """Find titles/series profitable with ZERO ad spend."""
    organic = []
    
    for b in books_30:
        if b["spending"] == 0 and b["gross_royalty"] > 5:
            organic.append({
                "title": b["title"],
                "asin": b["asin"],
                "gross": b["gross_royalty"],
                "kenp": b["total_reads"],
                "units": b["ebooks_paid_sold"],
                "series": b.get("all_series", []),
                "image": b.get("image", ""),
            })
    
    organic.sort(key=lambda x: -x["gross"])
    return organic[:20]


def compute_bsr_revenue_correlation(books_30, bsr_data):
    """Cross-reference BSR positions with actual revenue.
    
    Computes average BSR across all available dates in the dataset.
    Handles both record formats:
      - Old format: record_date (str), asin (str)
      - New format: recorded_at (timestamp), title_id (UUID), no asin
    Returns list of dicts plus a metadata dict as the last element.
    """
    # Build ASIN → revenue/series lookup from 30-day PC data
    asin_to_author = build_asin_to_author_map()
    asin_revenue = {}
    for b in books_30:
        asin = b.get("asin")
        if not asin:
            continue
        series_list = b.get("all_series", [])
        # Build series label: use first series entry, or detect box set
        if is_boxset_or_omnibus(b["title"]):
            series_label = "Box Set"
        elif series_list:
            series_label = series_list[0]  # e.g. "#1 in Ryan Kaine"
        else:
            series_label = "Standalone"
        asin_revenue[asin] = {
            "title": b["title"],
            "author": asin_to_author.get(asin, "Unknown"),
            "gross": b["gross_royalty"],
            "kenp": b["total_reads"],
            "units": b["ebooks_paid_sold"],
            "series_label": series_label,
        }
    
    if not bsr_data:
        return []
    
    # Normalise records: extract date and asin from either format
    # Accumulate BSR readings per ASIN across all dates
    asin_bsr_readings = defaultdict(list)  # asin -> list of bsr_us values
    all_dates = set()
    
    for r in bsr_data:
        # Resolve date field (handle both formats)
        date_str = r.get("record_date") or (r.get("recorded_at", "")[:10])
        if not date_str:
            continue
        all_dates.add(date_str)
        
        # Resolve ASIN (old format has asin directly; new format uses title_id)
        asin = r.get("asin")
        if not asin:
            # New format: try title-based lookup
            title_norm = r.get("title", "").lower().strip()
            # Build reverse map lazily if needed (done once per call)
            if not hasattr(compute_bsr_revenue_correlation, "_title_to_asin"):
                compute_bsr_revenue_correlation._title_to_asin = {
                    b["title"].lower().strip(): b["asin"]
                    for b in books_30 if b.get("asin")
                }
            asin = compute_bsr_revenue_correlation._title_to_asin.get(title_norm)
        
        if not asin or asin not in asin_revenue:
            continue
        
        bsr_us = r.get("bsr_us")
        if bsr_us and bsr_us > 0:
            asin_bsr_readings[asin].append(bsr_us)
    
    days_of_data = len(all_dates)
    
    correlations = []
    for asin, readings in asin_bsr_readings.items():
        if not readings:
            continue
        rev = asin_revenue[asin]
        avg_bsr = int(round(sum(readings) / len(readings)))
        correlations.append({
            "title": rev["title"],
            "author": rev["author"],
            "asin": asin,
            "bsr_us": avg_bsr,          # average across all available dates
            "bsr_readings": len(readings),
            "gross_30day": rev["gross"],
            "kenp_30day": rev["kenp"],
            "units_30day": rev["units"],
            "series_label": rev["series_label"],
            "days_of_data": days_of_data,
        })
    
    correlations.sort(key=lambda x: x["bsr_us"])
    # Clear cached title map so it's rebuilt fresh on next call
    if hasattr(compute_bsr_revenue_correlation, "_title_to_asin"):
        del compute_bsr_revenue_correlation._title_to_asin
    return correlations


# ─── HTML Generation ─────────────────────────────────────────────────────────

def load_logo_base64():
    """Load the white logo as base64."""
    logo_path = SCRIPT_DIR / "Vinci_Books_Logo_Icon_White.png"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


def fmt_currency(value, currency="£"):
    """Format currency value. Handles negative numbers as -£XXX."""
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    if abs_val >= 1_000_000:
        return f"{sign}{currency}{abs_val/1_000_000:.1f}M"
    elif abs_val >= 1_000:
        return f"{sign}{currency}{abs_val/1_000:.1f}K"
    else:
        return f"{sign}{currency}{abs_val:.0f}"


def fmt_number(value):
    """Format large numbers."""
    if value >= 1_000_000:
        return f"{value/1_000_000:.1f}M"
    elif value >= 1_000:
        return f"{value/1_000:.1f}K"
    else:
        return f"{value:,.0f}"


def fmt_pct(value):
    """Format percentage with sign."""
    if value > 0:
        return f"+{value:.1f}%"
    else:
        return f"{value:.1f}%"


def get_change_class(value):
    """Get CSS class for positive/negative change."""
    return "positive" if value >= 0 else "negative"


def get_rt_color_class(value, benchmark):
    """Get color class for readthrough benchmark."""
    if value >= benchmark:
        return "rt-green"
    elif value >= benchmark - RT_AMBER_THRESHOLD:
        return "rt-amber"
    else:
        return "rt-red"


def compute_period_kpis(books_data, curr_symbol, label, prev_books=None, prev_label=None):
    """Compute KPI grid HTML for a given period's book data."""
    gross = sum(b.get("gross_royalty", 0) for b in books_data)
    spend = sum(b.get("spending", 0) for b in books_data)
    net = gross - spend
    kenp = sum(b.get("total_reads", 0) for b in books_data)
    units = sum(b.get("ebooks_paid_sold", 0) for b in books_data)
    roi = (gross / spend * 100) if spend > 0 else float('inf')
    roi_str = f"{roi:.0f}%" if roi != float('inf') else "∞"
    
    # Build comparison row if prev data provided
    comp_html = ""
    if prev_books is not None:
        pg = sum(b.get("gross_royalty", 0) for b in prev_books)
        ps = sum(b.get("spending", 0) for b in prev_books)
        pn = pg - ps
        pk = sum(b.get("total_reads", 0) for b in prev_books)
        
        def pct_chg(a, b):
            """Return a coloured percentage-change span with comma formatting for large values."""
            if b == 0:
                return '<span class="positive">N/A</span>' if a > 0 else 'N/A'
            v = (a - b) / b * 100
            cls = "positive" if v >= 0 else "negative"
            sign = "+" if v >= 0 else ""
            return f'<span class="{cls}">{sign}{v:,.1f}%</span>'
        
        comp_html = f"""
        <div class="kpi-comparison">
            <span style="font-weight: 700; color: var(--gold);">vs {prev_label}:</span>
            <span>Gross {pct_chg(gross, pg)}</span>
            <span>Net {pct_chg(net, pn)}</span>
            <span>KENP {pct_chg(kenp, pk)}</span>
        </div>"""
    
    return f"""
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-value">{fmt_currency(gross, curr_symbol)}</div>
            <div class="kpi-label">GROSS REVENUE</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value">{fmt_currency(spend, curr_symbol)}</div>
            <div class="kpi-label">AD SPEND</div>
            <div class="kpi-sublabel">FB + AMZ combined</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value">{fmt_currency(net, curr_symbol)}</div>
            <div class="kpi-label">NET PROFIT</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value">{fmt_number(kenp)}</div>
            <div class="kpi-label">KENP READS</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value">{roi_str}</div>
            <div class="kpi-label">PORTFOLIO ROI</div>
            <div class="kpi-sublabel">Gross / Spend</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value">{fmt_number(units)}</div>
            <div class="kpi-label">UNITS SOLD</div>
            <div class="kpi-sublabel">{len(books_data):,} active titles</div>
        </div>
    </div>{comp_html}"""


def generate_html(portfolio, authors, authors_90, series_30, series_90, readthrough_90, readthrough_30,
                  author_rankings, ad_funnels, organic_winners, bsr_correlation,
                  country_data, books_30, books_90, books_ytd, books_ytd_ly, books_fy2025,
                  books_mtd=None, books_mtd_ly=None, pulse=None,
                  books_fy2024=None, books_lifetime=None):
    """Generate the full HTML executive dashboard."""
    
    logo_b64 = load_logo_base64()
    report_date = datetime.now(timezone.utc).strftime("%B %d, %Y")
    currency = portfolio.get("currency", "GBP")
    curr_symbol = "£" if currency == "GBP" else "$"
    
    # ─── Build sections ───
    
    # Portfolio KPIs — multi-period tabs
    today_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    ytd_start = datetime.now(timezone.utc).strftime("Jan 1, %Y")
    
    # MTD: compare to same days in the same month last year
    kpi_mtd = compute_period_kpis(books_mtd or books_30, curr_symbol, "MTD", books_mtd_ly, "same period last year")
    
    # 30-Day: compare to the prior 30-day window (i.e. days 31-60 ago)
    # We use books_90 minus books_30 as a proxy for the prior 30-day window
    # A better approach: load a dedicated prior-30 file if available, else skip comparison
    _prior30_path = DATA_DIR / "pc_prior30day.json"
    if _prior30_path.exists():
        import json as _json30
        _prior30_books = _json30.load(open(_prior30_path)).get("table_data", [])
        kpi_30 = compute_period_kpis(books_30, curr_symbol, "30-Day", _prior30_books, "prior 30 days")
    else:
        kpi_30 = compute_period_kpis(books_30, curr_symbol, "30-Day")
    
    kpi_90 = compute_period_kpis(books_90, curr_symbol, "90-Day")
    kpi_ytd = compute_period_kpis(books_ytd, curr_symbol, "YTD 2026", books_ytd_ly, "YTD 2025")
    _fy2024 = books_fy2024 or []
    _lifetime = books_lifetime or []
    kpi_fy2025 = compute_period_kpis(books_fy2025, curr_symbol, "FY 2025", _fy2024 if _fy2024 else None, "FY 2024" if _fy2024 else None)
    kpi_fy2024 = compute_period_kpis(_fy2024, curr_symbol, "FY 2024")
    kpi_lifetime = compute_period_kpis(_lifetime, curr_symbol, "Lifetime")
    kpi_cards = f"""
    <div class="period-tabs">
        <button class="period-tab active" onclick="switchTab(this, 'portfolio-mtd')">MTD</button>
        <button class="period-tab" onclick="switchTab(this, 'portfolio-30')">30-Day</button>
        <button class="period-tab" onclick="switchTab(this, 'portfolio-90')">90-Day</button>
        <button class="period-tab" onclick="switchTab(this, 'portfolio-ytd')">YTD 2026</button>
        <button class="period-tab" onclick="switchTab(this, 'portfolio-fy25')">FY 2025</button>
        <button class="period-tab" onclick="switchTab(this, 'portfolio-fy24')">FY 2024</button>
        <button class="period-tab" onclick="switchTab(this, 'portfolio-lifetime')">Lifetime</button>
    </div>
    <div id="portfolio-mtd" class="period-panel">{kpi_mtd}</div>
    <div id="portfolio-30" class="period-panel" style="display:none">{kpi_30}</div>
    <div id="portfolio-90" class="period-panel" style="display:none">{kpi_90}</div>
    <div id="portfolio-ytd" class="period-panel" style="display:none">{kpi_ytd}</div>
    <div id="portfolio-fy25" class="period-panel" style="display:none">{kpi_fy2025}</div>
    <div id="portfolio-fy24" class="period-panel" style="display:none">{kpi_fy2024}</div>
    <div id="portfolio-lifetime" class="period-panel" style="display:none">{kpi_lifetime}</div>
    """
    
    # Portfolio Pulse — 6 live KPI boxes
    pulse = pulse or {}
    us_top10k = pulse.get('us_top10k', 0)
    uk_top10k = pulse.get('uk_top10k', 0)
    de_top10k = pulse.get('de_top10k', 0)
    avg_b1_to_b2 = pulse.get('avg_b1_to_b2', 0)
    organic_pct = pulse.get('organic_pct', 0)
    top_mover = pulse.get('top_mover')
    pulse_date = pulse.get('latest_date', 'Latest')
    
    # Avg B1->B2 color
    b1b2_color = '#00c853' if avg_b1_to_b2 >= 50 else ('#ffab00' if avg_b1_to_b2 >= 40 else '#ff1744')
    
    # Top mover card content
    if top_mover:
        mover_title = top_mover['title'][:35] + ('...' if len(top_mover['title']) > 35 else '')
        mover_author = top_mover.get('author', '')
        mover_cover = top_mover.get('cover_url', '')
        mover_improvement = top_mover['improvement']
        if mover_improvement >= 1_000_000:
            mover_str = f"+{mover_improvement/1_000_000:.1f}M"
        elif mover_improvement >= 1_000:
            mover_str = f"+{mover_improvement/1_000:.0f}K"
        else:
            mover_str = f"+{mover_improvement:,}"
        cover_img = f'<img src="{mover_cover}" alt="cover" class="mover-cover" onerror="this.style.display=\'none\'">'
        author_line = f'<div class="kpi-sublabel mover-author">{mover_author}</div>' if mover_author else ''
        mover_html = f"""
            <div class="mover-kpi-inner">
                {cover_img}
                <div class="mover-kpi-text">
                    <div class="kpi-value" style="font-size:1.4rem;color:#00c853">{mover_str}</div>
                    <div class="kpi-label">TOP MOVER (US BSR)</div>
                    <div class="kpi-sublabel" style="font-size:0.7rem;white-space:normal;line-height:1.3">{mover_title}</div>
                    {author_line}
                    <div class="kpi-sublabel">{top_mover['prev_bsr']:,} → {top_mover['curr_bsr']:,}</div>
                </div>
            </div>"""
    else:
        mover_html = '<div class="kpi-value">—</div><div class="kpi-label">TOP MOVER (US BSR)</div>'
    
    pulse_html = f"""
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-value">{us_top10k}</div>
            <div class="kpi-label">US TOP 10K</div>
            <div class="kpi-sublabel">Titles ranked ≤10,000 (as of {pulse_date})</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value">{uk_top10k}</div>
            <div class="kpi-label">UK TOP 10K</div>
            <div class="kpi-sublabel">Titles ranked ≤10,000 (as of {pulse_date})</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value">{de_top10k}</div>
            <div class="kpi-label">DE TOP 10K</div>
            <div class="kpi-sublabel">Titles ranked ≤10,000 (as of {pulse_date})</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value" style="color:{b1b2_color}">{avg_b1_to_b2:.1f}%</div>
            <div class="kpi-label">AVG B1→B2 READTHROUGH</div>
            <div class="kpi-sublabel">Portfolio avg across all series &middot; Benchmark: 50%+</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value">{organic_pct:.1f}%</div>
            <div class="kpi-label">ORGANIC REVENUE %</div>
            <div class="kpi-sublabel">Gross from titles with zero ad spend (30-day)</div>
        </div>
        <div class="kpi-card">
            {mover_html}
        </div>
    </div>"""
    
    # Author Economics Table — 30-day
    author_rows_30 = ""
    for i, a in enumerate(authors[:20], 1):
        roi_str = f"{a['roi']:.0f}%" if a['roi'] != float('inf') else "∞"
        roi_class = "positive" if a['roi'] >= 100 else "negative"
        net_class = "positive" if a['net'] >= 0 else "negative"
        author_rows_30 += f"""
        <tr>
            <td class="rank">{i}</td>
            <td class="author-name">{a['name']}</td>
            <td class="num">{a['books']}</td>
            <td class="num">{fmt_currency(a['gross'], curr_symbol)}</td>
            <td class="num">{fmt_currency(a['spend'], curr_symbol)}</td>
            <td class="num {net_class}">{fmt_currency(a['net'], curr_symbol)}</td>
            <td class="num {roi_class}">{roi_str}</td>
            <td class="num">{fmt_number(a['kenp'])}</td>
        </tr>"""
    
    # Author Economics Table — 90-day
    author_rows_90 = ""
    for i, a in enumerate(authors_90[:20], 1):
        roi_str = f"{a['roi']:.0f}%" if a['roi'] != float('inf') else "∞"
        roi_class = "positive" if a['roi'] >= 100 else "negative"
        net_class = "positive" if a['net'] >= 0 else "negative"
        author_rows_90 += f"""
        <tr>
            <td class="rank">{i}</td>
            <td class="author-name">{a['name']}</td>
            <td class="num">{a['books']}</td>
            <td class="num">{fmt_currency(a['gross'], curr_symbol)}</td>
            <td class="num">{fmt_currency(a['spend'], curr_symbol)}</td>
            <td class="num {net_class}">{fmt_currency(a['net'], curr_symbol)}</td>
            <td class="num {roi_class}">{roi_str}</td>
            <td class="num">{fmt_number(a['kenp'])}</td>
        </tr>"""
    
    # Series Economics (Top 15) — 30-day
    series_rows_30 = ""
    for i, s in enumerate(series_30[:15], 1):
        roi_str = f"{s['roi']:.0f}%" if s['roi'] != float('inf') else "∞"
        roi_class = "positive" if s['roi'] >= 100 else "negative"
        net_class = "positive" if s['total_net'] >= 0 else "negative"
        series_rows_30 += f"""
        <tr>
            <td class="rank">{i}</td>
            <td class="author-name">{s.get('author', '—')}</td>
            <td class="series-name">{s['name']}</td>
            <td class="num">{s['book_count']}</td>
            <td class="num">{fmt_currency(s['total_gross'], curr_symbol)}</td>
            <td class="num">{fmt_currency(s['total_spend'], curr_symbol)}</td>
            <td class="num {net_class}">{fmt_currency(s['total_net'], curr_symbol)}</td>
            <td class="num {roi_class}">{roi_str}</td>
            <td class="num">{fmt_number(s['total_kenp'])}</td>
        </tr>"""
    
    # Series Economics (Top 15) — 90-day
    series_rows_90 = ""
    for i, s in enumerate(series_90[:15], 1):
        roi_str = f"{s['roi']:.0f}%" if s['roi'] != float('inf') else "∞"
        roi_class = "positive" if s['roi'] >= 100 else "negative"
        net_class = "positive" if s['total_net'] >= 0 else "negative"
        series_rows_90 += f"""
        <tr>
            <td class="rank">{i}</td>
            <td class="author-name">{s.get('author', '—')}</td>
            <td class="series-name">{s['name']}</td>
            <td class="num">{s['book_count']}</td>
            <td class="num">{fmt_currency(s['total_gross'], curr_symbol)}</td>
            <td class="num">{fmt_currency(s['total_spend'], curr_symbol)}</td>
            <td class="num {net_class}">{fmt_currency(s['total_net'], curr_symbol)}</td>
            <td class="num {roi_class}">{roi_str}</td>
            <td class="num">{fmt_number(s['total_kenp'])}</td>
        </tr>"""
    
    # Build series name -> author map for RT card labels
    series_author_map = {s["name"]: s.get("author", "—") for s in series_90}
    
    # Readthrough Funnels (Top 10 series by revenue with RT data)
    rt_charts_html = ""
    # Sort by total gross to show the most commercially significant series
    top_rt_candidates = [r for r in readthrough_90 if r["book_count"] >= 3]
    top_rt_candidates.sort(key=lambda x: -x["total_gross"])
    top_rt = top_rt_candidates[:12]
    for rt in top_rt:
        # No cap — show ALL books in the series
        labels = [f"Book {d['num']}" for d in rt["rt_data"]]
        # Use step-by-step retention for bar heights:
        # Book 1 = 100% (baseline), Book 2+ = step retention from preceding book
        values = []
        for i, d in enumerate(rt["rt_data"]):
            if i == 0:
                values.append(100.0)  # Book 1 is always the 100% baseline
            else:
                step = rt["step_retention"][i - 1] if i - 1 < len(rt["step_retention"]) else 0
                values.append(step)
        
        # Build per-bar step-based colors (not cumulative % of Book 1)
        # Book 1: always gold
        # Book 2: green if B1→B2 step >=50%, amber if >=40%, red if <40%
        # Book 3+: green if step from prev >=70%, amber if >=60%, red if <60%
        bar_colors = []
        bar_borders = []
        step_rets = rt["step_retention"]  # step_rets[i] = retention from book i+1 to book i+2
        for i in range(len(values)):
            if i == 0:
                # Book 1 always gold
                bar_colors.append(BRAND_GOLD)
                bar_borders.append(BRAND_GOLD)
            else:
                step = step_rets[i - 1] if i - 1 < len(step_rets) else 0
                if i == 1:
                    # B1→B2 step
                    if step >= 50:
                        bar_colors.append("rgba(0, 200, 83, 0.7)")
                        bar_borders.append("#00c853")
                    elif step >= 40:
                        bar_colors.append("rgba(255, 171, 0, 0.7)")
                        bar_borders.append("#ffab00")
                    else:
                        bar_colors.append("rgba(255, 23, 68, 0.5)")
                        bar_borders.append("#ff1744")
                else:
                    # B2+ subsequent steps
                    if step >= 70:
                        bar_colors.append("rgba(0, 200, 83, 0.7)")
                        bar_borders.append("#00c853")
                    elif step >= 60:
                        bar_colors.append("rgba(255, 171, 0, 0.7)")
                        bar_borders.append("#ffab00")
                    else:
                        bar_colors.append("rgba(255, 23, 68, 0.5)")
                        bar_borders.append("#ff1744")
        
        # Step retention badges — show all steps (no cap)
        step_badges = ""
        for i, ret in enumerate(rt["step_retention"]):
            if i == 0:
                color_class = get_rt_color_class(ret, RT_BENCHMARK_BOOK1_TO_2)
                label = f"B1→B2: {ret:.0f}%"
            else:
                benchmark = RT_BENCHMARK_AFTER_BOOK2 if i >= 2 else RT_BENCHMARK_SUBSEQUENT
                color_class = get_rt_color_class(ret, benchmark)
                label = f"B{i+1}→B{i+2}: {ret:.0f}%"
            step_badges += f'<span class="rt-badge {color_class}">{label}</span>'
        
        rt_author = series_author_map.get(rt['series_name'], '—')
        # Build pure CSS bar chart — no external dependencies
        max_val = max(values) if values else 100
        tall_class = " tall" if len(values) > 10 else ""
        bars_html = ""
        for bi, (label, val, bg_col) in enumerate(zip(labels, values, bar_colors)):
            bar_pct = (val / max_val * 100) if max_val > 0 else 0
            # Tooltip: show step retention and also cumulative % of Book 1 for context
            if bi == 0:
                tooltip_text = f"Book 1 baseline (100%)"
                bar_label_val = "100%"
            else:
                # val is already the step retention from preceding book
                pct_of_b1 = rt["rt_data"][bi]["pct_of_book1"]
                prev_label = f"B{bi}" if bi > 0 else "B1"
                tooltip_text = f"B{bi}→B{bi+1}: {val:.1f}% of preceding book | {pct_of_b1:.1f}% of B1"
                bar_label_val = f"{val:.0f}%"
            bars_html += f"""
                <div class="rt-bar-wrap">
                    <div class="rt-bar-tooltip">{tooltip_text}</div>
                    <div class="rt-bar-value">{bar_label_val}</div>
                    <div class="rt-bar" style="height:{bar_pct:.1f}%; background:{bg_col};"></div>
                    <div class="rt-bar-label">{label.replace('Book ', 'B')}</div>
                </div>"""
        # Get composition annotation from series_90 data
        rt_series_data = next((s for s in series_90 if s['name'] == rt['series_name']), None)
        composition_annotation = rt_series_data.get('composition', '') if rt_series_data else ''
        composition_html = f'<div class="rt-composition">{composition_annotation}</div>' if composition_annotation else ''
        rt_charts_html += f"""
        <div class="rt-card">
            <div class="rt-header">
                <h4>{rt['series_name']}</h4>
                <span class="rt-meta">{rt_author} &middot; {rt['book_count']} EN books &middot; Book 1 KENP: {rt['book1_kenp']:,}</span>
                {composition_html}
            </div>
            <div class="rt-badges">{step_badges}</div>
            <div class="rt-bar-chart">
                <div class="rt-bars-container{tall_class}">{bars_html}
                </div>
            </div>
        </div>"""
    
    # 30-day vs 90-day RT comparison (early warning)
    rt_warnings = ""
    rt_30_map = {r["series_name"]: r["book1_to_2"] for r in readthrough_30}
    rt_90_map = {r["series_name"]: r["book1_to_2"] for r in readthrough_90}
    
    warnings_list = []
    for name, rt90 in rt_90_map.items():
        rt30 = rt_30_map.get(name)
        if rt30 is not None and rt90 > 0:
            drop = rt90 - rt30
            if drop > 10:
                warnings_list.append({"name": name, "rt_90": rt90, "rt_30": rt30, "drop": drop})
    
    warnings_list.sort(key=lambda x: -x["drop"])
    if warnings_list:
        rt_warnings = '<div class="warning-box"><h4>⚠️ Readthrough Early Warnings</h4><p>Flags series where the last 30-day Book 1→Book 2 readthrough has dropped more than 10 percentage points below the 90-day average. A sudden drop may indicate: wrong readers being attracted by new ads or covers, pricing changes affecting conversion, or algorithm visibility loss. Investigate the cause and adjust marketing.</p><ul>'
        for w in warnings_list[:5]:
            rt_warnings += f'<li><strong>{w["name"]}</strong>: 90-day RT {w["rt_90"]:.0f}% → 30-day RT {w["rt_30"]:.0f}% (↓{w["drop"]:.0f}pp)</li>'
        rt_warnings += '</ul></div>'
    
    # Author Readthrough Ranking
    author_rt_rows = ""
    # Sort by best B1→B2 readthrough (the most relevant metric for the ad funnel)
    author_rankings_sorted = sorted(author_rankings, key=lambda x: -x['best_readthrough'])
    for i, ar in enumerate(author_rankings_sorted[:20], 1):
        b1b2_class = get_rt_color_class(ar["best_readthrough"], RT_BENCHMARK_BOOK1_TO_2)
        author_rt_rows += f"""
        <tr>
            <td class="rank">{i}</td>
            <td class="author-name">{ar['author']}</td>
            <td class="num {b1b2_class}">{ar['best_readthrough']:.0f}%</td>
            <td class="num">{ar['series_count']}</td>
            <td class="series-name">{ar['best_series']}</td>
        </tr>"""
    
    # Ad Efficiency
    # Minimum £1K gross to qualify for any tier
    MIN_GROSS = 1000
    qualified = [f for f in ad_funnels if f["total_series_gross"] >= MIN_GROSS]
    
    # Three tiers
    star_funnels = [f for f in qualified if f["roi"] >= 300][:10]
    solid_funnels = [f for f in qualified if 200 <= f["roi"] < 300][:10]
    burning_funnels = [f for f in qualified if f["roi"] < 200]
    # Sort by absolute loss (spend - gross) descending — worst losses first
    for f in burning_funnels:
        f["abs_loss"] = f["total_series_spend"] - f["total_series_gross"]
    burning_funnels.sort(key=lambda x: -x["abs_loss"])
    burning_funnels = burning_funnels[:10]
    
    def _ad_row(f, roi_class):
        return f"""
        <tr>
            <td class="series-name">
                <div style="font-weight: 700;">{f['series_name']}</div>
                <div style="font-size: 0.7rem; color: var(--text-secondary);">{f['author']}</div>
            </td>
            <td class="num">{f['book_count']}</td>
            <td class="num">{fmt_currency(f['total_series_spend'], curr_symbol)}</td>
            <td class="num">{fmt_currency(f['total_series_gross'], curr_symbol)}</td>
            <td class="num {roi_class}">{f['roi']:.0f}%</td>
            <td class="num">{fmt_currency(f['cost_per_reader'], curr_symbol) if f['cost_per_reader'] != float('inf') else '—'}</td>
        </tr>"""
    
    ad_star_rows = "".join(_ad_row(f, "positive") for f in star_funnels)
    ad_solid_rows = "".join(_ad_row(f, "positive") for f in solid_funnels)
    ad_burning_rows = ""
    for f in burning_funnels:
        abs_loss = f.get("abs_loss", f["total_series_spend"] - f["total_series_gross"])
        ad_burning_rows += f"""
        <tr>
            <td class="series-name">
                <div style="font-weight: 700;">{f['series_name']}</div>
                <div style="font-size: 0.7rem; color: var(--text-secondary);">{f['author']}</div>
            </td>
            <td class="num">{f['book_count']}</td>
            <td class="num">{fmt_currency(f['total_series_spend'], curr_symbol)}</td>
            <td class="num">{fmt_currency(f['total_series_gross'], curr_symbol)}</td>
            <td class="num negative">{f['roi']:.0f}%</td>
            <td class="num negative" style="font-weight:700">{fmt_currency(-abs_loss, curr_symbol)}</td>
        </tr>"""
    # Keep ad_profitable_rows as alias for template backward compat
    ad_profitable_rows = ad_star_rows
    
    # Country breakdown
    # Known non-country keys that Publisher Champ sometimes includes in the countries dict
    _NON_COUNTRIES = {"Facebook", "Meta", "Amazon", "Google", "Apple", "BookBub",
                      "Draft2Digital", "Kobo", "Smashwords", "IngramSpark"}
    country_rows = ""
    countries = portfolio.get("countries", {})
    # Filter out ad-platform entries and zero-gross rows
    countries_filtered = {
        k: v for k, v in countries.items()
        if k not in _NON_COUNTRIES and (v.get("converted", 0) > 0 or v.get("converted_spend", 0) > 0)
    }
    total_country_gross = sum(c.get("converted", 0) for c in countries_filtered.values())
    # Countries where ad spend is in a different (local) currency — show a note
    _HIGH_CONVERSION_COUNTRIES = {"India", "Japan", "Brazil", "Mexico"}  # low GBP conversion
    for name, cdata in sorted(countries_filtered.items(), key=lambda x: -x[1].get("converted", 0)):
        gross = cdata.get("converted", 0)
        spend = cdata.get("converted_spend", 0)
        net = gross - spend
        net_class = "positive" if net >= 0 else "negative"
        pct_of_total = (gross / total_country_gross * 100) if total_country_gross > 0 else 0
        # Mini bar for visual % representation
        bar_width = min(int(pct_of_total), 100)
        # Context note for high-conversion-ratio countries where spend looks disproportionate
        orig_currency = cdata.get("original_currency", "")
        country_note = ""
        if name in _HIGH_CONVERSION_COUNTRIES and orig_currency and orig_currency != "GBP":
            orig_gross = cdata.get("original", "")
            orig_spend = cdata.get("original_spend", "")
            if orig_gross != "-" and orig_spend != "-":
                country_note = f' <span style="font-size:0.65rem;color:var(--text-muted);" title="Amounts converted from {orig_currency}. Original: {orig_currency} {orig_gross:,.0f} gross / {orig_currency} {orig_spend:,.0f} spend">({orig_currency})</span>'
        country_rows += f"""
        <tr>
            <td class="country-name">{name}{country_note}</td>
            <td class="num">{fmt_currency(gross, curr_symbol)}</td>
            <td class="num">{fmt_currency(spend, curr_symbol)}</td>
            <td class="num {net_class}">{fmt_currency(net, curr_symbol)}</td>
            <td class="num" style="white-space:nowrap">
                <span style="font-weight:600;color:var(--gold)">{pct_of_total:.1f}%</span>
                <div style="height:4px;background:var(--card-border);border-radius:2px;margin-top:3px;width:60px;display:inline-block;vertical-align:middle;margin-left:6px">
                    <div style="height:100%;width:{bar_width}%;background:var(--gold);border-radius:2px"></div>
                </div>
            </td>
        </tr>"""
    
    # Organic Winners
    organic_rows = ""
    for i, o in enumerate(organic_winners[:15], 1):
        series_str = ", ".join(o["series"]) if o["series"] else "Standalone"
        organic_rows += f"""
        <tr>
            <td class="rank">{i}</td>
            <td class="book-title">{o['title'][:50]}</td>
            <td class="num">{fmt_currency(o['gross'], curr_symbol)}</td>
            <td class="num">{fmt_number(o['kenp'])}</td>
            <td class="num">{o['units']}</td>
            <td class="series-info">{series_str[:40]}</td>
        </tr>"""
    
    # BSR-Revenue Correlation
    bsr_days = bsr_correlation[0]["days_of_data"] if bsr_correlation else 0
    bsr_rev_rows = ""
    for c in bsr_correlation[:25]:
        series_lbl = c.get("series_label", "")
        bsr_rev_rows += f"""
        <tr>
            <td class="num mono" style="text-align: right; padding-right: 1.5rem;">{c['bsr_us']:,}</td>
            <td class="book-title">
                <div style="font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{c['title']}</div>
                <div style="font-size: 0.7rem; color: var(--text-secondary);">{c['author']}</div>
            </td>
            <td style="font-size: 0.75rem; color: var(--text-secondary); text-align: left; padding-left: 0.5rem;">{series_lbl[:35]}</td>
            <td class="num" style="text-align: right;">{fmt_currency(c['gross_30day'], curr_symbol)}</td>
            <td class="num" style="text-align: right;">{fmt_number(c['kenp_30day'])}</td>
            <td class="num" style="text-align: right;">{c['units_30day']}</td>
        </tr>"""
    
    # ─── Full HTML ───
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vinci Books — Executive Performance Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        :root {{
            --black: {BRAND_BLACK};
            --gold: {BRAND_GOLD};
            --white: {BRAND_WHITE};
            --dark-bg: #0a0a0a;
            --card-bg: #141414;
            --card-border: #222;
            --text-primary: #f0f0f0;
            --text-secondary: #999;
            --text-muted: #666;
            --green: #00c853;
            --red: #ff1744;
            --amber: #ffab00;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--dark-bg);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }}
        
        /* Header */
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1.5rem 2rem;
            background: var(--black);
            border-bottom: 2px solid var(--gold);
            margin-bottom: 2rem;
        }}
        
        .header-left {{
            display: flex;
            align-items: center;
            gap: 1rem;
        }}
        
        .header-logo {{
            width: 40px;
            height: auto;
        }}
        
        .header-title h1 {{
            font-size: 1.5rem;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}
        
        .header-title .subtitle {{
            font-size: 0.75rem;
            color: var(--gold);
            text-transform: uppercase;
            letter-spacing: 2px;
        }}
        
        .header-right {{
            text-align: right;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }}
        
        .header-right .date {{
            font-size: 1.1rem;
            color: var(--white);
            font-weight: 600;
        }}
        
        /* Sections */
        .section {{
            margin-bottom: 3rem;
        }}
        
        .section-header {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 1.5rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid var(--card-border);
        }}
        
        .section-header h2 {{
            font-size: 1.3rem;
            font-weight: 700;
            color: var(--white);
        }}
        
        .section-header .section-badge {{
            background: var(--gold);
            color: var(--black);
            font-size: 0.65rem;
            font-weight: 700;
            padding: 0.2rem 0.5rem;
            border-radius: 3px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .section-desc {{
            color: var(--text-secondary);
            font-size: 0.85rem;
            margin-bottom: 1rem;
        }}
        
        /* KPI Grid */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }}
        
        .kpi-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 1.5rem;
            text-align: center;
        }}
        
        .kpi-value {{
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--gold);
            font-family: 'JetBrains Mono', 'SF Mono', monospace;
        }}
        
        .kpi-label {{
            font-size: 0.7rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-top: 0.5rem;
        }}
        
        .kpi-change {{
            font-size: 0.8rem;
            margin-top: 0.3rem;
            font-weight: 600;
        }}
        
        .kpi-sublabel {{
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-top: 0.3rem;
        }}
        
        .positive {{ color: var(--green); }}
        .negative {{ color: var(--red); }}
        
        /* Top Mover KPI card with cover thumbnail */
        .mover-kpi-inner {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            justify-content: center;
        }}
        .mover-cover {{
            width: 52px;
            height: 72px;
            object-fit: cover;
            border-radius: 4px;
            border: 1px solid var(--card-border);
            flex-shrink: 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.4);
        }}
        .mover-kpi-text {{
            text-align: left;
        }}
        .mover-author {{
            color: var(--text-secondary);
            font-size: 0.7rem;
            font-style: italic;
        }}
        
        /* Tables */
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
        }}
        
        .data-table th {{
            background: var(--card-bg);
            color: var(--gold);
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            padding: 0.75rem 1rem;
            text-align: center;
            border-bottom: 1px solid var(--card-border);
            position: sticky;
            top: 0;
        }}
        
        .data-table td {{
            padding: 0.6rem 1rem;
            border-bottom: 1px solid #1a1a1a;
            vertical-align: middle;
            text-align: center;
        }}
        
        .data-table tr:hover {{
            background: rgba(245, 197, 24, 0.03);
        }}
        
        .data-table .rank {{
            color: var(--text-muted);
            font-size: 0.75rem;
            width: 30px;
            text-align: center;
        }}
        
        .data-table .num {{
            text-align: center;
            font-family: 'JetBrains Mono', 'SF Mono', monospace;
            font-size: 0.8rem;
        }}
        
        .data-table .mono {{
            font-family: 'JetBrains Mono', 'SF Mono', monospace;
            text-align: center;
        }}
        
        /* Name/text columns stay left-aligned */
        .data-table .author-name,
        .data-table .series-name,
        .data-table .book-title {{
            text-align: left;
            font-weight: 500;
            max-width: 250px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        
        .table-wrapper {{
            overflow-x: auto;
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 8px;
        }}
        
        /* Readthrough */
        .rt-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 1.5rem;
        }}
        
        .rt-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
        }}
        
        .rt-card h4 {{
            font-size: 1rem;
            margin-bottom: 0.3rem;
        }}
        
        .rt-meta {{
            font-size: 0.75rem;
            color: var(--text-muted);
        }}
        
        .rt-composition {{
            font-size: 0.7rem;
            color: var(--gold);
            opacity: 0.75;
            margin-top: 0.25rem;
            font-family: 'JetBrains Mono', 'SF Mono', monospace;
            letter-spacing: 0.02em;
        }}
        
        .rt-badges {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin: 0.75rem 0;
            flex-grow: 1;  /* pushes bar chart to the bottom */
            align-content: flex-start;
        }}
        
        .rt-badge {{
            font-size: 0.7rem;
            padding: 0.2rem 0.5rem;
            border-radius: 3px;
            font-weight: 600;
            font-family: 'JetBrains Mono', 'SF Mono', monospace;
        }}
        
        .rt-green {{ background: rgba(0, 200, 83, 0.15); color: var(--green); border: 1px solid rgba(0, 200, 83, 0.3); }}
        .rt-amber {{ background: rgba(255, 171, 0, 0.15); color: var(--amber); border: 1px solid rgba(255, 171, 0, 0.3); }}
        .rt-red {{ background: rgba(255, 23, 68, 0.15); color: var(--red); border: 1px solid rgba(255, 23, 68, 0.3); }}
        
        /* Pure CSS Bar Chart */
        .rt-bar-chart {{
            width: 100%;
            margin-top: auto;  /* anchors chart to bottom of flex column */
            overflow-x: auto;
        }}
        .rt-bars-container {{
            display: flex;
            align-items: flex-end;
            gap: 4px;
            height: 160px;
            padding-bottom: 28px;
            position: relative;
        }}
        .rt-bars-container.tall {{
            height: 200px;
        }}
        .rt-bar-wrap {{
            display: flex;
            flex-direction: column;
            align-items: center;
            flex: 1;
            min-width: 28px;
            height: 100%;
            justify-content: flex-end;
            position: relative;
        }}
        .rt-bar {{
            width: 100%;
            border-radius: 3px 3px 0 0;
            transition: opacity 0.15s;
            position: relative;
            min-height: 2px;
        }}
        .rt-bar:hover {{
            opacity: 0.8;
        }}
        .rt-bar-label {{
            position: absolute;
            bottom: -24px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 9px;
            color: #666;
            white-space: nowrap;
            font-family: monospace;
        }}
        .rt-bar-value {{
            position: absolute;
            top: -18px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 9px;
            color: #aaa;
            white-space: nowrap;
            font-family: monospace;
            font-weight: 600;
        }}
        .rt-bar-tooltip {{
            display: none;
            position: absolute;
            bottom: calc(100% + 8px);
            left: 50%;
            transform: translateX(-50%);
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 4px;
            padding: 6px 10px;
            font-size: 11px;
            color: #eee;
            white-space: nowrap;
            z-index: 10;
            pointer-events: none;
        }}
        .rt-bar-wrap:hover .rt-bar-tooltip {{
            display: block;
        }}
        
        /* Warning box */
        .warning-box {{
            background: rgba(255, 171, 0, 0.08);
            border: 1px solid rgba(255, 171, 0, 0.3);
            border-radius: 8px;
            padding: 1.5rem;
            margin-top: 1.5rem;
        }}
        
        .warning-box h4 {{
            color: var(--amber);
            margin-bottom: 0.5rem;
        }}
        
        .warning-box p {{
            color: var(--text-secondary);
            font-size: 0.85rem;
            margin-bottom: 0.75rem;
        }}
        
        .warning-box ul {{
            list-style: none;
            padding: 0;
        }}
        
        .warning-box li {{
            font-size: 0.85rem;
            padding: 0.3rem 0;
            color: var(--text-primary);
        }}
        
        /* Benchmark legend */
        .benchmark-legend {{
            display: flex;
            gap: 1.5rem;
            flex-wrap: wrap;
            margin-bottom: 1.5rem;
            padding: 1rem;
            background: var(--card-bg);
            border-radius: 8px;
            border: 1px solid var(--card-border);
        }}
        
        .benchmark-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.8rem;
        }}
        
        .benchmark-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }}
        
        .benchmark-dot.green {{ background: var(--green); }}
        .benchmark-dot.amber {{ background: var(--amber); }}
        .benchmark-dot.red {{ background: var(--red); }}
        
        /* Two-column layout */
        .two-col {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
        }}
        
        .two-col .col-header {{
            font-size: 0.9rem;
            font-weight: 700;
            color: var(--gold);
            margin-bottom: 1rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        /* KPI Comparison Row */
        .kpi-comparison {{
            display: flex;
            gap: 1.5rem;
            flex-wrap: wrap;
            padding: 0.75rem 1rem;
            background: rgba(245,197,24,0.05);
            border: 1px solid rgba(245,197,24,0.15);
            border-radius: 6px;
            margin-top: 0.75rem;
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}
        .kpi-comparison span {{
            display: flex;
            gap: 0.4rem;
            align-items: center;
        }}
        
        /* Period Tabs */
        .period-tabs {{
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1rem;
        }}
        .period-tab {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            color: var(--text-secondary);
            padding: 0.4rem 1.2rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: all 0.15s;
        }}
        .period-tab:hover {{
            border-color: var(--gold);
            color: var(--gold);
        }}
        .period-tab.active {{
            background: var(--gold);
            border-color: var(--gold);
            color: var(--black);
        }}
        
        /* Footer */
        .footer {{
            text-align: center;
            padding: 2rem;
            color: var(--text-muted);
            font-size: 0.75rem;
            border-top: 1px solid var(--card-border);
            margin-top: 3rem;
        }}
        
        /* Responsive */
        @media (max-width: 768px) {{
            .container {{ padding: 1rem; }}
            .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .two-col {{ grid-template-columns: 1fr; }}
            .rt-grid {{ grid-template-columns: 1fr; }}
            .header {{ flex-direction: column; gap: 1rem; text-align: center; }}
            .header-right {{ text-align: center; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-left">
            <img src="data:image/png;base64,{logo_b64}" alt="Vinci Books" class="header-logo">
            <div class="header-title">
                <h1>Executive Performance Dashboard</h1>
                <div class="subtitle">Portfolio Intelligence Report</div>
            </div>
        </div>
        <div class="header-right">
            <div class="date">{report_date}</div>
            <div>Currency: {currency}</div>
        </div>
    </div>
    
    <div class="container">
        <!-- 1. Portfolio Overview -->
        <div class="section portfolio-section">
            <div class="section-header">
                <h2>Portfolio Overview</h2>
                <span class="section-badge">Multi-Period</span>
            </div>
            {kpi_cards}
        </div>
        
        <!-- 1b. Portfolio Pulse -->
        <div class="section">
            <div class="section-header">
                <h2>Portfolio Pulse</h2>
                <span class="section-badge">Live Signals</span>
            </div>
            <p class="section-desc">Real-time portfolio health signals. BSR Top 10K counts from the latest daily Supabase snapshot. Readthrough and organic metrics from the 90-day Publisher Champ window.</p>
            {pulse_html}
        </div>
        
        <!-- 2. Author-Level Economics -->
        <div class="section">
            <div class="section-header">
                <h2>Author Economics</h2>
                <span class="section-badge">P&L</span>
            </div>
            <p class="section-desc">All books grouped by author. Revenue includes ebook sales + KENP royalties. ROI = Gross Revenue / Ad Spend.</p>
            <div class="period-tabs">
                <button class="period-tab active" onclick="switchTab(this, 'author-30')">30-Day</button>
                <button class="period-tab" onclick="switchTab(this, 'author-90')">90-Day</button>
            </div>
            <div id="author-30" class="period-panel">
                <div class="table-wrapper">
                    <table class="data-table">
                        <thead><tr><th>#</th><th>Author</th><th>Books</th><th>Gross</th><th>Spend</th><th>Net</th><th>ROI</th><th>KENP</th></tr></thead>
                        <tbody>{author_rows_30}</tbody>
                    </table>
                </div>
            </div>
            <div id="author-90" class="period-panel" style="display:none">
                <div class="table-wrapper">
                    <table class="data-table">
                        <thead><tr><th>#</th><th>Author</th><th>Books</th><th>Gross</th><th>Spend</th><th>Net</th><th>ROI</th><th>KENP</th></tr></thead>
                        <tbody>{author_rows_90}</tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <!-- 3. Series Economics -->
        <div class="section">
            <div class="section-header">
                <h2>Series Economics</h2>
                <span class="section-badge">Funnel P&L</span>
            </div>
            <p class="section-desc">Series-level view. A Book 1 may show a loss individually, but the series as a whole may be highly profitable due to readthrough.</p>
            <div class="period-tabs">
                <button class="period-tab active" onclick="switchTab(this, 'series-30')">30-Day</button>
                <button class="period-tab" onclick="switchTab(this, 'series-90')">90-Day</button>
            </div>
            <div id="series-30" class="period-panel">
                <div class="table-wrapper">
                    <table class="data-table">
                        <thead><tr><th>#</th><th>Author</th><th>Series</th><th>Books</th><th>Gross</th><th>Spend</th><th>Net</th><th>ROI</th><th>KENP</th></tr></thead>
                        <tbody>{series_rows_30}</tbody>
                    </table>
                </div>
            </div>
            <div id="series-90" class="period-panel" style="display:none">
                <div class="table-wrapper">
                    <table class="data-table">
                        <thead><tr><th>#</th><th>Author</th><th>Series</th><th>Books</th><th>Gross</th><th>Spend</th><th>Net</th><th>ROI</th><th>KENP</th></tr></thead>
                        <tbody>{series_rows_90}</tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <!-- 4. Readthrough Funnels -->
        <div class="section">
            <div class="section-header">
                <h2>Readthrough Funnels</h2>
                <span class="section-badge">90-Day</span>
            </div>
            <p class="section-desc">KENP readthrough as percentage of the <strong>preceding book</strong> (step-by-step retention: Book 2 as % of Book 1, Book 3 as % of Book 2, etc.). Book 1 bar = 100% baseline. Hover bars for detail. 90-day rolling window for statistical significance.</p>
            <div class="benchmark-legend">
                <div class="benchmark-item"><div class="benchmark-dot green"></div> Meets/exceeds benchmark</div>
                <div class="benchmark-item"><div class="benchmark-dot amber"></div> Within 10pp of benchmark</div>
                <div class="benchmark-item"><div class="benchmark-dot red"></div> Below benchmark</div>
                <div class="benchmark-item" style="margin-left:auto; color:var(--text-muted);">Benchmarks: B1→B2 ≥50% | Subsequent ≥70% | After B2 ≥80%</div>
            </div>
            <div class="rt-grid">{rt_charts_html}</div>
            {rt_warnings}
        </div>
        
        <!-- 5. Author Readthrough Retention Ranking -->
        <div class="section">
            <div class="section-header">
                <h2>Author Readthrough Retention Ranking</h2>
                <span class="section-badge">Leaderboard</span>
            </div>
            <p class="section-desc">Authors ranked by their best Book 1→Book 2 readthrough rate across all series. This is the critical ad funnel conversion point — it measures how many Book 1 readers are sticky enough to buy Book 2. Industry benchmark: 50%+ is good, 60%+ is excellent.</p>
            <div class="table-wrapper">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Author</th>
                            <th title="Best Book 1→Book 2 readthrough across all their series. This is the ad funnel conversion point — the % of Book 1 readers who buy Book 2.">B1→B2 RT% ⓘ</th>
                            <th>Series</th>
                            <th>Best Series</th>
                        </tr>
                    </thead>
                    <tbody>{author_rt_rows}</tbody>
                </table>
            </div>
        </div>
        
        <!-- 6. Ad Efficiency -->
        <div class="section">
            <div class="section-header">
                <h2>Ad Efficiency</h2>
                <span class="section-badge">Funnel Economics</span>
            </div>
            <p class="section-desc">Evaluating Book 1 funnels at SERIES level. A profitable funnel means total series revenue exceeds total ad spend. <span style="color:var(--text-muted)">Minimum £1K gross revenue to qualify.</span></p>
            <div style="display:inline-block;background:var(--card-border);border-radius:4px;padding:4px 12px;font-size:0.75rem;color:var(--gold);font-weight:600;margin-bottom:1rem;">&#128197; Based on 30-day rolling data</div>
            
            <!-- Tier 1: Star Performers -->
            <div class="col-header" style="color: var(--gold); margin-bottom: 0.5rem;">⭐ Star Performers (ROI ≥ 300%)</div>
            <div class="table-wrapper" style="margin-bottom: 1.5rem;">
                <table class="data-table">
                    <colgroup>
                        <col style="width: 35%;">
                        <col style="width: 8%;">
                        <col style="width: 14%;">
                        <col style="width: 14%;">
                        <col style="width: 10%;">
                        <col style="width: 19%;">
                    </colgroup>
                    <thead><tr><th>Series / Author</th><th>Books</th><th>Spend</th><th>Gross</th><th>ROI</th><th>Cost/Reader <span style="font-size:0.65rem;font-weight:400;color:var(--text-muted);" title="Ad spend ÷ total readers acquired. Total readers = KU complete reads (full_reads) + paid ebook units + paperback units. A lower value means you are acquiring readers more efficiently.">(?)</span></th></tr></thead>
                    <tbody>{ad_star_rows}</tbody>
                </table>
            </div>
            
            <!-- Tier 2: Solid Performers -->
            <div class="col-header" style="color: var(--green); margin-bottom: 0.5rem;">✓ Solid Performers (ROI 200–300%)</div>
            <div class="table-wrapper" style="margin-bottom: 1.5rem;">
                <table class="data-table">
                    <colgroup>
                        <col style="width: 35%;">
                        <col style="width: 8%;">
                        <col style="width: 14%;">
                        <col style="width: 14%;">
                        <col style="width: 10%;">
                        <col style="width: 19%;">
                    </colgroup>
                    <thead><tr><th>Series / Author</th><th>Books</th><th>Spend</th><th>Gross</th><th>ROI</th><th>Cost/Reader <span style="font-size:0.65rem;font-weight:400;color:var(--text-muted);" title="Ad spend ÷ total readers acquired. Total readers = KU complete reads (full_reads) + paid ebook units + paperback units. A lower value means you are acquiring readers more efficiently.">(?)</span></th></tr></thead>
                    <tbody>{ad_solid_rows}</tbody>
                </table>
            </div>
            
            <!-- Tier 3: Burning Money -->
            <div class="col-header" style="color: var(--red); margin-bottom: 0.5rem;">✗ Burning Money (ROI &lt; 200%)</div>
            <div class="table-wrapper">
                <table class="data-table">
                    <colgroup>
                        <col style="width: 35%;">
                        <col style="width: 8%;">
                        <col style="width: 14%;">
                        <col style="width: 14%;">
                        <col style="width: 10%;">
                        <col style="width: 19%;">
                    </colgroup>
                    <thead><tr><th>Series / Author</th><th>Books</th><th>Spend</th><th>Gross</th><th>ROI</th><th>£ Loss</th></tr></thead>
                    <tbody>{ad_burning_rows}</tbody>
                </table>
            </div>
        </div>
        
        <!-- 7. Market Breakdown -->
        <div class="section">
            <div class="section-header">
                <h2>Market Breakdown</h2>
                <span class="section-badge">By Country</span>
            </div>
            <p class="section-desc">Revenue and spend by marketplace. All values converted to {currency}.</p>
            <div class="table-wrapper">
                <table class="data-table">
                    <thead><tr><th>Country</th><th>Revenue</th><th>Ad Spend</th><th>Net</th><th>% of Total</th></tr></thead>
                    <tbody>{country_rows}</tbody>
                </table>
            </div>
        </div>
        
        <!-- 8. True Algorithmic Winners -->
        <div class="section">
            <div class="section-header">
                <h2>True Algorithmic Winners</h2>
                <span class="section-badge">Zero Ad Spend</span>
            </div>
            <p class="section-desc">Titles generating revenue with absolutely zero advertising spend. Confirmed organic performers.</p>
            <div class="table-wrapper">
                <table class="data-table">
                    <thead><tr><th>#</th><th>Title</th><th>Gross</th><th>KENP</th><th>Units</th><th>Series</th></tr></thead>
                    <tbody>{organic_rows}</tbody>
                </table>
            </div>
        </div>
        
        <!-- 9. BSR-Revenue Correlation -->
        <div class="section">
            <div class="section-header">
                <h2>BSR-Revenue Correlation</h2>
                <span class="section-badge">US Market</span>
            </div>
            <p class="section-desc">Average US BSR rank cross-referenced with 30-day Publisher Champ revenue. BSR is averaged across all available daily snapshots — the average stabilises as tracking accumulates. Sorted by best (lowest) average rank.</p>
            <p style="font-size: 0.75rem; color: var(--amber); margin-bottom: 1rem;">&#9432; Avg BSR based on {bsr_days} day(s) of tracking data (BSR tracking started May 15, 2026 — average will improve as history grows)</p>
            <div class="table-wrapper">
                <table class="data-table" style="table-layout: fixed; width: 100%;">
                    <colgroup>
                        <col style="width: 10%;">
                        <col style="width: 35%;">
                        <col style="width: 15%;">
                        <col style="width: 15%;">
                        <col style="width: 10%;">
                        <col style="width: 15%;">
                    </colgroup>
                    <thead>
                        <tr>
                            <th style="text-align: right; padding-right: 1.5rem;">Avg BSR (US)</th>
                            <th style="text-align: left;">Title / Author</th>
                            <th style="text-align: left; padding-left: 0.5rem;">Series</th>
                            <th style="text-align: right;">30-Day Gross</th>
                            <th style="text-align: right;">KENP</th>
                            <th style="text-align: right;">Units</th>
                        </tr>
                    </thead>
                    <tbody>{bsr_rev_rows}</tbody>
                </table>
            </div>
        </div>
    </div>
    
    <div class="footer">
        <p>Vinci Books Executive Performance Dashboard | Generated {report_date} | Data: Publisher Champ API + Amazon BSR Tracking</p>
        <p>Confidential — For Internal Use Only</p>
    </div>
    
    <script>
        // Tab switching for period views — scoped to the containing section
        function switchTab(btn, panelId) {{
            // Deactivate all sibling tabs
            const tabGroup = btn.parentElement;
            tabGroup.querySelectorAll('.period-tab').forEach(t => t.classList.remove('active'));
            btn.classList.add('active');
            // Hide all period-panels that are siblings of the tab group's parent
            const section = tabGroup.closest('.section, .portfolio-section');
            if (section) {{
                section.querySelectorAll('.period-panel').forEach(p => {{ p.style.display = 'none'; }});
            }}
            const target = document.getElementById(panelId);
            if (target) target.style.display = 'block';
        }}
    </script>
</body>
</html>"""
    
    return html


# ─── Snapshot Management ─────────────────────────────────────────────────────

def save_daily_snapshot(portfolio, series_30, readthrough_90, author_rankings):
    """Save a daily snapshot for trend tracking."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    snapshot = {
        "date": today,
        "portfolio": {
            "gross": portfolio["total_gross_30"],
            "spend": portfolio["total_spend_30"],
            "net": portfolio["total_net_30"],
            "kenp": portfolio["total_kenp_30"],
            "roi": portfolio["roi_30"],
            "books": portfolio["total_books"],
        },
        "top_series": [
            {"name": s["name"], "gross": s["total_gross"], "net": s["total_net"], "roi": s["roi"]}
            for s in series_30[:10]
        ],
        "top_readthrough": [
            {"series": r["series_name"], "book1_to_2": r["book1_to_2"]}
            for r in readthrough_90[:10]
        ],
        "top_authors_rt": [
            {"author": a["author"], "avg_rt": a["avg_readthrough"]}
            for a in author_rankings[:10]
        ],
    }
    
    snapshot_file = SNAPSHOTS_DIR / f"snapshot_{today}.json"
    with open(snapshot_file, "w") as f:
        json.dump(snapshot, f, indent=2)
    
    print(f"📸 Snapshot saved: {snapshot_file}")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("═" * 60)
    print("  VINCI BOOKS — Executive Performance Dashboard Generator v2")
    print("═" * 60)
    print()
    
    # Check for --extract flag
    if "--extract" in sys.argv:
        extract_all_data()
        print()
    
    # Load data
    print("📂 Loading data...")
    books_30 = load_book_data("30day")
    books_90 = load_book_data("90day")
    books_ytd = load_book_data("ytd2026")
    books_ytd_ly = load_book_data("ytd2025_sameperiod")
    books_fy2025 = load_book_data("fy2025")
    books_fy2024 = load_book_data("fy2024")
    books_lifetime = load_book_data("lifetime")
    country_30 = load_country_data("30day")
    author_data = load_author_data()
    bsr_data = load_bsr_data()
    
    print(f"   → 30-day books: {len(books_30)}")
    print(f"   → 90-day books: {len(books_90)}")
    print(f"   → YTD 2026 books: {len(books_ytd)}")
    print(f"   → YTD 2025 same-period books: {len(books_ytd_ly)}")
    print(f"   → FY 2025 books: {len(books_fy2025)}")
    print(f"   → FY 2024 books: {len(books_fy2024)}")
    print(f"   → Lifetime books: {len(books_lifetime)}")
    print(f"   → Authors: {len(author_data)}")
    print(f"   → BSR records: {len(bsr_data)}")
    
    if not books_30:
        print("❌ No book data available. Run with --extract flag first.")
        sys.exit(1)
    
    # Compute analytics
    print("\n📊 Computing analytics...")
    
    print("   → Building author map...")
    asin_to_author = build_asin_to_author_map()
    print(f"      {len(asin_to_author)} ASINs mapped to authors")
    
    print("   → Portfolio overview...")
    portfolio = compute_portfolio_overview(books_30, books_90, country_30)
    
    print("   → Author economics (30-day)...")
    authors = compute_author_economics(author_data, books_30)
    
    print("   → Author economics (90-day)...")
    authors_90_view = compute_author_economics_from_books(books_90, asin_to_author)
    
    print("   → Series economics (30-day)...")
    series_30 = compute_series_economics(books_30, "30-day", asin_to_author)
    
    print("   → Series economics (90-day)...")
    series_90 = compute_series_economics(books_90, "90-day", asin_to_author)
    
    print("   → Readthrough funnels (90-day)...")
    readthrough_90 = compute_readthrough(series_90, "90-day")
    
    print("   → Readthrough funnels (30-day)...")
    readthrough_30 = compute_readthrough(compute_series_economics(books_30, asin_to_author=asin_to_author), "30-day")
    
    print("   → Author readthrough ranking...")
    author_rankings = compute_author_readthrough_ranking(readthrough_90, series_90)
    
    print("   → Ad efficiency...")
    ad_funnels = compute_ad_efficiency(series_30)
    
    print("   → Organic winners...")
    organic_winners = compute_organic_winners(books_30)
    
    print("   → BSR-Revenue correlation...")
    bsr_correlation = compute_bsr_revenue_correlation(books_30, bsr_data)
    
    print("   → Portfolio pulse (BSR Top 10K + movers)...")
    pulse = compute_portfolio_pulse(bsr_data, readthrough_90, books_30, asin_to_author)
    
    # Generate HTML
    print("\n🎨 Generating HTML report...")
    books_mtd = load_book_data("mtd2026")
    books_mtd_ly = load_book_data("mtd2025")
    
    html = generate_html(
        portfolio, authors, authors_90_view, series_30, series_90,
        readthrough_90, readthrough_30, author_rankings,
        ad_funnels, organic_winners, bsr_correlation,
        country_30, books_30, books_90, books_ytd, books_ytd_ly, books_fy2025,
        books_mtd=books_mtd, books_mtd_ly=books_mtd_ly,
        pulse=pulse,
        books_fy2024=books_fy2024,
        books_lifetime=books_lifetime,
    )
    
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    file_size = OUTPUT_FILE.stat().st_size
    print(f"\n✅ Report saved to: {OUTPUT_FILE}")
    print(f"   File size: {file_size / 1024:.1f} KB")
    
    # Save daily snapshot
    save_daily_snapshot(portfolio, series_30, readthrough_90, author_rankings)
    
    print(f"\n{'═' * 60}")
    print(f"  Dashboard ready. Open in any browser to view.")
    print(f"{'═' * 60}")


if __name__ == "__main__":
    main()
