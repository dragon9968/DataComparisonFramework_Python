import polars as pl
from models.module_config import ModuleConfig

class DataComparator:

    @classmethod
    def compare_polars_dfs(cls, df_source: pl.DataFrame, df_target: pl.DataFrame, config: ModuleConfig) -> dict:
        """Vectorized reconciliation comparator capable of processing 600,000+ rows in sub-seconds."""
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

        # 1. High-Speed Hash Full Outer Join on Polars C/Rust Engine
        joined = df_source.join(
            df_target,
            on="final_key",
            how="full",
            suffix="_target"
        )

        mismatches = []
        mismatch_no = 1
        MAX_MISMATCHES = 5000

        # 2. Missing Records in Target
        missing_in_target = joined.filter(pl.col("final_key_target").is_null())
        if missing_in_target.height > 0:
            keys = missing_in_target.get_column("final_key").to_list()
            for k in keys:
                if mismatch_no > MAX_MISMATCHES:
                    break
                mismatches.append({
                    "no": mismatch_no,
                    "key": k,
                    "column": "ALL_FIELDS",
                    "expected": "DATA AVAILABLE",
                    "actual": "MISSING IN FILE EXTRACT",
                    "issue": "MISSING RECORD"
                })
                mismatch_no += 1

        # 3. Missing Records in Source
        missing_in_source = joined.filter(pl.col("final_key").is_null())
        if missing_in_source.height > 0:
            keys = missing_in_source.get_column("final_key_target").to_list()
            for k in keys:
                if mismatch_no > MAX_MISMATCHES:
                    break
                mismatches.append({
                    "no": mismatch_no,
                    "key": k,
                    "column": "ALL_FIELDS",
                    "expected": "MISSING IN FILE EXTRACT",
                    "actual": "DATA AVAILABLE",
                    "issue": "MISSING RECORD"
                })
                mismatch_no += 1

        # 4. Instant Series-level Column Comparison for Matched Keys
        matched = joined.filter(pl.col("final_key").is_not_null() & pl.col("final_key_target").is_not_null())

        if matched.height > 0:
            keys_series = matched["final_key"]
            for col in compare_cols:
                if mismatch_no > MAX_MISMATCHES:
                    break
                target_col = f"{col}_target" if f"{col}_target" in matched.columns else col

                s_exp = matched[col]
                s_act = matched[target_col]

                # Fast check: If entire column series is 100% identical, skip instantly (0.0001s)
                if s_exp.equals(s_act):
                    continue

                # Vectorized index extraction for rows with differences
                diff_indices = (s_exp != s_act).arg_true()
                if len(diff_indices) > 0:
                    sub_keys = keys_series[diff_indices].to_list()
                    sub_exp = s_exp[diff_indices].to_list()
                    sub_act = s_act[diff_indices].to_list()

                    limit = min(len(sub_keys), MAX_MISMATCHES - mismatch_no + 1)
                    for i in range(limit):
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