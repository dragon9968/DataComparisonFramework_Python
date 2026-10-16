import os
import csv
import re
import time
import polars as pl
from models.module_config import ModuleConfig
from utils.excel_reader import ExcelReader
from commons.global_constants import GlobalConstants
from utils.file_utils import FileUtils

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
    def compare_polars_dfs(cls, df_source: pl.DataFrame, df_target: pl.DataFrame, config: ModuleConfig, is_row_aligned: bool = False) -> dict:
        """Optimized reconciliation comparator. Direct vectorized check when row-aligned; full outer join otherwise."""
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
        mismatches = []
        mismatch_no = 1

        # ULTRA-FAST PATH: When row counts match and rows are physically aligned (no JOIN overhead)
        if is_row_aligned and total_source_rows == total_target_rows:
            keys_series = df_source["final_key"]
            for col in compare_cols:
                s_exp = df_source[col]
                s_act = df_target[col]

                # Fast check: skip identical columns instantly (~0.001s)
                if s_exp.equals(s_act):
                    continue

                diff_indices = (s_exp != s_act).arg_true()
                if len(diff_indices) == 0:
                    continue

                sub_exp = s_exp[diff_indices]
                sub_act = s_act[diff_indices]

                # Run normalization only on differing rows
                sub_exp_clean = ExcelReader.normalize_column_series(sub_exp, col)
                sub_act_clean = ExcelReader.normalize_column_series(sub_act, col)

                real_diff_sub = (sub_exp_clean != sub_act_clean).arg_true()
                if len(real_diff_sub) > 0:
                    real_diff_indices = diff_indices[real_diff_sub]
                    sub_keys = keys_series[real_diff_indices].to_list()
                    final_exp = sub_exp_clean[real_diff_sub].to_list()
                    final_act = sub_act_clean[real_diff_sub].to_list()

                    for i in range(len(sub_keys)):
                        mismatches.append({
                            "no": mismatch_no,
                            "key": sub_keys[i],
                            "column": col,
                            "expected": final_exp[i],
                            "actual": final_act[i],
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

        # ROBUST FULL-OUTER-JOIN PATH: Used when row counts differ to isolate missing records
        joined = df_source.join(
            df_target,
            on="final_key",
            how="full",
            suffix="_target"
        )

        missing_in_target = joined.filter(pl.col("final_key_target").is_null())
        if missing_in_target.height > 0:
            keys = missing_in_target.get_column("final_key").to_list()
            for k in keys:
                mismatches.append({
                    "no": mismatch_no,
                    "key": k,
                    "column": "ALL_FIELDS",
                    "expected": "DATA AVAILABLE",
                    "actual": "NOT IN EXTRACT FILE",
                    "issue": "MISSING RECORD"
                })
                mismatch_no += 1

        missing_in_source = joined.filter(pl.col("final_key").is_null())
        if missing_in_source.height > 0:
            keys = missing_in_source.get_column("final_key_target").to_list()
            for k in keys:
                mismatches.append({
                    "no": mismatch_no,
                    "key": k,
                    "column": "ALL_FIELDS",
                    "expected": "NOT IN RAW FILE",
                    "actual": "DATA AVAILABLE",
                    "issue": "MISSING RECORD"
                })
                mismatch_no += 1

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
                if len(diff_indices) == 0:
                    continue

                sub_exp = s_exp[diff_indices]
                sub_act = s_act[diff_indices]

                sub_exp_clean = ExcelReader.normalize_column_series(sub_exp, col)
                sub_act_clean = ExcelReader.normalize_column_series(sub_act, target_col)

                real_diff_sub = (sub_exp_clean != sub_act_clean).arg_true()
                if len(real_diff_sub) > 0:
                    real_diff_indices = diff_indices[real_diff_sub]
                    sub_keys = keys_series[real_diff_indices].to_list()
                    final_exp = sub_exp_clean[real_diff_sub].to_list()
                    final_act = sub_act_clean[real_diff_sub].to_list()

                    for i in range(len(sub_keys)):
                        mismatches.append({
                            "no": mismatch_no,
                            "key": sub_keys[i],
                            "column": col,
                            "expected": final_exp[i],
                            "actual": final_act[i],
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
    def compare_large_files_batched(cls, source_path: str, target_path: str, config: ModuleConfig, batch_size: int = 200000) -> dict:
        """Stream and reconcile massive files using batch streaming and auto-key synchronization."""
        import pandas as pd
        print(f"\n🚀 [LARGE FILE MODE] Counting total rows in file for progress tracking...", flush=True)
        total_source_lines = cls._count_total_lines_fast(source_path)
        total_target_lines = cls._count_total_lines_fast(target_path)

        user_key = getattr(config, "key_columns", getattr(config, "keyColumns", ""))
        user_key_columns = [k.strip() for k in (user_key if isinstance(user_key, str) else ",".join(user_key or [])).split(",") if k.strip()]

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
        total_mismatches_count = 0
        top_200_mismatches = []
        global_mismatch_no = 1
        use_row_key = False
        detected_keys = None

        start_time = time.time()
        batch_count = 0

        current_offset_src = 2
        current_offset_tgt = 2

        FileUtils.create_directory_if_not_exists(str(GlobalConstants.OUTPUT_PATH))
        module_name_val = getattr(config, "module_name", getattr(config, "moduleName", "Unknown_Module"))
        safe_module_name = re.sub(r'[\\/:*?"<>|]', '_', str(module_name_val))
        csv_filename = f"{safe_module_name}_Discrepancies.csv"
        csv_path = os.path.join(GlobalConstants.OUTPUT_PATH, csv_filename)

        csv_file = None
        csv_writer = None

        try:
            for pdf_src, pdf_tgt in zip(reader_src, reader_tgt):
                batch_count += 1

                df_src_raw = pl.from_pandas(pdf_src)
                df_tgt_raw = pl.from_pandas(pdf_tgt)

                is_last_src = df_src_raw.height < batch_size
                is_last_tgt = df_tgt_raw.height < batch_size

                df_src_clean_raw = ExcelReader.truncate_metadata(df_src_raw) if is_last_src else df_src_raw
                df_tgt_clean_raw = ExcelReader.truncate_metadata(df_tgt_raw) if is_last_tgt else df_tgt_raw

                # Determine key strategy dynamically on the initial batch
                if batch_count == 1:
                    if user_key_columns:
                        detected_keys = user_key_columns
                        use_row_key = False
                    else:
                        if is_last_src and is_last_tgt:
                            use_row_key = (df_src_clean_raw.height == df_tgt_clean_raw.height)
                        else:
                            use_row_key = (total_source_lines > 0 and total_source_lines == total_target_lines)

                        if not use_row_key and detected_keys is None:
                            detected_keys = ExcelReader.auto_detect_key_columns(df_src_clean_raw)

                df_src_clean = ExcelReader.normalize_dataframe_batch(
                    df_src_clean_raw, 
                    config, 
                    start_row_index=current_offset_src,
                    is_last_batch=False,
                    use_row_key=use_row_key,
                    custom_keys=detected_keys
                )
                df_tgt_clean = ExcelReader.normalize_dataframe_batch(
                    df_tgt_clean_raw, 
                    config, 
                    start_row_index=current_offset_tgt,
                    is_last_batch=False,
                    use_row_key=use_row_key,
                    custom_keys=detected_keys
                )

                current_offset_src += df_src_clean.height
                current_offset_tgt += df_tgt_clean.height

                total_src_rows += df_src_clean.height
                total_tgt_rows += df_tgt_clean.height

                batch_result = cls.compare_polars_dfs(df_src_clean, df_tgt_clean, config, is_row_aligned=use_row_key)
                batch_mismatches = batch_result["mismatches"]

                if batch_mismatches:
                    if csv_writer is None:
                        try:
                            csv_file = open(csv_path, mode="w", newline="", encoding="utf-8-sig")
                        except PermissionError:
                            alt_filename = f"{safe_module_name}_Discrepancies_{int(time.time())}.csv"
                            csv_path = os.path.join(GlobalConstants.OUTPUT_PATH, alt_filename)
                            csv_filename = alt_filename
                            csv_file = open(csv_path, mode="w", newline="", encoding="utf-8-sig")

                        csv_writer = csv.writer(csv_file)
                        csv_writer.writerow(["NO.", "KEY", "COLUMN NAME", "EXPECTED (DATA)", "ACTUAL (SHARETEC)", "ISSUES"])

                    for m in batch_mismatches:
                        m["no"] = global_mismatch_no
                        if len(top_200_mismatches) < 200:
                            top_200_mismatches.append(m)
                        csv_writer.writerow([m["no"], m["key"], m["column"], m["expected"], m["actual"], m["issue"]])
                        global_mismatch_no += 1

                    total_mismatches_count += len(batch_mismatches)

                elapsed = time.time() - start_time
                if total_source_lines > 0:
                    if is_last_src:
                        pct = 100.0
                    else:
                        pct = min(99.9, (total_src_rows / total_source_lines) * 100)
                    bar_len = 15
                    filled = int(bar_len * pct // 100)
                    bar = "=" * filled + "-" * (bar_len - filled)
                    progress_str = f"[{bar}] {pct:.1f}% | {total_src_rows:,}/{total_source_lines:,} rows"
                else:
                    progress_str = f"{total_src_rows:,} rows processed"

                print(f"  ⏳ Batch {batch_count:02d} {progress_str} | Mismatches: {total_mismatches_count:,} | Time: {elapsed:.1f}s", flush=True)
        except StopIteration:
            pass
        finally:
            if csv_file is not None:
                csv_file.close()

        status = "FAILED" if total_mismatches_count > 0 else "PASSED"

        return {
            "status": status,
            "total_source_rows": total_src_rows,
            "total_target_rows": total_tgt_rows,
            "total_mismatches": total_mismatches_count,
            "mismatches": top_200_mismatches,
            "csv_filename": csv_filename if total_mismatches_count > 0 else ""
        }