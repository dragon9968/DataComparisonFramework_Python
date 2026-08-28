import os
import pytest
from commons.global_constants import GlobalConstants
from utils.config_reader import ConfigReader
from utils.excel_reader import ExcelReader
from utils.file_utils import FileUtils
from utils.data_comparator import DataComparator
from reports.extent_manager import ExtentManager

class TestDynamicDataCompare:

    @pytest.mark.parametrize("module_name", ConfigReader.get_all_module_names())
    def test_compare_module_data(self, module_name):
        # 1. Load module JSON configuration
        config = ConfigReader.load_module_config(module_name)

        # 2. Automatically resolve source and target file paths (.xlsx, .xlsm, .xls, .csv)
        folder_path = os.path.join(GlobalConstants.TEST_DATA_PATH, module_name)
        source_path = FileUtils.resolve_file_path(folder_path, config.source_file)
        target_path = FileUtils.resolve_file_path(folder_path, config.target_file)

        # 3. Read data into record maps matching Java ExcelReader logic
        expected_map = ExcelReader.read_file_to_map(source_path, config, is_source=True)
        actual_map = ExcelReader.read_file_to_map(target_path, config, is_source=False)

        # 4. Console log summary banner
        print("\n" + "=" * 80)
        print(f"[START] VERIFICATION: {module_name}")
        print(f"[INFO] Source file: {os.path.basename(source_path)}")
        print(f"[INFO] Target file: {os.path.basename(target_path)}")
        print(f"[INFO] Total row Expected: {len(expected_map)} | Total row Actual: {len(actual_map)}")
        print("=" * 80)

        # 5. Execute reconciliation
        result = DataComparator.compare_data_map(expected_map, actual_map, config)
        total_discrepancies = len(result["mismatches"])

        # 6. Record result in ExtentManager
        ExtentManager.add_result(
            module_name=module_name,
            status=result["status"],
            total_exp=result["total_source_rows"],
            total_act=result["total_target_rows"],
            mismatches=result["mismatches"]
        )

        # 7. Print result status
        if result["status"] == "FAILED":
            print(f"[FAIL] Result: A Total Of {total_discrepancies} Data Discrepancies were found")
            print(f"[INFO] Report: Full details exported to HTML and CSV.")
        else:
            print(f"[PASS] Result: All data matched perfectly (0 Discrepancies)!")

        # 8. Assert verification result
        assert result["status"] == "PASSED", (
            f"\nTest Table failed - {total_discrepancies} records failed!\n"
            f"Expected :0\n"
            f"Actual   :{total_discrepancies}"
        )