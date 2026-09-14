import os
import pytest
from commons.global_constants import GlobalConstants
from models.module_config import ModuleConfig
from utils.excel_reader import ExcelReader
from utils.data_comparator import DataComparator
from reports.extent_manager import ExtentManager

SOURCE_DIR = os.path.join(GlobalConstants.PROJECT_PATH, "resources", "raw_data")
TARGET_DIR = os.path.join(GlobalConstants.PROJECT_PATH, "resources", "sharetec_data")

def get_all_bulk_files():
    if not os.path.exists(SOURCE_DIR):
        return []

    file_list = []
    for root, _, files in os.walk(SOURCE_DIR):
        for file in files:
            # Include .csv, .xlsx, .xls, .xlsm and .d data files
            if file.lower().endswith((".csv", ".xlsx", ".xls", ".xlsm", ".d")):
                rel_path = os.path.relpath(os.path.join(root, file), SOURCE_DIR)
                file_list.append(rel_path)
    return file_list

class TestBulkCompare:

    @pytest.mark.parametrize("rel_file_path", get_all_bulk_files())
    def test_compare_bulk_files(self, rel_file_path):
        source_path = os.path.join(SOURCE_DIR, rel_file_path)
        target_path = os.path.join(TARGET_DIR, rel_file_path)
        module_name = rel_file_path.replace("\\", "/")

        if not os.path.exists(target_path):
            ExtentManager.add_result(
                module_name=module_name,
                status="FAILED",
                total_exp=0,
                total_act=0,
                mismatches=[{
                    "no": 1,
                    "key": "SYSTEM",
                    "column": "FILE_EXISTENCE",
                    "expected": "FILE AVAILABLE",
                    "actual": f"NOT FOUND AT {target_path}",
                    "issue": "MISSING_TARGET_FILE"
                }]
            )
            pytest.fail(f"❌ Target file not found at {target_path}")

        config = ModuleConfig(
            moduleName=module_name,
            keyColumns="", 
            compareColumns=[]
        )

        df_source = ExcelReader.read_file_to_polars_df(source_path, config, is_source=True)
        df_target = ExcelReader.read_file_to_polars_df(target_path, config, is_source=False)

        result = DataComparator.compare_polars_dfs(df_source, df_target, config)
        total_discrepancies = len(result["mismatches"])

        ExtentManager.add_result(
            module_name=module_name,
            status=result["status"],
            total_exp=result["total_source_rows"],
            total_act=result["total_target_rows"],
            mismatches=result["mismatches"]
        )

        if result["status"] == "FAILED":
            pytest.fail(f"Verification failed for [{module_name}] - {total_discrepancies} mismatches found!")