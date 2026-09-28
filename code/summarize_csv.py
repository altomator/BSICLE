#!/usr/bin/env python3
"""
CSV Data Summarizer Script
--------------------------
Reads a CSV data file and generates a detailed summary ("résumé") of its structure,
data quality, missing values, descriptive statistics, and sample records.
Filter by centuries and export a new dataset

python summarize_csv.py C:/Users/dams0003363/Desktop/Manuscrits/Recette_MNS/Manuscrits/dataset_10k.csv -o ./ -e latin-1 --export-csv C:/Users/dams0003363/Desktop/Manuscrits/Recette_MNS/Manuscrits/dataset_century_5_15.csv --min-century 5 --max-century 15 --sep "\t"
"""

import sys
import argparse
from pathlib import Path
import pandas as pd


def detect_delimiter_and_encoding(filepath: Path) -> tuple[str, str]:
    """Detects file encoding and CSV delimiter automatically."""
    encodings_to_try = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    delimiters_to_try = [',', ';', '\t', '|']
    
    detected_encoding = 'utf-8'
    detected_delimiter = ','

    for enc in encodings_to_try:
        try:
            with open(filepath, 'r', encoding=enc, errors='strict') as f:
                first_lines = [f.readline() for _ in range(5)]
                sample = "".join(first_lines)
                if not sample:
                    continue
                detected_encoding = enc
                
                # Count delimiter frequencies in sample
                counts = {d: sample.count(d) for d in delimiters_to_try}
                best_delim = max(counts, key=counts.get)
                if counts[best_delim] > 0:
                    detected_delimiter = best_delim
                break
        except (UnicodeDecodeError, Exception):
            continue

    return detected_delimiter, detected_encoding


def summarize_csv(filepath: str, sep: str = None, encoding: str = None) -> str:
    """Reads a CSV file and generates a formatted text report summarizing its contents."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    # Detect delimiter and encoding if not explicitly provided
    auto_sep, auto_enc = detect_delimiter_and_encoding(path)
    final_sep = sep if sep else auto_sep
    final_enc = encoding if encoding else auto_enc

    file_size_mb = path.stat().st_size / (1024 * 1024)

    # Read CSV into DataFrame
    try:
        df = pd.read_csv(path, sep=final_sep, encoding=final_enc, low_memory=False)
    except Exception as err:
        # Fallback reading with python engine
        df = pd.read_csv(path, sep=None, engine='python', encoding=final_enc)

    num_rows, num_cols = df.shape
    mem_usage_mb = df.memory_usage(deep=True).sum() / (1024 * 1024)

    lines = []
    lines.append("=" * 75)
    lines.append(f" CSV DATA SUMMARY REPORT: {path.name}")
    lines.append("=" * 75)
    lines.append(f"• File Path:       {path.resolve()}")
    lines.append(f"• File Size:       {file_size_mb:.2f} MB ({path.stat().st_size:,} bytes)")
    lines.append(f"• RAM Memory:      {mem_usage_mb:.2f} MB")
    lines.append(f"• Encoding Used:   {final_enc}")
    lines.append(f"• Delimiter Used:  {repr(final_sep)}")
    lines.append(f"• Total Rows:      {num_rows:,}")
    lines.append(f"• Total Columns:   {num_cols}")
    lines.append(f"• Total Cells:     {num_rows * num_cols:,}")

    if df.empty:
        lines.append("\n[Warning] CSV file is empty.")
        return "\n".join(lines)

    # Data Quality & Duplicate Rows
    dup_rows = df.duplicated().sum()
    dup_pct = (dup_rows / num_rows * 100) if num_rows > 0 else 0
    lines.append(f"• Duplicate Rows:  {dup_rows:,} ({dup_pct:.1f}%)")

    # Column Details Table
    lines.append("\n" + "-" * 75)
    lines.append(" 1. COLUMN DETAILS & MISSING VALUES")
    lines.append("-" * 75)

    col_info = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        null_count = df[col].isnull().sum()
        null_pct = (null_count / num_rows * 100) if num_rows > 0 else 0
        unique_cnt = df[col].nunique(dropna=True)
        col_info.append({
            "Column Name": str(col),
            "Type": dtype,
            "Non-Null": f"{num_rows - null_count:,}",
            "Missing": f"{null_count:,}",
            "Missing %": f"{null_pct:.1f}%",
            "Unique Values": f"{unique_cnt:,}"
        })
    col_df = pd.DataFrame(col_info)
    lines.append(col_df.to_string(index=False))

    # Numerical Columns Statistics
    numeric_df = df.select_dtypes(include=['number'])
    if not numeric_df.empty:
        lines.append("\n" + "-" * 75)
        lines.append(" 2. NUMERICAL COLUMNS STATISTICS")
        lines.append("-" * 75)
        stats = numeric_df.describe().T[['mean', 'std', 'min', '25%', '50%', '75%', 'max']]
        stats.rename(columns={'50%': 'median'}, inplace=True)
        lines.append(stats.to_string())
        # count the values for column century and express in %
        century_counts = df["century"].value_counts(dropna=True).sort_index()
        lines.append("\n" + "-" * 75)
        lines.append(" 2.1. CENTURY COUNTS")
        lines.append("-" * 75)
        for century, count in century_counts.items():
            lines.append(f"• {century}: {count:,} ({count / num_rows * 100:.1f}%)")

    # Text / Categorical Columns Breakdown
    cat_df = df.select_dtypes(include=['object', 'category', 'string', 'bool'])
    if not cat_df.empty:
        lines.append("\n" + "-" * 75)
        lines.append(" 3. CATEGORICAL / TEXT COLUMNS (TOP VALUES)")
        lines.append("-" * 75)
        for col in cat_df.columns:
            top = df[col].value_counts(dropna=True).head(5)
            val_strs = [f"'{k}': {v:,}" for k, v in top.items()]
            top_formatted = ", ".join(val_strs) if val_strs else "None"
            lines.append(f"• [{col}] (Unique: {df[col].nunique():,}) -> Top 5: {top_formatted}")

    # First 5 Rows Preview
    lines.append("\n" + "-" * 75)
    lines.append(" 4. DATA PREVIEW (FIRST 5 ROWS)")
    lines.append("-" * 75)
    lines.append(df.head(5).to_string())

    lines.append("\n" + "=" * 75 + "\n")
    return "\n".join(lines)


def filter_by_century(
    filepath: str,
    output_filepath: str = None,
    min_century: float = 5.0,
    max_century: float = 15.0,
    century_col: str = "century",
    sep: str = None,
    encoding: str = None
) -> pd.DataFrame:
    """
    Filters CSV rows where the century column is between min_century and max_century (inclusive: 5 <= century <= 15).
    Exports a new CSV file with the exact same columns and delimiter.
    
    Parameters:
        filepath (str): Input CSV file path.
        output_filepath (str, optional): Destination path for the new CSV file.
        min_century (float): Minimum century value (default: 5).
        max_century (float): Maximum century value (default: 15).
        century_col (str): Century column name (default: 'century').
        sep (str, optional): CSV delimiter. Auto-detected if None.
        encoding (str, optional): File encoding. Auto-detected if None.

    Returns:
        pd.DataFrame: Filtered DataFrame.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    auto_sep, auto_enc = detect_delimiter_and_encoding(path)
    final_sep = sep if sep else auto_sep
    final_enc = encoding if encoding else auto_enc

    df = pd.read_csv(path, sep=final_sep, encoding=final_enc, low_memory=False)

    if century_col not in df.columns:
        raise KeyError(f"Column '{century_col}' not found in CSV. Available columns: {list(df.columns)}")

    # Convert century column values to numeric (coerce non-numeric to NaN)
    numeric_century = pd.to_numeric(df[century_col], errors='coerce')

    # Filter lines where min_century <= century <= max_century
    mask = (numeric_century >= min_century) & (numeric_century <= max_century)
    filtered_df = df[mask].copy()

    print(f"\n[Filtering] Found {len(filtered_df):,} / {len(df):,} rows with century between {min_century} and {max_century}.")

    if output_filepath:
        out_path = Path(output_filepath)
        filtered_df.to_csv(out_path, sep=final_sep, index=False, encoding=final_enc)
        print(f"[Export] Filtered CSV saved to: {out_path.resolve()}")

    return filtered_df


