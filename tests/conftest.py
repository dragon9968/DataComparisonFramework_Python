import pytest
from commons.global_constants import GlobalConstants
from utils.file_utils import FileUtils
from reports.extent_manager import ExtentManager

@pytest.fixture(scope="session", autouse=True)
def setup_test_suite():
    """Khởi tạo môi trường và dọn dẹp thư mục Report trước khi chạy Suite"""
    print("\n🧹 Đang khởi tạo môi trường và dọn dẹp thư mục Report...")
    FileUtils.create_directory_if_not_exists(str(GlobalConstants.REPORT_PATH))
    yield

def pytest_sessionfinish(session, exitstatus):
    """🔥 Pytest Hook: Tự động kích hoạt SAU KHI TẤT CẢ TEST CASES hoàn tất"""
    print("\n📊 Đang tổng hợp dữ liệu và xuất báo cáo Extent Report HTML...")
    ExtentManager.generate_html_report()