import os
import sys
import time
import polars as pl
from models.module_config import ModuleConfig
from utils.excel_reader import ExcelReader

class DataComparator:

    @staticmethod
    def _count_total_lines_fast(file_path: str) -> int:
        """Count total lines rapidly via raw binary chunks without loading dataset into RAM."""
        try:
            with open(file_path, "rb") as f:
                return sum(buffer.count(b"\n") for buffer in iter(lambda: f.read(8 * 1024 * 1024), b""))
        except Exception:
            return 0

    @classmethod
    def compare_polars_dfs(cls, df_source: pl.DataFrame, df_target: pl.DataFrame, config: ModuleConfig) -> dict:
        """Vectorized reconciliation comparator for standard in-memory DataFrames."""
        total_source_rows = df_source.height if df_source is not None else 0
        total_target_rows = df_target.height if df_target is not None else 0

        if total_source_rows == 0 and total_target_rows == 0:
            return {
                "status": "PASSED",
                "total_source_rows": 0,
                "total_target_rows": 0,
                "mismatches": []
            }

        compare_cols = [c for c in df_source.columns if c != "final_key"]

        joined = df_source.join(
            df_target,
            on="final_key",
            how="full",
            suffix="_target"
        )

        mismatches = []
        mismatch_no = 1

        # Check for missing records in target
        missing_in_target = joined.filter(pl.col("final_key_target").is_null())
        if missing_in_target.height > 0:
            keys = missing_in_target.get_column("final_key").to_list()
            for k in keys:
                mismatches.append({
                    "no": mismatch_no,
                    "key": k,
                    "column": "ALL_FIELDS",
                    "expected": "DATA AVAILABLE",
                    "actual": "MISSING IN FILE EXTRACT",
                    "issue": "MISSING RECORD"
                })
                mismatch_no += 1

        # Check for missing records in source
        missing_in_source = joined.filter(pl.col("final_key").is_null())
        if missing_in_source.height > 0:
            keys = missing_in_source.get_column("final_key_target").to_list()
            for k in keys:
                mismatches.append({
                    "no": mismatch_no,
                    "key": k,
                    "column": "ALL_FIELDS",
                    "expected": "MISSING IN FILE EXTRACT",
                    "actual": "DATA AVAILABLE",
                    "issue": "MISSING RECORD"
                })
                mismatch_no += 1

        # Vectorized column-by-column variance check for matched keys
        matched = joined.filter(pl.col("final_key").is_not_null() & pl.col("final_key_target").is_not_null())

        if matched.height > 0:
            keys_series = matched["final_key"]
            for col in compare_cols:
                target_col = f"{col}_target" if f"{col}_target" in matched.columns else col

                s_exp = matched[col]
                s_act = matched[target_col]

                if s_exp.equals(s_act):
                    continue

                diff_indices = (s_exp != s_act).arg_true()
                if len(diff_indices) > 0:
                    sub_keys = keys_series[diff_indices].to_list()
                    sub_exp = s_exp[diff_indices].to_list()
                    sub_act = s_act[diff_indices].to_list()

                    for i in range(len(sub_keys)):
                        mismatches.append({
                            "no": mismatch_no,
                            "key": sub_keys[i],
                            "column": col,
                            "expected": sub_exp[i],
                            "actual": sub_act[i],
                            "issue": "VARIANCE"
                        })
                        mismatch_no += 1

        status = "FAILED" if len(mismatches) > 0 else "PASSED"

        return {
            "status": status,
            "total_source_rows": total_source_rows,
            "total_target_rows": total_target_rows,
            "mismatches": mismatches
        }

    @classmethod
    def compare_large_files_batched(cls, source_path: str, target_path: str, config: ModuleConfig, batch_size: int = 150000) -> dict:
        """Stream and reconcile large CSV dumps in-memory using robust Pandas chunking."""
        import pandas as pd
        print(f"\n🚀 [LARGE FILE MODE] Counting total rows in file for progress tracking...", flush=True)
        total_source_lines = cls._count_total_lines_fast(source_path)
        
        # Use pandas chunksize to safely read malformed CSV lines without shifting columns.
        # keep_default_na=False ensures empty fields become "" instead of NaN.
        reader_src = pd.read_csv(
            source_path, chunksize=batch_size, dtype=str, 
            encoding="utf-8", encoding_errors="replace", keep_default_na=False
        )
        reader_tgt = pd.read_csv(
            target_path, chunksize=batch_size, dtype=str, 
            encoding="utf-8", encoding_errors="replace", keep_default_na=False
        )

        total_src_rows = 0
        total_tgt_rows = 0
        all_mismatches = []
        global_mismatch_no = 1

        start_time = time.time()
        batch_count = 0

        current_offset_src = 2
        current_offset_tgt = 2

        try:
            for pdf_src, pdf_tgt in zip(reader_src, reader_tgt):
                batch_count += 1

                df_src_raw = pl.from_pandas(pdf_src)
                df_tgt_raw = pl.from_pandas(pdf_tgt)

                # Check if this is the final batch
                is_last_src = df_src_raw.height < batch_size
                is_last_tgt = df_tgt_raw.height < batch_size

                df_src_clean = ExcelReader.normalize_dataframe_batch(
                    df_src_raw, 
                    config, 
                    start_row_index=current_offset_src,
                    is_last_batch=is_last_src
                )
                df_tgt_clean = ExcelReader.normalize_dataframe_batch(
                    df_tgt_raw, 
                    config, 
                    start_row_index=current_offset_tgt,
                    is_last_batch=is_last_tgt
                )

                current_offset_src += df_src_raw.height
                current_offset_tgt += df_tgt_raw.height

                total_src_rows += df_src_clean.height
                total_tgt_rows += df_tgt_clean.height

                batch_result = cls.compare_polars_dfs(df_src_clean, df_tgt_clean, config)

                for m in batch_result["mismatches"]:
                    m["no"] = global_mismatch_no
                    all_mismatches.append(m)
                    global_mismatch_no += 1

                elapsed = time.time() - start_time
                if total_source_lines > 0:
                    pct = min(100.0, (total_src_rows / total_source_lines) * 100)
                    bar_len = 15
                    filled = int(bar_len * pct // 100)
                    bar = "=" * filled + "-" * (bar_len - filled)
                    progress_str = f"[{bar}] {pct:.1f}% | {total_src_rows:,}/{total_source_lines:,} rows"
                else:
                    progress_str = f"{total_src_rows:,} rows processed"

                print(f"  ⏳ Batch {batch_count:02d} {progress_str} | Mismatches: {len(all_mismatches):,} | Time: {elapsed:.1f}s", flush=True)
        except StopIteration:
            pass

        status = "FAILED" if len(all_mismatches) > 0 else "PASSED"

        return {
            "status": status,
            "total_source_rows": total_src_rows,
            "total_target_rows": total_tgt_rows,
            "mismatches": all_mismatches
        }