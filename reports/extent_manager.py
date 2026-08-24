import os
from datetime import datetime
from commons.global_constants import GlobalConstants
from utils.file_utils import FileUtils

class ExtentManager:
    _test_results = []

    @classmethod
    def add_result(cls, module_name: str, status: str, total_exp: int, total_act: int, mismatches: list):
        cls._test_results.append({
            "module_name": module_name,
            "status": status,
            "total_exp": total_exp,
            "total_act": total_act,
            "mismatches": mismatches,
            "timestamp": datetime.now().strftime("%I:%M:%S %p")
        })

    @classmethod
    def generate_html_report(cls):
        FileUtils.create_directory_if_not_exists(str(GlobalConstants.REPORT_PATH))
        report_file = os.path.join(GlobalConstants.REPORT_PATH, "ExtentDataReport.html")

        now_str = datetime.now().strftime("%b %d, %Y %I:%M:%S %p")

        # Sidebar Menu
        sidebar_items = ""
        content_items = ""

        for idx, res in enumerate(cls._test_results, 1):
            status_color = "#f44336" if res["status"] == "FAILED" else "#4caf50"
            status_label = "Fail" if res["status"] == "FAILED" else "Pass"
            
            sidebar_items += f"""
            <div class="test-item" onclick="showTest('{res['module_name']}')">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <strong>TABLE: {res['module_name']}</strong>
                    <span class="badge" style="background-color:{status_color};">{status_label}</span>
                </div>
                <div style="font-size:11px; color:#888; margin-top:4px;">{res['timestamp']}</div>
            </div>
            """

            # Bảng chứa dòng dữ liệu lệch
            rows_html = ""
            for item in res["mismatches"]:
                rows_html += f"""
                <tr style="background-color: #fff0f0;">
                    <td style="text-align:center; font-weight:bold;">{item['no']}</td>
                    <td style="font-weight:bold;">{item['key']}</td>
                    <td style="color:#2b5797; font-weight:bold;">{item['column']}</td>
                    <td style="color:#d9534f; word-break:break-all;">{item['expected']}</td>
                    <td style="color:#d9534f; word-break:break-all;">{item['actual']}</td>
                    <td style="text-align:center;"><span class="badge-variance">❌ {item['issue']}</span></td>
                </tr>
                """

            content_items += f"""
            <div id="module-{res['module_name']}" class="test-content">
                <h3 style="color:#d9534f; margin-bottom:5px;">TABLE: {res['module_name']}</h3>
                <div style="margin-bottom:15px;">
                    <span class="tag tag-time">{now_str}</span>
                    <span class="tag tag-fail">#test-id={idx}</span>
                </div>
                <p style="font-weight:bold; color:#555;">AUTO VERIFICATION FOR {res['module_name']}</p>
                <p style="font-size:14px; margin-bottom:15px;">
                    <strong>Count:</strong> Total Row Expected = {res['total_exp']} | Total Row Actual = {res['total_act']}
                </p>
                <p style="font-weight:bold; color:#333;">
                    Detail {len(res['mismatches'])} Data Discrepancies:
                </p>

                <table class="data-table">
                    <thead>
                        <tr>
                            <th style="width:50px;">NO.</th>
                            <th style="width:150px;">KEY (MEMBER+TYPE)</th>
                            <th style="width:200px;">COLUMN NAME</th>
                            <th>EXPECTED (DATA)</th>
                            <th>ACTUAL (SHARETEC)</th>
                            <th style="width:110px;">ISSUES</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html if rows_html else '<tr><td colspan="6" style="text-align:center; color:green; font-weight:bold;">✅ Mọi dữ liệu khớp 100%!</td></tr>'}
                    </tbody>
                </table>
            </div>
            """

        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Data Reconciliation Verification Report</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin:0; padding:0; background:#f5f6f8; }}
                .topbar {{ background:#19202a; color:#fff; padding:12px 20px; display:flex; justify-content:space-between; align-items:center; }}
                .topbar h2 {{ margin:0; font-size:16px; font-weight:400; }}
                .container {{ display:flex; height:calc(100vh - 45px); }}
                .sidebar {{ width:260px; background:#fff; border-right:1px solid #e0e0e0; overflow-y:auto; }}
                .test-item {{ padding:15px; border-bottom:1px solid #eee; cursor:pointer; }}
                .test-item:hover {{ background:#f0f4f9; }}
                .main-content {{ flex:1; padding:25px; overflow-y:auto; }}
                .badge {{ color:#fff; padding:3px 8px; border-radius:12px; font-size:10px; font-weight:bold; }}
                .badge-variance {{ color:#d9534f; font-weight:bold; font-size:12px; }}
                .tag {{ display:inline-block; padding:4px 8px; border-radius:3px; font-size:11px; color:#fff; margin-right:5px; }}
                .tag-time {{ background:#17a2b8; }}
                .tag-fail {{ background:#d9534f; }}
                .data-table {{ width:100%; border-collapse:collapse; background:#fff; margin-top:10px; box-shadow:0 1px 3px rgba(0,0,0,0.1); }}
                .data-table th {{ background:#4a4a5a; color:#fff; padding:10px; font-size:12px; text-align:left; }}
                .data-table td {{ padding:8px 10px; border-bottom:1px solid #eef; font-size:12px; }}
            </style>
        </head>
        <body>
            <div class="topbar">
                <h2>Data Reconciliation Verification Report</h2>
                <span style="font-size:12px; background:#5c6bc0; padding:4px 10px; border-radius:3px;">{now_str}</span>
            </div>
            <div class="container">
                <div class="sidebar">{sidebar_items}</div>
                <div class="main-content">{content_items}</div>
            </div>
            <script>
                function showTest(moduleName) {{
                    var contents = document.getElementsByClassName('test-content');
                    for (var i = 0; i < contents.length; i++) {{
                        contents[i].style.display = 'none';
                    }}
                    document.getElementById('module-' + moduleName).style.display = 'block';
                }}
                if(document.getElementsByClassName('test-content').length > 0) {{
                    document.getElementsByClassName('test-content')[0].style.display = 'block';
                }}
            </script>
        </body>
        </html>
        """

        with open(report_file, "w", encoding="utf-8") as f:
            f.write(full_html)
        print(f"\n📊 Extent Report đã được tạo tại: {report_file}")