import os
import csv
import html
import re
from datetime import datetime
from commons.global_constants import GlobalConstants
from utils.file_utils import FileUtils

class ExtentManager:
    _test_results = []

    @classmethod
    def clear_results(cls):
        """Clear previous test results before running a new test suite."""
        cls._test_results = []

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
    def print_summary_table(cls):
        """Print one consolidated summary table for all tested files at session finish."""
        if not cls._test_results:
            return

        print("\n" + "┌" + "─" * 44 + "┬" + "─" * 10 + "┬" + "─" * 10 + "┬" + "─" * 14 + "┬" + "─" * 10 + "┐")
        print(f"│ {'FILE PATH':<42} │ {'SOURCE':<8} │ {'TARGET':<8} │ {'MISMATCHES':<12} │ {'STATUS':<8} │")
        print("├" + "─" * 44 + "┼" + "─" * 10 + "┼" + "─" * 10 + "┼" + "─" * 14 + "┼" + "─" * 10 + "┤")

        for res in cls._test_results:
            module_name = res["module_name"]
            status_badge = "❌ FAIL" if res["status"] == "FAILED" else "✅ PASS"
            total_exp = res["total_exp"]
            total_act = res["total_act"]
            mismatches_count = len(res["mismatches"])
            
            disp_name = module_name if len(module_name) <= 42 else "..." + module_name[-39:]
            print(f"│ {disp_name:<42} │ {total_exp:<8} │ {total_act:<8} │ {mismatches_count:<12} │ {status_badge:<8} │")

        print("└" + "─" * 44 + "┴" + "─" * 10 + "┴" + "─" * 10 + "┴" + "─" * 14 + "┴" + "─" * 10 + "┘\n")

    @classmethod
    def _export_csv_discrepancies(cls, module_name: str, mismatches: list) -> str:
        """Export all discrepancies into a CSV file inside the output directory."""
        safe_module_name = re.sub(r'[\\/:*?"<>|]', '_', module_name)
        csv_filename = f"{safe_module_name}_Discrepancies.csv"
        csv_path = os.path.join(GlobalConstants.OUTPUT_PATH, csv_filename)
        
        headers = ["NO.", "KEY (MEMBER+TYPE)", "COLUMN NAME", "EXPECTED (DATA)", "ACTUAL (SHARETEC)", "ISSUES"]
        
        with open(csv_path, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for item in mismatches:
                writer.writerow([
                    item.get("no", ""),
                    item.get("key", ""),
                    item.get("column", ""),
                    item.get("expected", ""),
                    item.get("actual", ""),
                    item.get("issue", "")
                ])
        return csv_filename

    @classmethod
    def generate_html_report(cls):
        FileUtils.create_directory_if_not_exists(str(GlobalConstants.OUTPUT_PATH))
        report_file = os.path.join(GlobalConstants.OUTPUT_PATH, "ExtentDataReport.html")
        now_str = datetime.now().strftime("%b %d, %Y %I:%M:%S %p")

        # Organize results by folder structure
        grouped_results = {}
        total_pass = 0
        total_fail = 0

        for res in cls._test_results:
            mod_name = res["module_name"]
            if res["status"] == "FAILED":
                total_fail += 1
            else:
                total_pass += 1

            parts = mod_name.replace("\\", "/").split("/")
            if len(parts) > 1:
                folder = "/".join(parts[:-1])
                file_name = parts[-1]
            else:
                folder = "Root"
                file_name = mod_name

            if folder not in grouped_results:
                grouped_results[folder] = []
            grouped_results[folder].append({
                "file_name": file_name,
                "full_res": res
            })

        # 1. Build Sidebar Tree Menu
        sidebar_items = f"""
        <div class="menu-item active" onclick="showTest('dashboard-summary', this)">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <strong>📊 SUMMARY DASHBOARD</strong>
                <span class="badge" style="background-color:#17a2b8;">{len(cls._test_results)} Files</span>
            </div>
        </div>
        <div style="border-bottom:1px solid #e0e0e0; margin:5px 0;"></div>
        """

        for folder_idx, (folder, items) in enumerate(grouped_results.items(), 1):
            folder_fail_cnt = sum(1 for i in items if i["full_res"]["status"] == "FAILED")
            folder_badge_color = "#f44336" if folder_fail_cnt > 0 else "#4caf50"
            folder_badge_label = f"{folder_fail_cnt} Fail" if folder_fail_cnt > 0 else "All Pass"

            folder_dom_id = f"folder-group-{folder_idx}"
            arrow_id = f"arrow-{folder_idx}"

            sidebar_items += f"""
            <div class="folder-header" onclick="toggleFolder('{folder_dom_id}', '{arrow_id}')">
                <div>
                    <span id="{arrow_id}" class="arrow">▼</span>
                    <strong>📁 {html.escape(folder)}</strong>
                </div>
                <span class="badge" style="background-color:{folder_badge_color};">{folder_badge_label}</span>
            </div>
            <div id="{folder_dom_id}" class="folder-content">
            """

            for item in items:
                res = item["full_res"]
                m_name = res["module_name"]
                safe_id = "mod-" + re.sub(r'[^a-zA-Z0-9_-]', '_', m_name)
                
                status_color = "#f44336" if res["status"] == "FAILED" else "#4caf50"
                status_label = "Fail" if res["status"] == "FAILED" else "Pass"

                sidebar_items += f"""
                <div class="menu-item sub-item" onclick="showTest('{safe_id}', this)">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:12px;">📄 {html.escape(item['file_name'])}</span>
                        <span class="badge" style="background-color:{status_color};">{status_label}</span>
                    </div>
                </div>
                """
            sidebar_items += "</div>"

        # 2. Build Summary Dashboard Rows
        summary_table_rows = ""
        for res in cls._test_results:
            m_name = res["module_name"]
            mismatches_count = len(res["mismatches"])
            status_color = "#f44336" if res["status"] == "FAILED" else "#4caf50"
            status_label = "FAIL" if res["status"] == "FAILED" else "PASS"
            
            summary_table_rows += f"""
            <tr>
                <td style="font-weight:bold; color:#2b5797;">{html.escape(m_name)}</td>
                <td style="text-align:center;">{res['total_exp']}</td>
                <td style="text-align:center;">{res['total_act']}</td>
                <td style="text-align:center; font-weight:bold; color:{'#d9534f' if mismatches_count > 0 else '#28a745'};">{mismatches_count}</td>
                <td style="text-align:center;"><span class="badge" style="background-color:{status_color};">{status_label}</span></td>
            </tr>
            """

        dashboard_html = f"""
        <div id="module-dashboard-summary" class="test-content" style="display:block;">
            <h3 style="color:#2c3e50; margin-bottom:15px;">📊 Executive Summary Dashboard</h3>
            
            <div style="display:flex; gap:15px; margin-bottom:20px;">
                <div class="card-stat" style="border-left: 4px solid #17a2b8;">
                    <div class="stat-title">TOTAL FILES</div>
                    <div class="stat-value">{len(cls._test_results)}</div>
                </div>
                <div class="card-stat" style="border-left: 4px solid #28a745;">
                    <div class="stat-title">PASSED</div>
                    <div class="stat-value" style="color:#28a745;">{total_pass}</div>
                </div>
                <div class="card-stat" style="border-left: 4px solid #dc3545;">
                    <div class="stat-title">FAILED</div>
                    <div class="stat-value" style="color:#dc3545;">{total_fail}</div>
                </div>
            </div>

            <p style="font-weight:bold; color:#333; margin-bottom:10px;">Overall File Verification Status:</p>
            <table class="data-table">
                <thead>
                    <tr>
                        <th rowspan="2" style="vertical-align:middle;">FILE PATH</th>
                        <th colspan="2" style="text-align:center; border-bottom:1px solid #5a5a6a;">Count</th>
                        <th rowspan="2" style="width:120px; text-align:center; vertical-align:middle;">MISMATCHES</th>
                        <th rowspan="2" style="width:100px; text-align:center; vertical-align:middle;">STATUS</th>
                    </tr>
                    <tr>
                        <th style="width:110px; text-align:center;">SOURCE<br><span style="font-size:11px; font-weight:normal;">(Data)</span></th>
                        <th style="width:110px; text-align:center;">TARGET<br><span style="font-size:11px; font-weight:normal;">(Sharetec)</span></th>
                    </tr>
                </thead>
                <tbody>
                    {summary_table_rows}
                </tbody>
            </table>
        </div>
        """

        # 3. Build Individual File Detail Contents
        content_items = dashboard_html

        for idx, res in enumerate(cls._test_results, 1):
            module_name = res["module_name"]
            safe_id = "mod-" + re.sub(r'[^a-zA-Z0-9_-]', '_', module_name)
            
            total_mismatches = len(res["mismatches"])
            csv_filename = ""
            
            if total_mismatches > 0:
                csv_filename = cls._export_csv_discrepancies(module_name, res["mismatches"])

            display_mismatches = res["mismatches"][:200]

            rows_html = ""
            for item in display_mismatches:
                rows_html += f"""
                <tr style="background-color: #fff0f0;">
                    <td style="text-align:center; font-weight:bold;">{item['no']}</td>
                    <td style="font-weight:bold;">{html.escape(str(item['key']))}</td>
                    <td style="color:#2b5797; font-weight:bold;">{html.escape(str(item['column']))}</td>
                    <td style="color:#d9534f; word-break:break-all;">{html.escape(str(item['expected']))}</td>
                    <td style="color:#d9534f; word-break:break-all;">{html.escape(str(item['actual']))}</td>
                    <td style="text-align:left; padding-left:12px; white-space:nowrap;"><span class="badge-variance">❌ {html.escape(str(item['issue']))}</span></td>
                </tr>
                """

            notice_html = ""
            if total_mismatches > 200:
                notice_html = f"""
                <div style="background-color:#fff3cd; color:#856404; padding:10px 15px; border-radius:4px; margin-bottom:15px; border:1px solid #ffeeba;">
                    ⚠️ <strong>Notice:</strong> Showing first 200 of {total_mismatches} discrepancies in HTML. Full report exported to <strong>{csv_filename}</strong>
                </div>
                """
            elif total_mismatches > 0:
                notice_html = f"""
                <div style="background-color:#e2e3e5; color:#383d41; padding:8px 12px; border-radius:4px; margin-bottom:15px;">
                    📄 Detailed report exported to <strong>{csv_filename}</strong>
                </div>
                """

            content_items += f"""
            <div id="module-{safe_id}" class="test-content" style="display:none;">
                <h3 style="color:#d9534f; margin-bottom:5px;">FILE: {html.escape(module_name)}</h3>
                <div style="margin-bottom:15px;">
                    <span class="tag tag-time">{now_str}</span>
                    <span class="tag tag-fail">#test-id={idx}</span>
                </div>
                <p style="font-weight:bold; color:#555;">AUTO VERIFICATION FOR {html.escape(module_name)}</p>
                <p style="font-size:14px; margin-bottom:15px;">
                    <strong>Count:</strong> Total Row Expected = {res['total_exp']} | Total Row Actual = {res['total_act']}
                </p>
                <p style="font-weight:bold; color:#333;">
                    Detail {total_mismatches} Data Discrepancies:
                </p>
                {notice_html}

                <table class="data-table">
                    <thead>
                        <tr>
                            <th style="width:50px; text-align:center;">NO.</th>
                            <th style="width:150px;">KEY (MEMBER+TYPE)</th>
                            <th style="width:200px;">COLUMN NAME</th>
                            <th>EXPECTED (DATA)</th>
                            <th>ACTUAL (SHARETEC)</th>
                            <th style="width:140px; text-align:left; padding-left:12px;">ISSUES</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html if rows_html else '<tr><td colspan="6" style="text-align:center; color:green; font-weight:bold;">✅ All data matched 100%!</td></tr>'}
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
                .sidebar {{ width:280px; background:#fff; border-right:1px solid #e0e0e0; overflow-y:auto; padding-bottom:20px; }}
                
                .folder-header {{ padding:10px 15px; background:#f8f9fa; border-bottom:1px solid #eee; cursor:pointer; display:flex; justify-content:space-between; align-items:center; user-select:none; font-size:13px; }}
                .folder-header:hover {{ background:#eef2f7; }}
                .folder-content {{ display:block; background:#fafafa; border-bottom:1px solid #eee; }}
                
                .menu-item {{ padding:10px 15px; border-bottom:1px solid #f0f0f0; cursor:pointer; font-size:13px; }}
                .menu-item:hover {{ background:#e8f0fe; }}
                .menu-item.active {{ background:#e2edfc; border-left:4px solid #1a73e8; font-weight:bold; }}
                .sub-item {{ padding-left:25px; border-bottom:1px solid #f5f5f5; }}

                .arrow {{ display:inline-block; transition:transform 0.2s; font-size:10px; margin-right:5px; color:#666; }}
                .arrow.collapsed {{ transform:rotate(-90deg); }}

                .main-content {{ flex:1; padding:25px; overflow-y:auto; }}
                .badge {{ color:#fff; padding:3px 8px; border-radius:12px; font-size:10px; font-weight:bold; }}
                .badge-variance {{ color:#d9534f; font-weight:bold; font-size:12px; display:inline-block; white-space:nowrap; }}
                .tag {{ display:inline-block; padding:4px 8px; border-radius:3px; font-size:11px; color:#fff; margin-right:5px; }}
                .tag-time {{ background:#17a2b8; }}
                .tag-fail {{ background:#d9534f; }}
                
                .card-stat {{ background:#fff; padding:15px 20px; border-radius:5px; flex:1; box-shadow:0 1px 3px rgba(0,0,0,0.08); }}
                .stat-title {{ font-size:11px; color:#888; font-weight:bold; margin-bottom:5px; }}
                .stat-value {{ font-size:24px; font-weight:bold; color:#333; }}

                .data-table {{ width:100%; border-collapse:collapse; background:#fff; margin-top:10px; box-shadow:0 1px 3px rgba(0,0,0,0.1); }}
                .data-table th {{ background:#4a4a5a; color:#fff; padding:8px 10px; font-size:12px; text-align:left; }}
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
                function showTest(targetId, element) {{
                    var contents = document.getElementsByClassName('test-content');
                    for (var i = 0; i < contents.length; i++) {{
                        contents[i].style.display = 'none';
                    }}
                    var target = document.getElementById('module-' + targetId);
                    if (target) target.style.display = 'block';

                    var menuItems = document.getElementsByClassName('menu-item');
                    for (var i = 0; i < menuItems.length; i++) {{
                        menuItems[i].classList.remove('active');
                    }}
                    if(element) element.classList.add('active');
                }}

                function toggleFolder(folderId, arrowId) {{
                    var folder = document.getElementById(folderId);
                    var arrow = document.getElementById(arrowId);
                    if (folder.style.display === 'none') {{
                        folder.style.display = 'block';
                        arrow.classList.remove('collapsed');
                    }} else {{
                        folder.style.display = 'none';
                        arrow.classList.add('collapsed');
                    }}
                }}
            </script>
        </body>
        </html>
        """

        with open(report_file, "w", encoding="utf-8") as f:
            f.write(full_html)
        print(f"📊 Extent Report generated at: {report_file}")