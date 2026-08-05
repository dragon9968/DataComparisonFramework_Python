import polars as pl
from models.module_config import ModuleConfig

class DataComparator:

    @staticmethod
    def _clean_numeric_string(val_str: str) -> str:
        """Bỏ dấu phẩy phân cách hàng ngàn và chuẩn hóa số thập phân khuyết số 0"""
        v = val_str.replace(",", "").strip()
        if v.startswith("."):
            v = "0" + v
        elif v.startswith("-."):
            v = "-0" + v[1:]
        return v

    @classmethod
    def is_equal_values(cls, s_val: str, t_val: str) -> bool:
        """Hàm so sánh thông minh tương tự Java (hỗ trợ cả chữ lẫn số)"""
        # 1. Khớp hoàn toàn hoặc khớp chuỗi không phân biệt hoa thường
        if s_val.lower() == t_val.lower():
            return True

        # 2. Xử lý so sánh dạng Số (Bắt trọn 1,000.00 vs 1000 | 10.00 vs 10 | .00 vs 0)
        try:
            s_clean = cls._clean_numeric_string(s_val)
            t_clean = cls._clean_numeric_string(t_val)

            num_s = float(s_clean)
            num_t = float(t_clean)

            # So sánh giá trị số thực tế (cho phép sai số siêu nhỏ 1e-6)
            return abs(num_s - num_t) < 1e-6
        except ValueError:
            # Nếu không phải là số (chuỗi văn bản thường) -> Trả về False
            return False

    @classmethod
    def compare_data(cls, source_df: pl.DataFrame, target_df: pl.DataFrame, config: ModuleConfig) -> dict:
        results = {
            "status": "PASSED",
            "total_source_rows": len(source_df),
            "total_target_rows": len(target_df),
            "mismatches": []
        }

        if len(source_df) != len(target_df):
            results["status"] = "FAILED"

        key_col = None
        if config.key_columns:
            key_col = config.key_columns if isinstance(config.key_columns, str) else config.key_columns[0]

        pairs_to_compare = []
        if config.compare_columns:
            for col in config.compare_columns:
                pairs_to_compare.append((col, col))
        elif config.mappings:
            for m in config.mappings:
                pairs_to_compare.append((m.source_column, m.target_column))

        count_no = 1
        for src_col, tgt_col in pairs_to_compare:
            if src_col not in source_df.columns or tgt_col not in target_df.columns:
                results["status"] = "FAILED"
                results["mismatches"].append({
                    "no": count_no,
                    "key": "SYSTEM",
                    "column": src_col,
                    "expected": "Có trong Source" if src_col in source_df.columns else "Thiếu cột Source",
                    "actual": "Có trong Target" if tgt_col in target_df.columns else "Thiếu cột Target",
                    "issue": "MISSING_COLUMN"
                })
                count_no += 1
                continue

            col_value_map = config.value_mappings.get(src_col, {})

            src_vals = source_df[src_col].to_list()
            tgt_vals = target_df[tgt_col].to_list()
            limit = min(len(src_vals), len(tgt_vals))

            for idx in range(limit):
                s_val = "" if src_vals[idx] is None else str(src_vals[idx]).strip()
                t_val = "" if tgt_vals[idx] is None else str(tgt_vals[idx]).strip()

                # Ánh xạ theo valueMappings nếu có
                if col_value_map and s_val in col_value_map:
                    s_val = col_value_map[s_val]

                # 🚀 SO SÁNH THÔNG MINH (Bao trọn so sánh số & chuỗi)
                if not cls.is_equal_values(s_val, t_val):
                    results["status"] = "FAILED"
                    
                    key_val = f"Row {idx + 1}"
                    if key_col and key_col in source_df.columns:
                        key_val = str(source_df[key_col][idx])

                    results["mismatches"].append({
                        "no": count_no,
                        "key": key_val,
                        "column": src_col,
                        "expected": s_val,
                        "actual": t_val,
                        "issue": "VARIANCE"
                    })
                    count_no += 1

        return results