import os
from pathlib import Path

class GlobalConstants:
    # Lấy đường dẫn gốc của Project (Thư mục DataComparisonFramework_Python)
    PROJECT_PATH = Path(__file__).parent.parent.resolve()
    
    # Định nghĩa các đường dẫn tài nguyên
    CONFIG_PATH = os.path.join(PROJECT_PATH, "resources", "configs")
    TEST_DATA_PATH = os.path.join(PROJECT_PATH, "resources", "test-data")
    REPORT_PATH = os.path.join(PROJECT_PATH, "reports")

# Hằng số cấu hình file mặc định
    DEFAULT_SOURCE_FILE = "data_processed.xlsx"
    DEFAULT_TARGET_FILE = "data_extracted.xlsx"

    @classmethod
    def get_all_module_names(cls) -> list:
        """🔍 Tự động quét toàn bộ file .json trong resources/configs để lấy danh sách Module"""
        if not os.path.exists(cls.CONFIG_PATH):
            return []
            
        modules = [
            os.path.splitext(f)[0] 
            for f in os.listdir(cls.CONFIG_PATH) 
            if f.endswith(".json")
        ]
        return modules if modules else ["NO_MODULE_FOUND"]
    
# Chạy thử kiểm tra đường dẫn
if __name__ == "__main__":
    print(f"📌 Project Path: {GlobalConstants.PROJECT_PATH}")
    print(f"📌 Config Path:  {GlobalConstants.CONFIG_PATH}")