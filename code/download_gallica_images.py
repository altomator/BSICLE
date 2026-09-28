#!/usr/bin/env python3
"""
Gallica IIIF Image Downloader Script
------------------------------------
Reads a CSV dataset containing Gallica ARK identifiers (e.g., dataset_century_5_15.csv),
queries the Gallica Pagination API to discover the total page count for each document,
and downloads the IIIF v3 images into individual folders under `img_export/<ARK>/`.
"""

import os
import sys
import time
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import urllib.error
import pandas as pd

# timer between requests
iiif_timer = 0.2

# Standard User-Agent to avoid HTTP 403 Forbidden from Gallica servers
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}


def get_total_pages_gallica(ark_id: str, headers: dict = None, max_retries: int = 3) -> int:
    """
    Queries the Gallica Pagination API to obtain the number of pages/views for a given ARK.
    API Endpoint: https://gallica.bnf.fr/services/Pagination?ark=ark:/12148/{ark_id}
    """
    if headers is None:
        headers = DEFAULT_HEADERS

    clean_ark = ark_id.strip()
    if not clean_ark.startswith("ark:/12148/"):
        full_ark_param = f"ark:/12148/{clean_ark}"
    else:
        full_ark_param = clean_ark

    url = f"https://gallica.bnf.fr/services/Pagination?ark={full_ark_param}"

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                xml_data = resp.read()
            
            root = ET.fromstring(xml_data)
            
            # Extract all <ordre> values to find maximum page order
            ordres = [int(o.text) for o in root.findall('.//ordre') if o.text and o.text.isdigit()]
            if ordres:
                return max(ordres)

            # Alternative XML fallback: count of <structure> tags
            structures = root.findall('.//structure')
            if structures:
                return len(structures)

            return 0
        except (urllib.error.HTTPError, urllib.error.URLError, ET.ParseError) as err:
            if attempt == max_retries:
                print(f"[Warning] Failed to fetch pagination for {clean_ark}: {err}", file=sys.stderr)
                return 0
            time.sleep(1.0 * attempt)

    return 0


def download_single_image(
    ark_id: str,
    page_num: int,
    output_dir: Path,
    image_size: str = "max",
    headers: dict = None,
    max_retries: int = 3,
    skip_existing: bool = True
) -> bool:
    """
    Downloads a single IIIF image for a document page.
    IIIF API Endpoint: https://openapi.bnf.fr/iiif/image/v3/ark:/12148/{ark_id}/f{page_num}/full/{image_size}/0/default.jpg
    """
    
    

    if headers is None:
        headers = DEFAULT_HEADERS

    clean_ark = ark_id.replace("ark:/12148/", "").strip()
    dest_file = output_dir / f"{clean_ark}_f{page_num}.jpg"

    if skip_existing and dest_file.exists() and dest_file.stat().st_size > 0:
        print(f"Image {dest_file} already exists, skipping...")
        return True

    # wait a bit
    print(f"Waiting {iiif_timer} seconds before next request...")
    time.sleep(iiif_timer)
    
    url = f"https://openapi.bnf.fr/iiif/image/v3/ark:/12148/{clean_ark}/f{page_num}/full/{image_size}/0/default.jpg"

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()

            if resp.status == 200 and len(data) > 0:
                dest_file.write_bytes(data)
                return True
        except (urllib.error.HTTPError, urllib.error.URLError) as err:
            if attempt == max_retries:
                print(f"   └─ [Error] Page f{page_num} download failed ({err}): {url}", file=sys.stderr)
                return False
            time.sleep(1.0 * attempt)

    return False


def process_document(
    ark_id: str,
    export_base_dir: Path,
    image_size: str = "max",
    max_pages_limit: int = None,
    max_workers: int = 4,
    skip_existing: bool = True
) -> dict:
    """
    Processes a single document: fetches page count, creates folder, downloads images.
    """
    clean_ark = ark_id.replace("ark:/12148/", "").strip()
    doc_dir = export_base_dir / clean_ark
    doc_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[Document] Processing ARK: {clean_ark}")
    total_pages = get_total_pages_gallica(clean_ark)

    if total_pages == 0:
        print(f" └─ [Warning] 0 pages found for ARK {clean_ark}")
        return {"ark": clean_ark, "total_pages": 0, "downloaded": 0}

    pages_to_download = range(1, total_pages + 1)
    if max_pages_limit and max_pages_limit < total_pages:
        print(f" └─ Found {total_pages} page(s). Downloading first {max_pages_limit} page(s) (limited by settings).")
        pages_to_download = range(1, max_pages_limit + 1)
    else:
        print(f" └─ Found {total_pages} page(s). Starting download...")

    success_count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                download_single_image,
                clean_ark,
                page_num,
                doc_dir,
                image_size,
                DEFAULT_HEADERS,
                3,
                skip_existing
            ): page_num for page_num in pages_to_download
        }

        for future in as_completed(futures):
            if future.result():
                success_count += 1

    print(f" └─ Completed: {success_count}/{len(pages_to_download)} image(s) downloaded in {doc_dir.resolve()}")

    return {
        "ark": clean_ark,
        "total_pages": total_pages,
        "downloaded": success_count
    }


