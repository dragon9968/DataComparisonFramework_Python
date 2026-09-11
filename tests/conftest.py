import os
import sys

# Dynamic sys.path fix to support frozen executable runs
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

import pytest
from commons.global_constants import GlobalConstants
from utils.file_utils import FileUtils
from reports.extent_manager import ExtentManager

@pytest.fixture(scope="session", autouse=True)
def setup_test_suite():
    """Initialize environment and clear output directory before execution."""
    print("\n🧹 Cleaning output directory and resetting test results...")
    ExtentManager.clear_results()
    FileUtils.create_directory_if_not_exists(str(GlobalConstants.OUTPUT_PATH))
    yield

def pytest_sessionfinish(session, exitstatus):
    """Pytest hook: Print consolidated summary table and export HTML report after complete test suite execution."""
    ExtentManager.print_summary_table()
    print("📊 Exporting Extent Report and CSV discrepancy files...")
    ExtentManager.generate_html_report()