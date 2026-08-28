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
        if s.startswith("."):
            s = "0" + s
        return s

    @classmethod
    def read_file_to_map(cls, file_path: str, config: ModuleConfig, is_source: bool = True) -> dict:
        """
        Read data file into an ordered dictionary mapping final keys to record field maps,
        matching Java ExcelReader logic including cert-num key extension and 25-char description truncation.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"❌ Data file not found at: {file_path}")

        sheet_name = config.expected_sheet_name if is_source else config.actual_sheet_name
        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext == ".csv":
            df = pl.read_csv(file_path, infer_schema_length=0)
        elif file_ext in [".xlsx", ".xlsm", ".xls"]:
            if sheet_name:
                try:
                    df = pl.read_excel(file_path, sheet_name=sheet_name)
                except Exception:
                    df = pl.read_excel(file_path)
            else:
                df = pl.read_excel(file_path)
        else:
            raise ValueError(f"❌ Unsupported file format '{file_ext}' for file: {file_path}")

        header_map = {col.strip().lower(): col for col in df.columns}

        key_columns_str = config.key_columns if isinstance(config.key_columns, str) else ",".join(config.key_columns or [])
        key_columns = [k.strip() for k in key_columns_str.split(",") if k.strip()]
        compare_columns = config.compare_columns or [m.source_column for m in config.mappings]

        module_name = config.module_name or ""
        is_shares_module = module_name.upper() in ["SHARES", "DEPOSIT"]

        cert_num_col = None
        if is_shares_module:
            for candidate in ["dp.cert-num", "cert-num", "certnum"]:
                for h_lower, h_orig in header_map.items():
                    if h_lower == candidate or h_lower.endswith(candidate):
                        cert_num_col = h_orig
                        break
                if cert_num_col:
                    break

        result_map = {}
        key_counter_map = {}

        records = df.to_dicts()
        for row in records:
            # 1. Build Base Key
            key_parts = []
            for col_name in key_columns:
                actual_col = header_map.get(col_name.lower())
                val = row.get(actual_col) if actual_col else ""
                key_parts.append(cls._get_fast_evaluated_cell_value(val))

            base_key = "_".join(key_parts)
            if not base_key or base_key == "_":
                continue

            final_key = base_key

            # 2. Special cert-num & duplicate handling for SHARES/DEPOSIT
            if is_shares_module:
                if cert_num_col and cert_num_col in row:
                    cert_val = cls._get_fast_evaluated_cell_value(row.get(cert_num_col))
                    if cert_val and cert_val != "0":
                        base_key = f"{base_key}_{cert_val}"

                lower_base_key = base_key.lower()
                occurrence = key_counter_map.get(lower_base_key, 0)
                key_counter_map[lower_base_key] = occurrence + 1
                final_key = base_key if occurrence == 0 else f"{base_key}_dup{occurrence}"

            # 3. Build fields dictionary with 25-character description truncation
            fields_map = {}
            for col_name in compare_columns:
                actual_col = header_map.get(col_name.lower())
                val = cls._get_fast_evaluated_cell_value(row.get(actual_col)) if actual_col else ""

                # TRUNCATION LOGIC: Max 25 chars for description fields (Sharetec limit)
                if col_name.lower() in ["dp.dp-desc", "dp-desc", "description"]:
                    if len(val) > 25:
                        val = val[:25].strip()

                fields_map[col_name] = val

            result_map[final_key] = fields_map

        return result_map