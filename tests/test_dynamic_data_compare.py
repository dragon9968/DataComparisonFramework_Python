import os
import pytest
from commons.global_constants import GlobalConstants
from utils.config_reader import ConfigReader
from utils.excel_reader import ExcelReader
from utils.data_comparator import DataComparator
from reports.extent_manager import ExtentManager

class TestDynamicDataCompare:

    @pytest.mark.parametrize("module_name", ConfigReader.get_all_module_names())
    def test_compare_module_data(self, module_name):
        # 1. Đọc cấu hình JSON
        config = ConfigReader.load_module_config(module_name)

        # 2. Xác định đường dẫn file Source & Target
        source_path = os.path.join(GlobalConstants.TEST_DATA_PATH, module_name, config.source_file)
        target_path = os.path.join(GlobalConstants.TEST_DATA_PATH, module_name, config.target_file)

        # 3. Đọc dữ liệu ra DataFrame
        source_df = ExcelReader.read_file_to_dataframe(source_path, config.expected_sheet_name)
        target_df = ExcelReader.read_file_to_dataframe(target_path, config.actual_sheet_name)

        # 4. In Console Log banner khởi tạo giống hệt Java
        print("\n" + "=" * 80)
        print(f"[START] VERIFICATION: {module_name}")
        print(f"[INFO] Total row Expected: {len(source_df)} | Total row Actual: {len(target_df)}")
        print("=" * 80)

        # 5. Thực hiện so sánh dữ liệu
        result = DataComparator.compare_data(source_df, target_df, config)
        total_discrepancies = len(result["mismatches"])

        # 6. Ghi nhận kết quả vào ExtentManager
        ExtentManager.add_result(
            module_name=module_name,
            status=result["status"],
            total_exp=result["total_source_rows"],
            total_act=result["total_target_rows"],
            mismatches=result["mismatches"]
        )

        # 7. In thông báo kết quả chi tiết theo định dạng Java
        if result["status"] == "FAILED":
            print(f"[FAIL] Result: A Total Of {total_discrepancies} Data Discrepancies were found")
            print(f"[INFO] Report: Full details exported to HTML: ExtentDataReport.html")
        else:
            print(f"[PASS] Result: All data matched perfectly (0 Discrepancies)!")

        # 8. Assert với thông báo lỗi Expected :0 / Actual :X chuẩn Java
        assert result["status"] == "PASSED", (
            f"\nTest Table failed - {total_discrepancies} records failed!\n"
            f"Expected :0\n"
            f"Actual   :{total_discrepancies}"
        )