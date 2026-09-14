import os
import polars as pl
from models.module_config import ModuleConfig

class ExcelReader:

    @staticmethod
    def _detect_dynamic_key_columns(columns: list) -> list:
        """Automatically identify structural ID/Code columns from leading file columns."""
        key_keywords = ("type", "code", "id", "num", "number", "key")
        exclude_keywords = ("zz-", "date", "amt", "bal", "amount", "balance", "desc")

        detected = []
        leading_cols = columns[:min(4, len(columns))]

        for col in leading_cols:
            col_lower = col.strip().lower()
            if any(kw in col_lower for kw in exclude_keywords):
                continue
            if any(kw in col_lower for kw in key_keywords):
                detected.append(col)

        return detected if detected else [columns[0]]

    @classmethod
    def read_file_to_polars_df(cls, file_path: str, config: ModuleConfig, is_source: bool = True) -> pl.DataFrame:
        """High-performance file reader with Rust-compatible regex normalization for both Source and Target."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"❌ Data file not found at: {file_path}")

        file_ext = os.path.splitext(file_path)[1].lower()
        sheet_name = config.expected_sheet_name if is_source else config.actual_sheet_name

        # 1. Read File supporting CSV, Excel, and Progress .d format
        if file_ext in [".csv", ".d"]:
            df = pl.read_csv(file_path, infer_schema_length=0, ignore_errors=True)
        elif file_ext in [".xlsx", ".xlsm", ".xls"]:
            df = pl.read_excel(file_path, sheet_name=sheet_name) if sheet_name else pl.read_excel(file_path)
            df = df.select([pl.all().cast(pl.Utf8)])
        else:
            raise ValueError(f"❌ Unsupported format '{file_ext}' for file: {file_path}")

        if df.height == 0:
            return pl.DataFrame()

        # 2. Metadata Truncation (Tail 50 rows)
        first_col_raw = df.columns[0]
        tail_size = min(50, df.height)
        tail_df = df.tail(tail_size)
        tail_clean = tail_df[first_col_raw].fill_null("").cast(pl.Utf8).str.replace_all(r'[\r\n\t\xa0"]', "").str.strip_chars().str.to_lowercase()

        is_meta = (
            tail_clean.is_in([".", "psc", "0."]) |
            tail_clean.str.contains(r"^(filename=|records=|ldbname=|timestamp=|numforma|dateformat=|cpstream=)")
        )
        meta_indices = is_meta.arg_true()
        if len(meta_indices) > 0:
            cut_offset = (df.height - tail_size) + meta_indices[0]
            df = df.slice(0, cut_offset)

        if df.height == 0:
            return pl.DataFrame()

        header_map = {col.strip().lower(): col for col in df.columns}
        actual_compare_cols = config.compare_columns if config.compare_columns else list(df.columns)

        # 3. Vectorized Normalization
        exprs = []
        for col_name in actual_compare_cols:
            actual_col = header_map.get(col_name.lower())
            if actual_col:
                expr = (
                    pl.col(actual_col)
                    .fill_null("")
                    .cast(pl.Utf8)
                    .str.replace_all(r'[\r\n\t\xa0"]', "")  # Strip quotes & control characters
                    .str.strip_chars()                       # Strip leading/trailing spaces
                    .str.replace(r"\.0$", "")                # Standardize float strings "1.0" -> "1"
                    .str.replace(r" 00:00:00$", "")          # Strip time component
                    .str.replace(r"T00:00:00$", "")
                    .str.replace(r"^\.(\d+)", r"0.$1")
                )

                # Strip leading zeros cleanly for integers ("01"->"1", "00"->"0")
                expr = expr.str.replace(r"^0+?([1-9]\d*|0)$", r"$1")

                # Standardize Date Formats to M/D/YYYY:
                expr = expr.str.replace(r"^(\d{4})[/-]0*([1-9]\d?)[/-]0*([1-9]\d?)$", r"$2/$3/$1")
                expr = expr.str.replace(r"^0*([1-9]\d?)[/-]0*([1-9]\d?)[/-](\d{2})$", r"$1/$2/20$3")
                expr = expr.str.replace(r"^0*([1-9]\d?)[/-]0*([1-9]\d?)[/-](\d{4})$", r"$1/$2/$3")

                exprs.append(expr.alias(col_name))
            else:
                exprs.append(pl.lit("").alias(col_name))

        df_clean = df.select(exprs)

        # 4. Composite Key Resolution (Conditional Indexing: Append (1) only if duplicate)
        key_columns_str = config.key_columns if isinstance(config.key_columns, str) else ",".join(config.key_columns or [])
        user_key_columns = [k.strip() for k in key_columns_str.split(",") if k.strip()]

        if not user_key_columns:
            effective_key_cols = cls._detect_dynamic_key_columns(list(df.columns))
        else:
            effective_key_cols = user_key_columns

        valid_keys = [k for k in effective_key_cols if k in df_clean.columns]
        if valid_keys:
            df_clean = df_clean.with_columns(
                base_key=pl.concat_str([pl.col(k) for k in valid_keys], separator="_")
            )
        else:
            df_clean = df_clean.with_columns(
                base_key=pl.concat_str([pl.lit("ROW_"), pl.int_range(1, pl.len() + 1).cast(pl.Utf8)])
            )

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