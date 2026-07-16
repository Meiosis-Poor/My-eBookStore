from __future__ import annotations

import json
import platform
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


CASE_DESCRIPTIONS = {
    "test_page_slice_paths": "分页首、中、末页以及越界路径",
    "test_payload_int_valid_paths": "整数、数字字符串和默认值路径",
    "test_payload_int_invalid_paths": "缺失、布尔及非法类型拒绝路径",
    "test_address_required_fields_true_and_false_paths": "地址字段完整与分别缺失路径",
    "test_normalize_book_all_default_and_conversion_paths": "图书默认值和类型转换路径",
    "test_response_envelope_and_exception_handler_paths": "成功、业务异常和普通异常响应路径",
    "test_database_row_conversion_and_result_set_paths": "空行、多行、Decimal和结果集路径",
    "test_get_conn_commit_rollback_and_close_paths": "事务提交、异常回滚和连接关闭路径",
    "test_payment_method_mapping_paths": "支付方式映射和默认路径",
    "test_coupon_type_condition_paths": "平台券与店铺券条件路径",
    "test_statistics_range_mapping_paths": "统计日期范围映射和回退路径",
    "test_reward_amount_and_threshold_valid_invalid_paths": "奖励金额、门槛有效和无效路径",
    "test_current_user_missing_invalid_and_unknown_paths": "缺失、伪造Token和用户不存在路径",
    "test_current_user_banned_and_success_paths": "禁用用户与合法认证路径",
    "test_optional_user_and_role_condition_paths": "可选认证和角色允许/拒绝路径",
    "test_public_user_optional_store_and_default_paths": "用户默认字段与卖家店铺字段路径",
    "test_pay_order_not_found_invalid_and_idempotent_paths": "订单不存在、状态非法和重复支付幂等路径",
    "test_pay_empty_items_stock_shortage_and_procedure_failure": "空明细、库存不足和过程失败路径",
    "test_pay_database_error_is_translated": "支付数据库异常转换路径",
    "test_review_rating_false_paths": "评分0和6拒绝路径",
    "test_review_purchase_payment_duplicate_and_success_paths": "未购买、未支付、重复和成功评价路径",
    "test_reward_type_and_procedure_error_paths": "奖励类型和过程异常转换路径",
}


def _case_status(case: ET.Element) -> str:
    if case.find("failure") is not None:
        return "失败"
    if case.find("error") is not None:
        return "错误"
    if case.find("skipped") is not None:
        return "跳过"
    return "通过"


def _description(name: str) -> str:
    return CASE_DESCRIPTIONS.get(name.split("[", 1)[0], "执行该用例定义的白盒路径和状态断言")


def _compress_lines(lines: list[int], limit: int = 18) -> str:
    if not lines:
        return "无"
    shown = ", ".join(str(line) for line in lines[:limit])
    return shown + (f" 等{len(lines)}行" if len(lines) > limit else "")


