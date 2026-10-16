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
                }],
                total_mismatches=1,
                csv_filename=""
            )
            pytest.fail(f"❌ Target file not found at {target_path}")

        try:
            config = ModuleConfig(
                module_name=module_name,
                key_columns="", 
                compare_columns=[]
            )
        except TypeError:
            config = ModuleConfig(
                moduleName=module_name,
                keyColumns="", 
                compareColumns=[]
            )

        file_size_mb = os.path.getsize(source_path) / (1024 * 1024)

        if file_size_mb > 20 and source_path.lower().endswith((".csv", ".d")):
            result = DataComparator.compare_large_files_batched(source_path, target_path, config, batch_size=200000)
        else:
            exp_sheet = getattr(config, "expected_sheet_name", getattr(config, "expectedSheetName", None))
            act_sheet = getattr(config, "actual_sheet_name", getattr(config, "actualSheetName", None))
            df_src_raw = ExcelReader.read_raw_dataframe(source_path, sheet_name=exp_sheet)
            df_tgt_raw = ExcelReader.read_raw_dataframe(target_path, sheet_name=act_sheet)

            df_src_truncated = ExcelReader.truncate_metadata(df_src_raw)
            df_tgt_truncated = ExcelReader.truncate_metadata(df_tgt_raw)

            user_key = getattr(config, "key_columns", getattr(config, "keyColumns", ""))
            user_key_columns = [k.strip() for k in (user_key if isinstance(user_key, str) else ",".join(user_key or [])).split(",") if k.strip()]

            use_row_key = False
            detected_keys = []

            if user_key_columns:
                detected_keys = user_key_columns
            else:
                # If row counts are identical, keep physical row order (ROW_2, ROW_3...)
                if df_src_truncated.height == df_tgt_truncated.height:
                    use_row_key = True
                else:
                    # When row counts differ, auto discover business key to prevent cascading misalignment
                    detected_keys = ExcelReader.auto_detect_key_columns(df_src_truncated)

            df_source = ExcelReader.normalize_dataframe_batch(
                df_src_truncated, config, start_row_index=2, is_last_batch=False,
                use_row_key=use_row_key, custom_keys=detected_keys
            )
            df_target = ExcelReader.normalize_dataframe_batch(
                df_tgt_truncated, config, start_row_index=2, is_last_batch=False,
                use_row_key=use_row_key, custom_keys=detected_keys
            )
            result = DataComparator.compare_polars_dfs(df_source, df_target, config, is_row_aligned=use_row_key)

        total_discrepancies = result.get("total_mismatches", len(result["mismatches"]))

        ExtentManager.add_result(
            module_name=module_name,
            status=result["status"],
            total_exp=result["total_source_rows"],
            total_act=result["total_target_rows"],
            mismatches=result["mismatches"],
            total_mismatches=total_discrepancies,
            csv_filename=result.get("csv_filename", "")
        )

        if result["status"] == "FAILED":
            pytest.fail(f"Verification failed for [{module_name}] - {total_discrepancies} mismatches found!")