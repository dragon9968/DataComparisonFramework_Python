import os
import pytest
from commons.global_constants import GlobalConstants
from models.module_config import ModuleConfig
from utils.excel_reader import ExcelReader
from utils.data_comparator import DataComparator
from reports.extent_manager import ExtentManager

# Update directory paths to use raw_data and sharetec_data
SOURCE_DIR = os.path.join(GlobalConstants.PROJECT_PATH, "resources", "raw_data")
TARGET_DIR = os.path.join(GlobalConstants.PROJECT_PATH, "resources", "sharetec_data")

def get_all_bulk_files():
    """Recursively scan and collect all relative data file paths inside SOURCE_DIR."""
    if not os.path.exists(SOURCE_DIR):
        return []
    
    file_list = []
    for root, _, files in os.walk(SOURCE_DIR):
        for file in files:
            if file.lower().endswith((".csv", ".xlsx", ".xls")):
                rel_path = os.path.relpath(os.path.join(root, file), SOURCE_DIR)
                file_list.append(rel_path)
    return file_list

class TestBulkCompare:

    @pytest.mark.parametrize("rel_file_path", get_all_bulk_files())
    def test_compare_bulk_files(self, rel_file_path):
        source_path = os.path.join(SOURCE_DIR, rel_file_path)
        target_path = os.path.join(TARGET_DIR, rel_file_path)

        # Preserve original relative file path
        module_name = rel_file_path.replace("\\", "/")

        # Verify that corresponding target file exists
        if not os.path.exists(target_path):
            pytest.fail(f"❌ Target file not found at {target_path}")

        # 1. Instantiate dynamic 1:1 configuration in memory
        config = ModuleConfig(
            moduleName=module_name,
            keyColumns="", 
            compareColumns=[]
        )

        # 2. Read source and target files into record maps
        expected_map = ExcelReader.read_file_to_map(source_path, config, is_source=True)
        actual_map = ExcelReader.read_file_to_map(target_path, config, is_source=False)

        # 3. Perform data reconciliation
        result = DataComparator.compare_data_map(expected_map, actual_map, config)
        total_discrepancies = len(result["mismatches"])
        
        # 4. Log test execution details to ExtentManager
        ExtentManager.add_result(
            module_name=module_name,
            status=result["status"],
            total_exp=result["total_source_rows"],
            total_act=result["total_target_rows"],
            mismatches=result["mismatches"]
        )

        # 5. Report failure cleanly if mismatches exist
        if result["status"] == "FAILED":
            pytest.fail(f"Verification failed for [{module_name}] - {total_discrepancies} mismatches found!")