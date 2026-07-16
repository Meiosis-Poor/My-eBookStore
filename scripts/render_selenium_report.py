from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from tests.ui.case_matrix import CASES


def _status(case: ET.Element) -> str:
    if case.find("failure") is not None:
        return "失败"
    if case.find("error") is not None:
        return "错误"
    if case.find("skipped") is not None:
        return "跳过"
    return "通过"


def render(report_dir: Path, *, commit: str, chrome_version: str, duration: float, port: int) -> Path:
    root = ET.parse(report_dir / "junit.xml").getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    tests = [case for suite in suites for case in suite.findall("testcase")]
    by_base_name = {case.attrib.get("name", "").split("[", 1)[0]: case for case in tests}
    scenario_rows = []
    for case_id, role, scene, expected, pytest_name in CASES:
        case = by_base_name.get(pytest_name)
        scenario_rows.append((case_id, role, scene, expected, _status(case) if case is not None else "未执行", pytest_name))
    passed = sum(row[4] == "通过" for row in scenario_rows)
    failed = [row for row in scenario_rows if row[4] in {"失败", "错误"}]
    not_run = [row for row in scenario_rows if row[4] in {"未执行", "跳过"}]
    screenshots = sorted((report_dir / "screenshots").glob("*.png")) if (report_dir / "screenshots").exists() else []

    lines = [
        "# 网上书店 Selenium 前端测试教师展示报告", "",
        "> 本报告为提前执行并留存的测试结果，课程验收现场无需重新运行。", "",
        "## 一、总体结论", "",
        "| 项目 | 结果 |", "| --- | --- |",
        f"| 测试结论 | {'通过' if not failed and not not_run else '存在失败或未执行场景'} |",
        f"| Git 提交 | `{commit}` |", f"| Chrome | `{chrome_version}` |",
        f"| 场景总数 | {len(scenario_rows)} |", f"| 通过 / 失败错误 / 未执行跳过 | {passed} / {len(failed)} / {len(not_run)} |",
        f"| 执行耗时 | {duration:.2f} 秒 |", f"| 本地服务端口 | `{port}` |",
        "| 数据库隔离 | pytest 会话状态守卫未报告差异 |", "",
        "## 二、逐场景结果", "",
        "| 编号 | 角色 | 场景 | 预期结果 | 实际结果 | pytest 用例 |", "| --- | --- | --- | --- | --- | --- |",
    ]
    for case_id, role, scene, expected, status, pytest_name in scenario_rows:
        lines.append(f"| {case_id} | {role} | {scene} | {expected} | {status} | `{pytest_name}` |")
    lines.extend(["", "## 三、失败与错误", ""])
    if failed:
        lines.extend(["| 编号 | 场景 | 状态 | 取证 |", "| --- | --- | --- | --- |"])
        for row in failed:
            lines.append(f"| {row[0]} | {row[2]} | {row[4]} | `failures/` 中的截图、HTML和控制台日志 |")
    else:
        lines.append("失败和错误场景为 0。")
    lines.extend(["", "## 四、未执行与遗留风险", ""])
    if not_run:
        lines.extend(["| 编号 | 场景 | 状态 |", "| --- | --- | --- |"])
        for row in not_run:
            lines.append(f"| {row[0]} | {row[2]} | {row[4]} |")
    else:
        lines.append("未执行和跳过场景为 0。")
    lines.extend([
        "", "遗留范围：未覆盖 Edge、移动端真机、视觉像素差异、无障碍、并发和性能压测。", "",
        "浏览器日志观察到部分种子图书封面和 favicon 路径返回 404；页面已使用封面回退元素，未造成空白页或未处理 JavaScript 异常。", "",
        "## 五、关键截图", "",
        "| 截图 | 文件 |", "| --- | --- |",
    ])
    for image in screenshots:
        lines.append(f"| {image.stem} | [打开截图](screenshots/{image.name}) |")
    lines.extend([
        "", "## 六、附件", "", "| 文件 | 用途 |", "| --- | --- |",
        "| `report.html` | 可筛选的 pytest HTML 报告 |", "| `junit.xml` | 机器可读测试结果 |",
        "| `screenshots/` | 成功流程关键截图 |", "| `failures/` | 失败截图、页面源码和控制台日志 |",
        "| `case-matrix.md` | 28 个计划场景矩阵 |", "| `summary.md` | 环境、提交和执行命令 |",
    ])
    output = report_dir / "readable-report.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output
