import os
import polars as pl
from models.module_config import ModuleConfig

class ExcelReader:

    @classmethod
    def normalize_column_series(cls, series: pl.Series, col_name: str) -> pl.Series:
        """On-demand normalization pipeline applied only to columns with variances."""
        col_lower = col_name.strip().lower()
        bool_keywords = ("log", "convert", "status", "flag", "indicator", "is-")

        # Standardize series name to a fixed identifier '_val' so expression resolution never fails
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

        # Alias to '_val' before turning into a single-column DataFrame to prevent column name lookup mismatch
        return series.alias("_val").to_frame().select(expr).to_series()

    @classmethod
    def normalize_dataframe_batch(
        cls, 
        df: pl.DataFrame, 
        config: ModuleConfig, 
        start_row_index: int = 2,
        is_last_batch: bool = True
    ) -> pl.DataFrame:
        """Fast preliminary batch ingestion with metadata truncation and dynamic key generation."""
        if df is None or df.height == 0:
            return pl.DataFrame()

        # 1. Truncate Progress metadata trailers only on the final batch of the file
        if is_last_batch and df.height > 0:
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

        if df.height == 0:
            return pl.DataFrame()

        # 2. Fast column cast to Utf8 string without evaluating heavy regex pipelines upfront
        header_map = {col.strip().lower(): col for col in df.columns}
        compare_cols = getattr(config, "compare_columns", getattr(config, "compareColumns", []))
        actual_compare_cols = compare_cols if compare_cols else list(df.columns)

        exprs = []
        for col_name in actual_compare_cols:
            actual_col = header_map.get(col_name.lower())
            if actual_col:
                exprs.append(pl.col(actual_col).fill_null("").cast(pl.Utf8).alias(col_name))
            else:
                exprs.append(pl.lit("").alias(col_name))

        df_clean = df.select(exprs)

        # 3. Dynamic key resolution or fallback to row index
        key_cols = getattr(config, "key_columns", getattr(config, "keyColumns", ""))
        key_columns_str = key_cols if isinstance(key_cols, str) else ",".join(key_cols or [])
        user_key_columns = [k.strip() for k in key_columns_str.split(",") if k.strip()]

        valid_keys = [k for k in user_key_columns if k in df_clean.columns]

        if valid_keys:
            key_exprs = [
                pl.col(k).fill_null("").cast(pl.Utf8).str.strip_chars().str.replace(r"\.0$", "")
                for k in valid_keys
            ]
            df_clean = df_clean.with_columns(
                base_key=pl.concat_str(key_exprs, separator="_")
            )
        else:
            df_clean = df_clean.with_columns(
                base_key=pl.concat_str([
                    pl.lit("ROW_"), 
                    pl.int_range(start_row_index, start_row_index + pl.len()).cast(pl.Utf8)
                ])
            )

        # 4. Handle duplicate keys if any
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
    def read_file_to_polars_df(cls, file_path: str, config: ModuleConfig, is_source: bool = True) -> pl.DataFrame:
        """Read standard sized files into an in-memory Polars DataFrame."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"❌ Data file not found at: {file_path}")

        file_ext = os.path.splitext(file_path)[1].lower()
        exp_sheet = getattr(config, "expected_sheet_name", getattr(config, "expectedSheetName", None))
        act_sheet = getattr(config, "actual_sheet_name", getattr(config, "actualSheetName", None))
        sheet_name = exp_sheet if is_source else act_sheet

        if file_ext in [".csv", ".d"]:
            import pandas as pd
            pdf = pd.read_csv(
                file_path, 
                dtype=str, 
                encoding="utf-8", 
                encoding_errors="replace",
                keep_default_na=False
            )
            df = pl.from_pandas(pdf)
        elif file_ext in [".xlsx", ".xlsm", ".xls"]:
            df = pl.read_excel(file_path, sheet_name=sheet_name) if sheet_name else pl.read_excel(file_path)
            df = df.select([pl.all().cast(pl.Utf8)])
        else:
            raise ValueError(f"❌ Unsupported format '{file_ext}' for file: {file_path}")

        return cls.normalize_dataframe_batch(df, config, start_row_index=2, is_last_batch=True)