def download_gallica_dataset(
    csv_path: str,
    output_base_dir: str = "img_export",
    ark_col: str = "arkName",
    max_docs: int = None,
    max_pages_per_doc: int = None,
    image_size: str = "max",
    max_workers: int = 4,
    skip_existing: bool = True,
    sep: str = ";"
) -> None:
    """
    Reads a CSV dataset of Gallica ARKs and downloads IIIF images for each document.
    """
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    # Read CSV
    try:
        df = pd.read_csv(csv_file, sep=sep)
    except Exception:
        df = pd.read_csv(csv_file, sep=None, engine='python')

    if ark_col not in df.columns:
        raise KeyError(f"Column '{ark_col}' not found in CSV. Columns present: {list(df.columns)}")

    arks = df[ark_col].dropna().unique().tolist()
    if max_docs:
        arks = arks[:max_docs]

    export_dir = Path(output_base_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    print("==========================================================================")
    print(" GALLICA IIIF IMAGE DOWNLOADER")
    print("==========================================================================")
    print(f"• Input CSV:        {csv_file.resolve()}")
    print(f"• Target Directory: {export_dir.resolve()}")
    print(f"• Total Documents:  {len(arks):,}")
    print(f"• Image Size:       {image_size}")
    if max_pages_per_doc:
        print(f"• Max Pages/Doc:    {max_pages_per_doc}")
    print("==========================================================================")

    stats = []
    for idx, ark in enumerate(arks, 1):
        print(f"\nProgress: [{idx}/{len(arks)}]")
        res = process_document(
            ark_id=str(ark),
            export_base_dir=export_dir,
            image_size=image_size,
            max_pages_limit=max_pages_per_doc,
            max_workers=max_workers,
            skip_existing=skip_existing
        )
        stats.append(res)

    total_downloaded = sum(s["downloaded"] for s in stats)
    print("\n==========================================================================")
    print(" DOWNLOAD SUMMARY COMPLETE")
    print("==========================================================================")
    print(f"• Processed Documents: {len(stats):,}")
    print(f"• Total Images Saved:  {total_downloaded:,}")
    print(f"• Export Location:     {export_dir.resolve()}")
    print("==========================================================================")


def main():
    parser = argparse.ArgumentParser(description="Download Gallica IIIF images for ARKs in a CSV file")
    parser.add_argument("csv_path", nargs="?", default="dataset_century_5_15.csv", help="Input CSV file path")
    parser.add_argument("-o", "--output-dir", default="img_export", help="Output directory (default: img_export)")
    parser.add_argument("--ark-col", default="arkName", help="Name of ARK column in CSV (default: arkName)")
    parser.add_argument("-n", "--max-docs", type=int, help="Limit maximum number of documents to download")
    parser.add_argument("-p", "--max-pages", type=int, help="Limit maximum pages per document (e.g. 5)")
    parser.add_argument("--size", default="pct:50", help="IIIF v3 size parameter: 'max', 'pct:50', '1000,', etc. (default: pct:50)")
    parser.add_argument("-w", "--workers", type=int, default=1, help="Concurrent image download threads per doc (default: 1)")
    parser.add_argument("--no-skip", action="store_true", help="Redownload images even if already present")
    parser.add_argument("-s", "--sep", default=";", help="CSV separator (default: ';')")

    args = parser.parse_args()

    try:
        download_gallica_dataset(
            csv_path=args.csv_path,
            output_base_dir=args.output_dir,
            ark_col=args.ark_col,
            max_docs=args.max_docs,
            max_pages_per_doc=args.max_pages,
            image_size=args.size,
            max_workers=args.workers,
            skip_existing=not args.no_skip,
            sep=args.sep
        )
    except Exception as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
