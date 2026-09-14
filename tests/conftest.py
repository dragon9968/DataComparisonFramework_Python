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

def pytest_sessionstart(session):
    """Clean temporary output directory and initialize environment before test execution."""
    # Only execute cleanup on master controller node when running under pytest-xdist
    if not hasattr(session.config, "workerinput"):
        print("\n🧹 Cleaning output directory and resetting test results...")
        ExtentManager.clear_results()
        FileUtils.create_directory_if_not_exists(str(GlobalConstants.OUTPUT_PATH))

def pytest_sessionfinish(session, exitstatus):
    """Safely aggregate test results and generate HTML report at master session finish."""
    # Ensure final aggregation runs strictly on the master node
    if not hasattr(session.config, "workerinput"):
        try:
            print("\n📊 Aggregating results and exporting Extent Report...")
            ExtentManager.generate_html_report()
        except Exception as e:
            print(f"⚠️ Failed to generate HTML report: {e}")