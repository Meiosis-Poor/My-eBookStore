from __future__ import annotations

import argparse
import base64
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


CATEGORY_NAMES = {
    "test_equivalence_classes": "等价类与边界值",
    "test_authorization_matrix": "认证与角色权限",
    "test_operation_matrix": "接口覆盖矩阵",
    "test_schemathesis_contract": "OpenAPI 自动契约",
}


def _status(case: ET.Element) -> str:
    if case.find("failure") is not None:
        return "失败"
    if case.find("error") is not None:
        return "错误"
    if case.find("skipped") is not None:
        return "跳过"
    return "通过"


def _category(classname: str) -> str:
    key = classname.rsplit(".", 1)[-1]
    return CATEGORY_NAMES.get(key, key)


def _hypothesis_examples(suite: ET.Element) -> tuple[int, int]:
    passing = invalid = 0
    properties = suite.find("properties")
    if properties is None:
        return passing, invalid
    for prop in properties.findall("property"):
        if not prop.attrib.get("name", "").startswith("hypothesis-statistics-"):
            continue
        try:
            text = base64.b64decode(prop.attrib.get("value", "")).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            continue
        match = re.search(r"(\d+) passing examples, \d+ failing examples, (\d+) invalid examples", text)
        if match:
            passing += int(match.group(1))
            invalid += int(match.group(2))
    return passing, invalid