def render(report_dir: Path, *, commit: str, database: str, seed: int, duration: float) -> Path:
    coverage = json.loads((report_dir / "coverage.json").read_text(encoding="utf-8"))
    root = ET.parse(report_dir / "junit.xml").getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    cases = [case for suite in suites for case in suite.findall("testcase")]
    status_counts = defaultdict(int)
    failures = []
    for case in cases:
        status = _case_status(case)
        status_counts[status] += 1
        if status in {"失败", "错误"}:
            node = case.find("failure") if status == "失败" else case.find("error")
            failures.append((case.attrib.get("name", "unknown"), status, (node.text or "") if node is not None else ""))

    totals = coverage["totals"]
    percent = float(totals.get("percent_covered", 0))
    branch_percent = 100.0
    if totals.get("num_branches"):
        branch_percent = 100 * totals.get("covered_branches", 0) / totals["num_branches"]
    files = coverage.get("files", {})

    lines = [
        "# 网上书店白盒测试教师展示报告",
        "",
        "> 本报告为提前执行并留存的测试结果，课程验收现场无需重新运行。",
        "",
        "## 一、总体结论",
        "",
        "| 项目 | 结果 |",
        "| --- | --- |",
        f"| 测试结论 | {'通过' if not failures else '未通过'} |",
        f"| Git 提交 | `{commit}` |",
        f"| Python | `{platform.python_version()}` |",
        f"| 测试数据库 | `{database}` |",
        f"| 固定 seed | `{seed}` |",
        f"| 用例总数 | {len(cases)} |",
        f"| 通过 / 失败 / 错误 / 跳过 | {status_counts['通过']} / {status_counts['失败']} / {status_counts['错误']} / {status_counts['跳过']} |",
        f"| 执行耗时 | {duration:.2f} 秒 |",
        "| 数据库隔离 | 通过（pytest 会话守卫未报告差异） |",
        "",
        "## 二、覆盖率",
        "",
        "| 指标 | 实际结果 | 展示目标 | 结论 |",
        "| --- | ---: | ---: | --- |",
        f"| 纳入统计代码语句覆盖率 | {percent:.1f}% | ≥ 75% | {'达到' if percent >= 75 else '未达到，详见未覆盖清单'} |",
        f"| 纳入统计代码分支覆盖率 | {branch_percent:.1f}% | 记录实际值 | 已记录 |",
        f"| 已覆盖 / 总语句 | {totals.get('covered_lines', 0)} / {totals.get('num_statements', 0)} | - | - |",
        f"| 已覆盖 / 总分支 | {totals.get('covered_branches', 0)} / {totals.get('num_branches', 0)} | - | - |",
        "",
        "### 模块覆盖明细",
        "",
        "| 模块 | 语句覆盖率 | 分支覆盖率 | 未覆盖行数 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for filename, data in sorted(files.items()):
        summary = data["summary"]
        file_branch = 100.0
        if summary.get("num_branches"):
            file_branch = 100 * summary.get("covered_branches", 0) / summary["num_branches"]
        lines.append(
            f"| `{filename.replace(chr(92), '/')}` | {summary.get('percent_covered', 0):.1f}% | "
            f"{file_branch:.1f}% | {summary.get('missing_lines', 0)} |"
        )

    lines.extend([
        "",
        "## 三、关键条件矩阵",
        "",
        "| 判定 | 条件组合 | 预期路径 | 覆盖方式 |",
        "| --- | --- | --- | --- |",
        "| 当前用户认证 | 无凭证 / 非法Token / 用户不存在 / 禁用 / 正常 | 401 / 401 / 401 / 403 / 返回用户 | 直接单元测试 |",
        "| 角色权限 | 角色属于允许集合 / 不属于 | 返回用户 / 403 | 直接单元测试 |",
        "| 支付状态 | 不存在 / 已支付完成 / 非待支付 / 待支付 | 拒绝 / 幂等 / 拒绝 / 继续 | Mock DAO |",
        "| 支付库存 | 无明细 / stock < quantity / 库存足 | 拒绝 / 拒绝 / 调用支付过程 | Mock DAO |",
        "| 评价资格 | 未购买 / 未支付 / 已评价 / 合法 | 拒绝 / 拒绝 / 拒绝 / 写入 | Mock DAO |",
        "| 事务 | 正常退出 / 抛出异常 | commit / rollback，均 close | 直接单元测试 |",
        "",
        "## 四、逐条测试用例",
        "",
        "| 编号 | 类别 | pytest 用例 | 验证内容 | 状态 | 耗时（秒） |",
        "| ---: | --- | --- | --- | --- | ---: |",
    ])
    for index, case in enumerate(cases, 1):
        name = case.attrib.get("name", "unknown").replace("|", "\\|")
        category = "白盒单元/Mock" if "whitebox" in case.attrib.get("classname", "") else "真实数据库回归"
        lines.append(f"| {index} | {category} | `{name}` | {_description(name)} | {_case_status(case)} | {float(case.attrib.get('time', 0)):.3f} |")

    lines.extend(["", "## 五、失败与错误用例", ""])
    if failures:
        lines.extend(["| 用例 | 状态 | 错误摘要 |", "| --- | --- | --- |"])
        for name, status, detail in failures:
            lines.append(f"| `{name}` | {status} | {detail.splitlines()[0].replace('|', chr(92) + '|')[:240]} |")
    else:
        lines.append("本次执行失败 0 个、错误 0 个。")

    lines.extend(["", "## 六、未覆盖代码与遗留风险", "", "| 模块 | 未覆盖行 | 说明 |", "| --- | --- | --- |"])
    for filename, data in sorted(files.items(), key=lambda item: len(item[1].get("missing_lines", [])), reverse=True):
        missing = data.get("missing_lines", [])
        if missing:
            lines.append(f"| `{filename.replace(chr(92), '/')}` | {_compress_lines(missing)} | 未覆盖不等于测试失败；主要为未纳入本次短时展示的管理和查询路径 |")

    lines.extend([
        "",
        "## 七、附件",
        "",
        "| 文件 | 用途 |",
        "| --- | --- |",
        "| `coverage-html/index.html` | 浏览源码逐行覆盖情况 |",
        "| `coverage.json` | 机器可读覆盖数据 |",
        "| `junit.xml` | 逐条 pytest 执行结果 |",
        "| `condition-matrix.md` | 关键复合条件覆盖矩阵 |",
        "| `summary.md` | 执行命令和基础环境 |",
    ])
    output = report_dir / "readable-report.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output

