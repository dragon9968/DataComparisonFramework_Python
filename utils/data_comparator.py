import re
from datetime import datetime
from models.module_config import ModuleConfig

class DataComparator:

    @staticmethod
    def is_leading_zero_code(val_str: str) -> bool:
        """Check if value is a code with leading zeros (e.g. '0001', '0100')."""
        return bool(re.match(r"^0[0-9]{2,}.*", val_str)) and "." not in val_str

    @staticmethod
    def _clean_cell_value(val) -> str:
        """Format cell value cleanly to string without trailing float zeros or midnight time parts."""
        if val is None:
            return ""
        s = str(val).strip()
        if s.endswith(".0"):
            s = s[:-2]
        if s.endswith(" 00:00:00"):
            s = s[:-9]
        elif s.endswith("T00:00:00"):
            s = s[:-9]
        return s

    @classmethod
    def is_value_matching(cls, value_mappings: dict, full_col_name: str, exp_val: str, act_val: str) -> bool:
        """Perform smart matching for text, dates, numbers, and value mappings."""
        exp_clean = cls._clean_cell_value(exp_val)
        act_clean = cls._clean_cell_value(act_val)

        # 1. Exact case-insensitive match
        if exp_clean.lower() == act_clean.lower():
            return True

        # 2. Smart Date / DateTime comparison (expanded with 2-digit year formats like %y)
        date_formats = (
            "%Y-%m-%d", "%Y-%m-%d %H:%M:%S",
            "%m/%d/%Y", "%d/%m/%Y",
            "%m/%d/%y", "%d/%m/%y",
            "%Y/%m/%d", "%y/%m/%d",
            "%Y-%m-%dT%H:%M:%S"
        )
        
        exp_dt = None
        for fmt in date_formats:
            try:
                exp_dt = datetime.strptime(exp_clean, fmt)
                break
            except ValueError:
                pass

        if exp_dt:
            for fmt in date_formats:
                try:
                    act_dt = datetime.strptime(act_clean, fmt)
                    if exp_dt.date() == act_dt.date():
                        return True
                except ValueError:
                    pass

        # 3. Numeric comparison (if not leading-zero code)
        if not cls.is_leading_zero_code(exp_clean) and not cls.is_leading_zero_code(act_clean):
            try:
                d1 = float(exp_clean.replace(",", ""))
                d2 = float(act_clean.replace(",", ""))
                if abs(d1 - d2) < 1e-6:
                    return True
            except ValueError:
                pass

        # 4. Value Mappings (Bidirectional lookup)
        col_rules = value_mappings.get(full_col_name, {})
        if col_rules:
            for rule_k, rule_v in col_rules.items():
                k_str = str(rule_k).strip().lower()
                v_str = str(rule_v).strip().lower()
                if (exp_clean.lower() == k_str and act_clean.lower() == v_str) or \
                   (exp_clean.lower() == v_str and act_clean.lower() == k_str):
                    return True

        return False

    @classmethod
    def compare_data_map(cls, expected_map: dict, actual_map: dict, config: ModuleConfig) -> dict:
        """Reconcile expected_map against actual_map matching Java DataComparator logic."""
        results = {
            "status": "PASSED",
            "total_source_rows": len(expected_map),
            "total_target_rows": len(actual_map),
            "mismatches": []
        }

        if len(expected_map) != len(actual_map):
            results["status"] = "FAILED"

        # STEP A: Determine comparison columns
        compare_columns = config.compare_columns
        if not compare_columns and config.mappings:
            compare_columns = [m.source_column for m in config.mappings]
        if not compare_columns and expected_map:
            first_record = next(iter(expected_map.values()), {})
            compare_columns = list(first_record.keys())

        value_mappings = config.value_mappings or {}
        actual_key_case_map = {k.lower(): k for k in actual_map.keys()}

        count_no = 1
        valid_compare_columns = []

        # STEP A1: System-level missing column detection
        for col_name in compare_columns:
            has_source_data = any(
                rec.get(col_name) is not None and str(rec.get(col_name)).strip() != ""
                for rec in expected_map.values()
            )
            has_target_data = any(
                rec.get(col_name) is not None and str(rec.get(col_name)).strip() != ""
                for rec in actual_map.values()
            )

            is_missing_in_target = has_source_data and not has_target_data
            is_missing_in_source = not has_source_data and has_target_data

            if is_missing_in_target or is_missing_in_source:
                results["status"] = "FAILED"
                exp_msg = "Available in Source" if is_missing_in_target else "Missing in Source"
                act_msg = "Missing in Target" if is_missing_in_target else "Available in Target"
                results["mismatches"].append({
                    "no": count_no,
                    "key": "SYSTEM",
                    "column": col_name,
                    "expected": exp_msg,
                    "actual": act_msg,
                    "issue": "MISSING_COLUMN"
                })
                count_no += 1
            else:
                valid_compare_columns.append(col_name)

        # STEP B: Record-by-record reconciliation loop
        for key, exp_record in expected_map.items():
            matched_act_key = actual_key_case_map.get(key.lower())
            act_record = actual_map.get(matched_act_key) if matched_act_key else None

            if act_record is None:
                results["status"] = "FAILED"
                results["mismatches"].append({
                    "no": count_no,
                    "key": key,
                    "column": "ALL_FIELDS",
                    "expected": "DATA AVAILABLE",
                    "actual": "MISSING IN FILE EXTRACT",
                    "issue": "MISSING RECORD"
                })
                count_no += 1
            else:
                for col_name in valid_compare_columns:
                    exp_val = exp_record.get(col_name, "")
                    act_val = act_record.get(col_name, "")

                    if not cls.is_value_matching(value_mappings, col_name, exp_val, act_val):
                        results["status"] = "FAILED"
                        results["mismatches"].append({
                            "no": count_no,
                            "key": key,
                            "column": col_name,
                            "expected": exp_val,
                            "actual": act_val,
                            "issue": "VARIANCE"
                        })
                        count_no += 1

        return results