def main():
    parser = argparse.ArgumentParser(description="Summarize and filter a CSV data file")
    parser.add_argument("filepath", nargs="?", default="dataset_20k.csv", help="Path to the CSV file (default: dataset_20k.csv)")
    parser.add_argument("-s", "--sep", help="CSV delimiter (e.g. ',' ';' '\\t'). Auto-detected if omitted.")
    parser.add_argument("-e", "--encoding", help="File encoding (e.g. 'utf-8', 'latin-1'). Auto-detected if omitted.")
    parser.add_argument("-o", "--output", help="Path to save the summary report text file")
    
    # Century filtering options
    parser.add_argument("--filter-century", action="store_true", help="Enable century filtering (5 <= century <= 15)")
    parser.add_argument("--min-century", type=float, default=5.0, help="Minimum century value (default: 5.0)")
    parser.add_argument("--max-century", type=float, default=15.0, help="Maximum century value (default: 15.0)")
    parser.add_argument("--export-csv", help="Path to export the filtered CSV file (default: dataset_century_5_15.csv)")

    args = parser.parse_args()

    try:
        report = summarize_csv(args.filepath, sep=args.sep, encoding=args.encoding)
        print(report)

        if args.output:
            out_path = Path(args.output)
            out_path.write_text(report, encoding="utf-8")
            print(f"\n[Success] Summary report saved to: {out_path.resolve()}")

        quit()
        
        # Perform century filtering if requested or if --export-csv specified
        if args.filter_century or args.export_csv:
            export_path = args.export_csv if args.export_csv else "dataset_century_5_15.csv"
            filter_by_century(
                filepath=args.filepath,
                output_filepath=export_path,
                min_century=args.min_century,
                max_century=args.max_century,
                sep=args.sep,
                encoding=args.encoding
            )

    except Exception as err:
        print(f"Error processing CSV file: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()


