import os
import itertools
import polars as pl
from models.module_config import ModuleConfig

class ExcelReader:

    @classmethod
    def read_raw_dataframe(cls, file_path: str, sheet_name: str = None) -> pl.DataFrame:
        """Read raw data file into a Polars DataFrame without upfront normalization."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"❌ Data file not found at: {file_path}")

        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext in [".csv", ".d"]:
            import pandas as pd
            pdf = pd.read_csv(
                file_path, 
                dtype=str, 
                encoding="utf-8", 
                encoding_errors="replace",
                keep_default_na=False
            )
            return pl.from_pandas(pdf)
        elif file_ext in [".xlsx", ".xlsm", ".xls"]:
            df = pl.read_excel(file_path, sheet_name=sheet_name) if sheet_name else pl.read_excel(file_path)
            return df.select([pl.all().cast(pl.Utf8)])
        else:
            raise ValueError(f"❌ Unsupported format '{file_ext}' for file: {file_path}")

    @classmethod
    def truncate_metadata(cls, df: pl.DataFrame) -> pl.DataFrame:
        """Truncate Progress metadata trailers at the bottom of the DataFrame."""
        if df is None or df.height == 0:
            return pl.DataFrame()

        first_col_raw = df.columns[0]
        first_col_clean = (
            df[first_col_raw]
            .fill_null("")
            .cast(pl.Utf8)
            .str.replace_all(r'[\r\n\t\xa0]', "")
            .str.strip_chars()
            .str.to_lowercase()
        )

        is_meta = (
            first_col_clean.is_in([".", "psc"]) |
            first_col_clean.str.contains(
                r"^(filename=|records=|ldbname=|timestamp=|numformat=|dateformat=|cpstream=|\.$)"
            )
        )

        tail_check_size = min(50, df.height)
        tail_meta = is_meta.tail(tail_check_size)
        meta_indices = tail_meta.arg_true()

        if len(meta_indices) > 0:
            cut_offset = (df.height - tail_check_size) + meta_indices[0]
            df = df.slice(0, cut_offset)

        return df

    @classmethod
    def auto_detect_key_columns(cls, df: pl.DataFrame) -> list[str]:
        """
        Dynamically discover natural primary key columns when row counts differ.
        Filters out measure/amount columns, ranks by cardinality, and returns optimal identifiers.
        """
        if df is None or df.height == 0:
            return []

        sample = df.head(1000)
        sample_rows = sample.height
        cols = [c for c in sample.columns if c not in ("physical_row_idx", "_row_num")]
        if not cols:
            return []

        metric_keywords = (
            "amt", "amount", "bal", "balance", "rate", "pct", "fee", 
            "sum", "total", "cost", "val", "price", "limit", "cur", "ytd", "mtd"
        )
        id_keywords = (
            "num", "id", "code", "key", "no", "tell", "station", "box", 
            "acct", "mbr", "user", "seq", "dt", "date", "type", "name", "desc", "gl"
        )

        eligible_cols = [c for c in cols if not any(mk in c.lower() for mk in metric_keywords)]
        if not eligible_cols:
            eligible_cols = cols

        id_candidates = [c for c in eligible_cols if any(ik in c.lower() for ik in id_keywords)]
        candidates = id_candidates if id_candidates else eligible_cols

        cardinalities = {c: sample[c].n_unique() for c in candidates}
        candidates = [c for c in candidates if cardinalities[c] > 1]
        candidates.sort(key=lambda c: cardinalities[c], reverse=True)

        if not candidates:
            return []

        # 1. Check for single column with 100% uniqueness
        for col in candidates:
            if cardinalities[col] == sample_rows:
                return [col]

        # 2. Check 2-column combinations
        top_pool = candidates[:8]
        best_combo = None
        best_unique_cnt = 0

        for c1, c2 in itertools.combinations(top_pool, 2):
            u_cnt = sample.select([c1, c2]).n_unique()
            if u_cnt == sample_rows:
                return [c1, c2]
            if u_cnt > best_unique_cnt:
                best_unique_cnt = u_cnt
                best_combo = [c1, c2]

        # 3. Check 3-column combinations
        for c1, c2, c3 in itertools.combinations(top_pool[:5], 3):
            u_cnt = sample.select([c1, c2, c3]).n_unique()
            if u_cnt == sample_rows:
                return [c1, c2, c3]
            if u_cnt > best_unique_cnt:
                best_unique_cnt = u_cnt
                best_combo = [c1, c2, c3]

        # 4. Return highest cardinality combination (duplicate instances are disambiguated by cum_count)
        if best_combo:
            return best_combo

        return [candidates[0]]

    @classmethod
    def normalize_column_series(cls, series: pl.Series, col_name: str) -> pl.Series:
        """On-demand normalization pipeline applied only to values with variances."""
        col_lower = col_name.strip().lower()
        bool_keywords = ("log", "convert", "status", "flag", "indicator", "is-")

        expr = (
            pl.col("_val")
            .fill_null("")
            .cast(pl.Utf8)
            .str.replace_all(r'[\r\n\t\xa0]', "")
            .str.strip_chars()
            .str.replace(r"^\?$", "")
            .str.replace(r"\.0$", "")
            .str.replace(r"^\.(\d+)", r"0.$1")
            .str.replace(r"^-\.(\d+)", r"-0.$1")
            .str.replace(r"^0+?([1-9]\d*|0)$", r"$1")
            .str.replace(r" 00:00:00$", "")
            .str.replace(r"T00:00:00$", "")
            .str.replace(r"^(\d{4})[/-]0*([1-9]\d?)[/-]0*([1-9]\d?)$", r"$2/$3/$1")
            .str.replace(r"^0*([1-9]\d?)[/-]0*([1-9]\d?)[/-]([3-9]\d)$", r"$1/$2/19$3")
            .str.replace(r"^0*([1-9]\d?)[/-]0*([1-9]\d?)[/-]([0-2]\d)$", r"$1/$2/20$3")
            .str.replace(r"^0*([1-9]\d?)[/-]0*([1-9]\d?)[/-](\d{4})$", r"$1/$2/$3")
            .str.replace(r"(?i)^true$", "TRUE")
            .str.replace(r"(?i)^false$", "FALSE")
        )

        if any(kw in col_lower for kw in bool_keywords):
            expr = expr.str.to_uppercase()

        return series.alias("_val").to_frame().select(expr).to_series()

    @classmethod
    def normalize_dataframe_batch(
        cls, 
        df: pl.DataFrame, 
        config: ModuleConfig, 
        start_row_index: int = 2,
        is_last_batch: bool = True,
        use_row_key: bool = False,
        custom_keys: list[str] = None
    ) -> pl.DataFrame:
        """Fast batch normalization supporting physical ROW indexing or Auto Key Discovery."""
        if df is None or df.height == 0:
            return pl.DataFrame()

        if is_last_batch and df.height > 0:
            df = cls.truncate_metadata(df)

        if df.height == 0:
            return pl.DataFrame()

        header_map = {col.strip().lower(): col for col in df.columns}
        compare_cols = getattr(config, "compare_columns", getattr(config, "compareColumns", []))
        actual_compare_cols = compare_cols if compare_cols else list(df.columns)

        # C-level whitespace trimming executed instantly (~0.05s) across all columns
        exprs = []
        for col_name in actual_compare_cols:
            actual_col = header_map.get(col_name.lower())
            if actual_col:
                exprs.append(
                    pl.col(actual_col)
                    .fill_null("")
                    .cast(pl.Utf8)
                    .str.strip_chars()
                    .alias(col_name)
                )
            else:
                exprs.append(pl.lit("").alias(col_name))

        df_clean = df.select(exprs)

        key_cols = getattr(config, "key_columns", getattr(config, "keyColumns", ""))
        key_columns_str = key_cols if isinstance(key_cols, str) else ",".join(key_cols or [])
        user_key_columns = [k.strip() for k in key_columns_str.split(",") if k.strip()]

        valid_keys = [k for k in user_key_columns if k in df_clean.columns]

        if not valid_keys and not use_row_key:
            if custom_keys:
                valid_keys = [k for k in custom_keys if k in df_clean.columns]
            else:
                valid_keys = cls.auto_detect_key_columns(df_clean)

        if valid_keys and not use_row_key:
            key_exprs = [
                pl.col(k)
                .fill_null("")
                .cast(pl.Utf8)
                .str.strip_chars()
                .str.replace(r"\.0$", "")
                .str.replace(r"^0+?([1-9]\d*|0)$", r"$1")
                .str.replace(r" 00:00:00$", "")
                .str.replace(r"^(\d{4})[/-]0*([1-9]\d?)[/-]0*([1-9]\d?)$", r"$2/$3/$1")
                .str.replace(r"^0*([1-9]\d?)[/-]0*([1-9]\d?)[/-]([3-9]\d)$", r"$1/$2/19$3")
                .str.replace(r"^0*([1-9]\d?)[/-]0*([1-9]\d?)[/-]([0-2]\d)$", r"$1/$2/20$3")
                .str.replace(r"^0*([1-9]\d?)[/-]0*([1-9]\d?)[/-](\d{4})$", r"$1/$2/$3")
                for k in valid_keys
            ]
            df_clean = df_clean.with_columns(
                base_key=pl.concat_str(key_exprs, separator="_")
            )
        else:
            # Physical spreadsheet row index (e.g. ROW_2, ROW_3...)
            df_clean = df_clean.with_columns(
                base_key=pl.concat_str([
                    pl.lit("ROW_"), 
                    pl.int_range(start_row_index, start_row_index + pl.len()).cast(pl.Utf8)
                ])
            )

        has_duplicates = df_clean["base_key"].is_duplicated().any()

        if not has_duplicates:
            df_clean = df_clean.rename({"base_key": "final_key"})
        else:
            df_clean = df_clean.with_columns(
                total_cnt=pl.col("base_key").count().over("base_key"),
                occurrence=pl.col("base_key").cum_count().over("base_key")
            ).with_columns(
                final_key=pl.when(pl.col("total_cnt") == 1)
                .then(pl.col("base_key"))
                .otherwise(
                    pl.concat_str([
                        pl.col("base_key"),
                        pl.lit("("),
                        pl.col("occurrence").cast(pl.Utf8),
                        pl.lit(")")
                    ])
                )
            ).drop(["base_key", "total_cnt", "occurrence"])

        return df_clean

    @classmethod
    def read_file_to_polars_df(
        cls, 
        file_path: str, 
        config: ModuleConfig, 
        is_source: bool = True,
        use_row_key: bool = False,
        custom_keys: list[str] = None
    ) -> pl.DataFrame:
        """Read standard sized files into an in-memory Polars DataFrame."""
        exp_sheet = getattr(config, "expected_sheet_name", getattr(config, "expectedSheetName", None))
        act_sheet = getattr(config, "actual_sheet_name", getattr(config, "actualSheetName", None))
        sheet_name = exp_sheet if is_source else act_sheet
        df_raw = cls.read_raw_dataframe(file_path, sheet_name=sheet_name)
        return cls.normalize_dataframe_batch(
            df_raw, config, start_row_index=2, is_last_batch=True,
            use_row_key=use_row_key, custom_keys=custom_keys
        )