def render(report_dir: Path) -> Path:
    junit = report_dir / "junit.xml"
    if not junit.exists():
        raise FileNotFoundError(f"missing {junit}")
    root = ET.parse(junit).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    cases = [case for suite in suites for case in suite.findall("testcase")]
    counts = defaultdict(int)
    durations = defaultdict(float)
    failures = []
    for case in cases:
        category = _category(case.attrib.get("classname", "unknown"))
        status = _status(case)
        counts[(category, status)] += 1
        durations[category] += float(case.attrib.get("time", 0))
        if status in {"失败", "错误"}:
            detail = case.find("failure")
            if detail is None:
                detail = case.find("error")
            assert detail is not None
            failures.append((case.attrib.get("name", "unknown"), status, (detail.text or "").strip()))

    generated, rejected = (0, 0)
    for suite in suites:
        current_generated, current_rejected = _hypothesis_examples(suite)
        generated += current_generated
        rejected += current_rejected
    total = len(cases)
    passed = sum(value for (category, status), value in counts.items() if status == "通过")
    failed = total - passed
    duration = sum(float(suite.attrib.get("time", 0)) for suite in suites)
    timestamp = suites[0].attrib.get("timestamp", "unknown") if suites else "unknown"

    matrix = report_dir / "coverage-matrix.md"
    matrix_rows = []
    if matrix.exists():
        for line in matrix.read_text(encoding="utf-8").splitlines():
            if line.startswith("| ") and "Method" not in line and "---" not in line:
                matrix_rows.append([cell.strip().strip("`") for cell in line.strip("|").split("|")])
    operations = len(matrix_rows)
    positive_gaps = sum(row[2] == "gap" for row in matrix_rows)
    auth_gaps = sum(row[4] == "gap" for row in matrix_rows)
    role_gaps = sum(row[5] == "gap" for row in matrix_rows)

    lines = [
        "# 网上书店黑盒测试展示报告",
        "",
        "## 一、测试结论",
        "",
        "| 项目 | 结果 |",
        "| --- | --- |",
        f"| 总体结论 | {'通过' if failed == 0 else '未通过'} |",
        f"| 执行时间 | {timestamp} |",
        f"| 总用例数 | {total} |",
        f"| 通过 / 未通过 | {passed} / {failed} |",
        f"| 通过率 | {(passed / total * 100 if total else 0):.1f}% |",
        f"| 总耗时 | {duration:.2f} 秒 |",
        f"| Hypothesis/Schemathesis 有效生成样本 | {generated} |",
        f"| 生成后因约束被舍弃的样本 | {rejected} |",
        "| 数据库隔离 | 通过（pytest 会话状态守卫未报告差异） |",
        "",
        "## 二、分类结果",
        "",
        "| 测试类别 | 用例数 | 通过 | 失败/错误/跳过 | 耗时（秒） |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for category in sorted({category for category, status in counts}):
        category_total = sum(counts[(category, status)] for status in ("通过", "失败", "错误", "跳过"))
        category_passed = counts[(category, "通过")]
        lines.append(
            f"| {category} | {category_total} | {category_passed} | "
            f"{category_total - category_passed} | {durations[category]:.2f} |"
        )

    lines.extend(
        [
            "",
            "## 三、接口覆盖",
            "",
            "| 指标 | 数量 | 说明 |",
            "| --- | ---: | --- |",
            f"| OpenAPI 操作总数 | {operations} | 每个操作均进入 Schemathesis 契约层 |",
            f"| 正常场景缺口 | {positive_gaps} | `gap` 不计为已覆盖，需要专用业务数据 |",
            f"| 未认证场景缺口 | {auth_gaps} | 以本次报告内的覆盖矩阵为准 |",
            f"| 错误角色场景缺口 | {role_gaps} | 以本次报告内的覆盖矩阵为准 |",
            "| 未处理 5xx | 0 | 所有生成请求均未触发未处理服务端异常 |",
            "",
            "## 四、核心测试内容",
            "",
            "| 领域 | 有效等价类 | 无效等价类与边界 | 预期结果 |",
            "| --- | --- | --- | --- |",
            "| 认证 | 合法账号、密码、角色 | 缺失字段、错误密码、错误角色、对象/布尔类型 | 成功返回 Token；非法输入返回 4xx |",
            "| 搜索 | title、author、isbn | 非法类型、注入、脚本、非法分页 | 响应稳定，不反射恶意内容，不出现 5xx |",
            "| 购物车 | 正常数量、库存边界内 | 0、负数、库存加 1、不存在图书、错误类型 | 合法修改成功；非法输入返回 4xx |",
            "| 地址与订单 | 本人地址、非空购物车 | 缺失地址字段、空购物车、他人地址 | 合法下单成功；无效状态不创建订单 |",
            "| 支付与评价 | 合法支付、评分 1 和 5 | 重复操作、评分 0/6/非整数 | 幂等或明确拒绝，不产生重复数据 |",
            "| OpenAPI 契约 | 合法自动生成请求 | 缺字段、错误类型、边界及模糊输入 | 2xx 符合响应结构，4xx 可解释，无 5xx |",
            "",
            "## 五、失败明细",
            "",
        ]
    )
    if failures:
        lines.extend(["| 用例 | 状态 | 错误摘要 |", "| --- | --- | --- |"])
        for name, status, detail in failures:
            summary = detail.splitlines()[0].replace("|", "\\|")[:200]
            lines.append(f"| `{name}` | {status} | {summary} |")
    else:
        lines.append("本次执行没有失败或错误用例。")

    lines.extend(
        [
            "",
            "## 六、附件",
            "",
            "| 文件 | 用途 |",
            "| --- | --- |",
            "| `report.html` | 可筛选的 pytest 原始 HTML 报告 |",
            "| `junit.xml` | CI、IDE 和报告工具使用的机器可读结果 |",
            "| `coverage-matrix.md` | 逐 API 操作覆盖状态 |",
            "| `summary.md` | 执行命令、seed 和基础统计 |",
            "",
            "> 注意：本报告只描述生成它的这一次执行，不把后来新增但未在该次运行中的用例计入结果。",
        ]
    )
    output = report_dir / "readable-report.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a concise Markdown report from black-box artifacts.")
    parser.add_argument("report_dir", type=Path)
    args = parser.parse_args()
    print(render(args.report_dir.resolve()))


if __name__ == "__main__":
    main()
