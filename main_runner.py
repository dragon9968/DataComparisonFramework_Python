import sys
import os
import argparse
import pytest
import webbrowser
from commons.global_constants import GlobalConstants

if __name__ == "__main__":
    print("🔥 Starting Data Comparison Framework Python...")

    # 1. Parse CLI Arguments
    parser = argparse.ArgumentParser(description="Data Comparison Framework Runner")
    parser.add_argument(
        "-m", "--module", 
        type=str, 
        help="Run comparison for a specific module (e.g., -m SHARE_MATRIX)"
    )
    parser.add_argument(
        "-n", "--workers", 
        type=str, 
        help="Number of parallel execution workers (e.g., -n 4)"
    )
    parser.add_argument(
        "--open-report", 
        action="store_true", 
        help="Automatically open HTML report after run completion"
    )

    args_parsed, extra_pytest_args = parser.parse_known_args()

    # 2. Build Pytest arguments
    pytest_args = [
        "-v",
        "-s",
        "--tb=short",
        "--disable-warnings",
        "tests/test_dynamic_data_compare.py"
    ]

    if args_parsed.module:
        pytest_args.extend(["-k", args_parsed.module])

    if args_parsed.workers:
        pytest_args.extend(["-n", args_parsed.workers])

    pytest_args.extend(extra_pytest_args)

    # 3. Execute Pytest
    exit_code = pytest.main(pytest_args)

    # 4. Automatically open HTML report if requested
    if args_parsed.open_report:
        report_path = os.path.abspath(os.path.join(GlobalConstants.OUTPUT_PATH, "ExtentDataReport.html"))
        if os.path.exists(report_path):
            print(f"🌐 Opening report in browser: {report_path}")
            webbrowser.open(f"file://{report_path}")

    sys.exit(exit_code)