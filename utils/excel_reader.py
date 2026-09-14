import os
import re
import polars as pl
from models.module_config import ModuleConfig

class ExcelReader:

    @staticmethod
    def _get_fast_evaluated_cell_value(val) -> str:
        """Extract and clean cell value with leading zero decimal, date, and leading zero int formatting."""
        if val is None:
            return ""
        s = str(val).strip()
        if s.endswith(".0"):
            s = s[:-2]
        if s.endswith(" 00:00:00"):
            s = s[:-9]
        elif s.endswith("T00:00:00"):
            s = s[:-9]
        if s.startswith(".") and len(s) > 1 and s[1].isdigit():
            s = "0" + s

        # Normalize 2-digit year dates (e.g., 02/29/00 -> 2/29/2000, 06/30/05 -> 6/30/2005)
        m_date2 = re.match(r"^0*(\d{1,2})[/-]0*(\d{1,2})[/-](\d{2})$", s)
        if m_date2:
            y = int(m_date2.group(3))
            full_y = f"20{m_date2.group(3)}" if y < 50 else f"19{m_date2.group(3)}"
            return f"{int(m_date2.group(1))}/{int(m_date2.group(2))}/{full_y}"

        # Normalize 4-digit year dates (e.g., 04/21/2010 -> 4/21/2010)
        m_date4 = re.match(r"^0*(\d{1,2})[/-]0*(\d{1,2})[/-](\d{4})$", s)
        if m_date4:
            return f"{int(m_date4.group(1))}/{int(m_date4.group(2))}/{m_date4.group(3)}"

        # Normalize ISO dates (e.g., 2000-02-29 -> 2/29/2000)
        m_iso = re.match(r"^(\d{4})[/-]0*(\d{1,2})[/-]0*(\d{1,2})$", s)
        if m_iso:
            return f"{int(m_iso.group(2))}/{int(m_iso.group(3))}/{m_iso.group(1)}"

        # Normalize 2-digit leading zero integers (e.g., '01' -> '1', '09' -> '9', '00' -> '0')
        if re.match(r"^0[0-9]$", s):
            return str(int(s))

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

        if df.height == 0:
            return {}

        header_map = {col.strip().lower(): col for col in df.columns}
        actual_compare_cols = config.compare_columns if config.compare_columns else list(df.columns)

        key_columns_str = config.key_columns if isinstance(config.key_columns, str) else ",".join(config.key_columns or [])
        user_key_columns = [k.strip() for k in key_columns_str.split(",") if k.strip()]

        records = df.to_dicts()
        first_col_name = list(df.columns)[0]

        if not user_key_columns:
            effective_key_cols = cls._detect_dynamic_key_columns(list(df.columns))
        else:
            effective_key_cols = user_key_columns

        result_map = {}
        key_counter_map = {}

        for idx, row in enumerate(records, start=1):
            raw_first_val = str(row.get(first_col_name) or "").strip()

            if cls._is_footer_metadata_row(raw_first_val):
                break

            key_parts = []
            for c in effective_key_cols:
                col_actual_name = header_map.get(c.lower(), c)
                val = cls._get_fast_evaluated_cell_value(row.get(col_actual_name))
                if val != "":
                    key_parts.append(val)

            if not key_parts:
                base_key = f"ROW_{idx}"
            else:
                base_key = "_".join(key_parts)

            # Format key with 1-based sequence index in parentheses e.g. IC_DR(1), LA_OTH(2)
            lower_base_key = base_key.lower()
            occurrence = key_counter_map.get(lower_base_key, 0) + 1
            key_counter_map[lower_base_key] = occurrence
            final_key = f"{base_key}({occurrence})"

            fields_map = {}
            for col_name in actual_compare_cols:
                actual_col = header_map.get(col_name.lower())
                val = cls._get_fast_evaluated_cell_value(row.get(actual_col)) if actual_col else ""

                if col_name.lower() in ["dp.dp-desc", "dp-desc", "description"] and len(val) > 25:
                    val = val[:25].strip()

                fields_map[col_name] = val

            result_map[final_key] = fields_map

        return result_map