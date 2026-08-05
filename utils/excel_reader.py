import os
import polars as pl

class ExcelReader:
    @staticmethod
    def read_file_to_dataframe(file_path: str, sheet_name: str = None) -> pl.DataFrame:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"❌ Không tìm thấy file dữ liệu tại: {file_path}")
            
        if file_path.endswith(".csv"):
            return pl.read_csv(file_path)
        elif file_path.endswith((".xlsx", ".xls")):
            if sheet_name:
                try:
                    return pl.read_excel(file_path, sheet_name=sheet_name)
                except ValueError:
                    # Nếu tên sheet trong JSON không khớp với Excel -> tự động đọc sheet đầu tiên
                    print(f"⚠️ Cảnh báo: Không tìm thấy sheet '{sheet_name}' trong file {os.path.basename(file_path)}. Đang chuyển sang đọc Sheet đầu tiên...")
                    return pl.read_excel(file_path)
            else:
                return pl.read_excel(file_path)
        else:
            raise ValueError(f"❌ Định dạng file không hỗ trợ: {file_path}")