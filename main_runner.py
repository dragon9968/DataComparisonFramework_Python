import sys
import pytest

if __name__ == "__main__":
    print("🔥 Đang kích hoạt Data Comparison Framework Python...")

    args = [
        "-v",
        "-s",
        "--tb=no",               # Ẩn hoàn toàn đoạn code traceback khi Fail
        "--disable-warnings",    # Tắt các cảnh báo Warning màu vàng
        "tests/test_dynamic_data_compare.py"
    ]

    exit_code = pytest.main(args)
    sys.exit(exit_code)