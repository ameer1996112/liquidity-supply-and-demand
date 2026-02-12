#!/usr/bin/env python3
"""
Convert CSV training data to Parquet format for faster loading

BENEFITS:
- 5-10x faster loading than CSV
- 50-80% smaller file size (compressed)
- Preserves data types (no inference needed)
- Columnar format (read only needed columns)

USAGE:
  python ml/convert_to_parquet.py ml/training_data.csv
  python ml/convert_to_parquet.py ml/training_data.csv --output ml/optimized_data.parquet
"""

import pandas as pd
import argparse
from pathlib import Path
import os


def convert_csv_to_parquet(csv_path, output_path=None):
    """Convert CSV to Parquet with optimal compression"""

    csv_path = Path(csv_path)

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    # Auto-generate output path
    if output_path is None:
        output_path = csv_path.with_suffix('.parquet')
    else:
        output_path = Path(output_path)

    print(f"📂 Converting: {csv_path}")
    print(f"   → {output_path}")

    # Get original file size
    csv_size = os.path.getsize(csv_path) / 1024**2  # MB

    # Load CSV
    print("\n📥 Loading CSV...")
    df = pd.read_csv(csv_path)
    print(f"   Rows: {len(df):,}")
    print(f"   Columns: {len(df.columns)}")
    print(f"   CSV size: {csv_size:.2f} MB")

    # Optimize data types to save space
    print("\n🔧 Optimizing data types...")
    for col in df.columns:
        # Convert integers to smallest possible type
        if df[col].dtype in ['int64', 'int32']:
            col_min = df[col].min()
            col_max = df[col].max()

            if col_min >= 0 and col_max <= 255:
                df[col] = df[col].astype('uint8')
            elif col_min >= -128 and col_max <= 127:
                df[col] = df[col].astype('int8')
            elif col_min >= 0 and col_max <= 65535:
                df[col] = df[col].astype('uint16')
            elif col_min >= -32768 and col_max <= 32767:
                df[col] = df[col].astype('int16')
            elif col_min >= -2147483648 and col_max <= 2147483647:
                df[col] = df[col].astype('int32')

        # Convert floats to float32 (sufficient for ML)
        elif df[col].dtype == 'float64':
            df[col] = df[col].astype('float32')

    # Save as Parquet with compression
    print("\n💾 Saving Parquet with snappy compression...")
    df.to_parquet(
        output_path,
        engine='pyarrow',
        compression='snappy',  # Fast compression (good balance)
        index=False
    )

    # Get parquet file size
    parquet_size = os.path.getsize(output_path) / 1024**2  # MB
    compression_ratio = (1 - parquet_size / csv_size) * 100

    print("\n" + "=" * 60)
    print("✅ CONVERSION COMPLETE!")
    print("=" * 60)
    print(f"CSV size:      {csv_size:.2f} MB")
    print(f"Parquet size:  {parquet_size:.2f} MB")
    print(f"Savings:       {compression_ratio:.1f}%")
    print(f"\n📁 Output: {output_path}")
    print("\n💡 Usage:")
    print(f"   python ml/train_ai_guardian_v3_lightgbm.py --data {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert CSV to Parquet")
    parser.add_argument('csv_file', help='Path to CSV file')
    parser.add_argument('--output', '-o', help='Output Parquet path (optional)')

    args = parser.parse_args()

    try:
        convert_csv_to_parquet(args.csv_file, args.output)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
