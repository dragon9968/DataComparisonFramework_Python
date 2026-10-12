import os
import gc
import polars as pl
from models.module_config import ModuleConfig

class ExcelReader:

    @classmethod
    def normalize_dataframe_batch(cls, df: pl.DataFrame, config: ModuleConfig, start_row_index: int = 2) -> pl.DataFrame:
        """Normalize DataFrame batch with intelligent metadata trailer truncation."""
        if df is None or df.height == 0:
            return pl.DataFrame()

        # 1. Truncate Metadata Trailer (remove trailing metadata lines like ., PSC, filename=, records=, etc.)
        first_col_raw = df.columns[0]
        first_col_clean = (
            df[first_col_raw]
            .fill_null("")
            .cast(pl.Utf8)
            .str.replace_all(r'[\r\n\t\xa0"]', "")
            .str.strip_chars()
            .str.to_lowercase()
        )

        is_meta = (
            first_col_clean.is_in([".", "psc", "0."]) |
            first_col_clean.str.contains(
                r"^(filename=|records=|ldbname=|timestamp=|numformat=|dateformat=|cpstream=|\.|\d{6,12}$)"
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

        # 2. Vectorized Column Normalization
        header_map = {col.strip().lower(): col for col in df.columns}
        actual_compare_cols = config.compare_columns if config.compare_columns else list(df.columns)

        exprs = []
        for col_name in actual_compare_cols:
            actual_col = header_map.get(col_name.lower())
            if actual_col:
                expr = (
                    pl.col(actual_col)
                    .fill_null("")
                    .cast(pl.Utf8)
                    .str.replace_all(r'[\r\n\t\xa0"]', "")
                    .str.strip_chars()
                    .str.replace(r"^\?$", "")  # Convert standalone '?' to blank string
                    .str.replace(r"\.0$", "")
                    .str.replace(r"^\.(\d+)", r"0.$1")
                    .str.replace(r"^0+?([1-9]\d*|0)$", r"$1")
                    # Universal Date Normalization applied to all columns
                    .str.replace(r" 00:00:00$", "")
                    .str.replace(r"T00:00:00$", "")
                    .str.replace(r"^(\d{4})[/-]0*([1-9]\d?)[/-]0*([1-9]\d?)$", r"$2/$3/$1")
                    .str.replace(r"^0*([1-9]\d?)[/-]0*([1-9]\d?)[/-]([3-9]\d)$", r"$1/$2/19$3")
                    .str.replace(r"^0*([1-9]\d?)[/-]0*([1-9]\d?)[/-]([0-2]\d)$", r"$1/$2/20$3")
                    .str.replace(r"^0*([1-9]\d?)[/-]0*([1-9]\d?)[/-](\d{4})$", r"$1/$2/$3")
                )

                exprs.append(expr.alias(col_name))
            else:
                exprs.append(pl.lit("").alias(col_name))

        df_clean = df.select(exprs)

        # 3. Fast-Path Key Resolution
        key_columns_str = config.key_columns if isinstance(config.key_columns, str) else ",".join(config.key_columns or [])
        user_key_columns = [k.strip() for k in key_columns_str.split(",") if k.strip()]

        valid_keys = [k for k in user_key_columns if k in df_clean.columns]
        
        if valid_keys:
            # Use specified keys
            df_clean = df_clean.with_columns(
                base_key=pl.concat_str([pl.col(k) for k in valid_keys], separator="_")
            )
        else:
            # NO EXPLICIT KEY -> Use Excel Row Number (e.g., ROW_2, ROW_3)
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
    def read_file_to_polars_df(cls, file_path: str, config: ModuleConfig, is_source: bool = True) -> pl.DataFrame:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"❌ Data file not found at: {file_path}")

        file_ext = os.path.splitext(file_path)[1].lower()
        sheet_name = config.expected_sheet_name if is_source else config.actual_sheet_name

        if file_ext in [".csv", ".d"]:
            df = pl.read_csv(
                file_path, 
                infer_schema_length=0, 
                ignore_errors=True, 
                truncate_ragged_lines=True,
                quote_char=None,
                encoding="utf8-lossy"
            )
        elif file_ext in [".xlsx", ".xlsm", ".xls"]:
            df = pl.read_excel(file_path, sheet_name=sheet_name) if sheet_name else pl.read_excel(file_path)
            df = df.select([pl.all().cast(pl.Utf8)])
        else:
            raise ValueError(f"❌ Unsupported format '{file_ext}' for file: {file_path}")

        # Start index is 2 because Row 1 is usually the header
        return cls.normalize_dataframe_batch(df, config, start_row_index=2)