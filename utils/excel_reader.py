import os
import polars as pl
from models.module_config import ModuleConfig

class ExcelReader:

    @staticmethod
    def _get_fast_evaluated_cell_value(val) -> str:
        """Extract and clean cell value with leading zero decimal formatting matching Java."""
        if val is None:
            return ""
        s = str(val).strip()
        if s.endswith(".0"):
            s = s[:-2]
        # Only prepend '0' if followed by digits (e.g. '.5' -> '0.5'), not for standalone '.'
        if s.startswith(".") and len(s) > 1 and s[1].isdigit():
            s = "0" + s
        return s

    @staticmethod
    def _is_footer_metadata_row(val_str: str) -> bool:
        """Check if cell value indicates the start of Progress/Sharetec metadata footer."""
        if not val_str:
            return False
        s = val_str.strip().lower()
        if s in [".", "psc", "0."]:
            return True
        metadata_prefixes = ("filename=", "records=", "ldbname=", "timestamp=", "numforma", "dateformat=", "cpstream=")
        return any(s.startswith(p) for p in metadata_prefixes)

    @classmethod
    def read_file_to_map(cls, file_path: str, config: ModuleConfig, is_source: bool = True) -> dict:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"❌ Data file not found at: {file_path}")

        file_ext = os.path.splitext(file_path)[1].lower()
        sheet_name = config.expected_sheet_name if is_source else config.actual_sheet_name

        if file_ext == ".csv":
            df = pl.read_csv(file_path, infer_schema_length=0)
        elif file_ext in [".xlsx", ".xlsm", ".xls"]:
            df = pl.read_excel(file_path, sheet_name=sheet_name) if sheet_name else pl.read_excel(file_path)
        else:
            raise ValueError(f"❌ Unsupported format '{file_ext}' for file: {file_path}")

        header_map = {col.strip().lower(): col for col in df.columns}
        actual_compare_cols = config.compare_columns if config.compare_columns else list(df.columns)

        key_columns_str = config.key_columns if isinstance(config.key_columns, str) else ",".join(config.key_columns or [])
        key_columns = [k.strip() for k in key_columns_str.split(",") if k.strip()]

        result_map = {}
        key_counter_map = {}
        records = df.to_dicts()

        for idx, row in enumerate(records, start=1):
            first_col_name = list(df.columns)[0]
            raw_first_val = str(row.get(first_col_name) or "").strip()

            # Stop reading immediately when hitting metadata footer section (. / PSC / filename= / etc.)
            if cls._is_footer_metadata_row(raw_first_val):
                break

            first_col_val = cls._get_fast_evaluated_cell_value(row.get(first_col_name))

            # 1. Base Key resolution logic
            if not key_columns:
                base_key = first_col_val if first_col_val else f"ROW_{idx}"
            else:
                key_parts = [cls._get_fast_evaluated_cell_value(row.get(header_map.get(c.lower()))) for c in key_columns]
                base_key = "_".join(key_parts)
                if not base_key or base_key == "_":
                    continue

            # 2. Append occurrence suffix for duplicate keys to prevent record overwriting
            lower_base_key = base_key.lower()
            occurrence = key_counter_map.get(lower_base_key, 0)
            key_counter_map[lower_base_key] = occurrence + 1
            final_key = base_key if occurrence == 0 else f"{base_key}_dup{occurrence}"

            # 3. Build record fields dictionary
            fields_map = {}
            for col_name in actual_compare_cols:
                actual_col = header_map.get(col_name.lower())
                val = cls._get_fast_evaluated_cell_value(row.get(actual_col)) if actual_col else ""
                
                if col_name.lower() in ["dp.dp-desc", "dp-desc", "description"] and len(val) > 25:
                    val = val[:25].strip()
                    
                fields_map[col_name] = val

            result_map[final_key] = fields_map

        return result_map