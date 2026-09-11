import os
import sys
import pytest
import webbrowser
import multiprocessing

# Add base directories to sys.path before importing internal packages
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
    meipass_dir = getattr(sys, '_MEIPASS', base_dir)
    if meipass_dir not in sys.path:
        sys.path.insert(0, meipass_dir)
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

# Import all modules explicitly so PyInstaller bundles them into the executable
import commons.global_constants
import models.module_config
import utils.file_utils
import utils.excel_reader
import utils.data_comparator
import reports.extent_manager

from commons.global_constants import GlobalConstants
from utils.file_utils import FileUtils

if __name__ == "__main__":
    multiprocessing.freeze_support()

    GlobalConstants.PROJECT_PATH = base_dir
    GlobalConstants.CONFIG_PATH = os.path.join(base_dir, "resources", "configs")
    GlobalConstants.TEST_DATA_PATH = os.path.join(base_dir, "resources", "test-data")
    GlobalConstants.OUTPUT_PATH = os.path.join(base_dir, "test-output")

    FileUtils.create_directory_if_not_exists(str(GlobalConstants.OUTPUT_PATH))

    print("======================================================================")
    print("                DATA COMPARISON FRAMEWORK TOOL")
    print("======================================================================")
    print(f"[INFO] Application Directory: {base_dir}\n")

    if getattr(sys, 'frozen', False):
        test_script = os.path.join(sys._MEIPASS, "tests", "test_bulk_compare.py")
    else:
        test_script = os.path.join(base_dir, "tests", "test_bulk_compare.py")

    if os.path.exists(test_script):
        pytest_args = ["-v", "-s", "--tb=no", "--disable-warnings", test_script]
        exit_code = pytest.main(pytest_args)
    else:
        print(f"❌ Error: Test script not found at {test_script}")

    report_file = os.path.join(GlobalConstants.OUTPUT_PATH, "ExtentDataReport.html")
    if os.path.exists(report_file):
        print(f"\n🌐 Automatically opening Extent Report in browser...")
        webbrowser.open(f"file:///{os.path.abspath(report_file)}")
    else:
        print(f"⚠️ Notice: Report file not generated at {report_file}")

    print("\n======================================================================")
    print("                     EXECUTION FINISHED!")
    print("======================================================================")
    input("\nPress Enter to exit...")