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
    """Pytest hook: Automatically export report after test completion."""
    print("\n📊 Exporting Extent Report and CSV discrepancy files...")
    ExtentManager.generate_html_report()