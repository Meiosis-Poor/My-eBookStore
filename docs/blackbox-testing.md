# 黑盒等价类与自动生成测试

本套件通过 HTTP 接口观察输入和输出，不依赖函数内部实现。Hypothesis 生成业务等价类、边界值和购物车状态序列；Schemathesis 从测试专用 OpenAPI 覆盖层生成请求，并检查所有路由不得出现未处理的 5xx。

## 安装与环境

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
$env:EBOOKSTORE_ENV_FILE = '.env.test'
```

数据库必须以 `_Test` 结尾、已经执行 `99_test_seed.sql`，并串行运行。写测试仅使用 UUID 临时资源；pytest 会话结束时比较种子图书库存、锁定库存、销量和奖励库存，并检查临时用户、图书、孤立订单及支付记录。

## 两档执行

日常快速档使用每个属性 20 个样本、状态序列最多 10 步：

```powershell
$env:EBOOKSTORE_BLACKBOX_PROFILE = 'smoke'
.\.venv\Scripts\python.exe -m pytest -m blackbox_smoke -q
```

Schemathesis 全路由契约检查可独立执行：

```powershell
.\.venv\Scripts\python.exe -m pytest -m schemathesis -q
```

课程展示档使用每个属性 100 个样本、状态序列最多 20 步，并固定随机种子：

```powershell
.\.venv\Scripts\python.exe scripts/run_blackbox_showcase.py --seed 20260716
```

仅在明确需要清空测试库时添加 `--reset`。该参数会拒绝开发库、系统库和任何不安全的数据库名。

## 报告与复现

展示结果写入 `test-results/blackbox/<timestamp>/`，包含面向教师阅读的 `readable-report.md`、JUnit XML、自包含 HTML、逐接口覆盖矩阵和 Markdown 汇总。目录默认不提交；课程提交时可从中选择一次成功结果另行归档。

已有 JUnit 报告也可以单独转换：

```powershell
.\.venv\Scripts\python.exe scripts/render_blackbox_report.py test-results/blackbox/<timestamp>
```

失败输出包含 Hypothesis 最小化输入。使用报告中的 seed 重跑：

```powershell
.\.venv\Scripts\python.exe -m pytest -m "blackbox_smoke or blackbox_full" --hypothesis-seed=20260716 -q
```

覆盖矩阵中的 `gap` 是真实缺口，不计为已覆盖。当前自动生成层对全部 OpenAPI 操作执行契约检查；涉及成功写入、跨店权限和特定业务状态的接口仍应以显式临时资源用例逐项关闭矩阵缺口。

本轮不包含 UI 自动化、真实并发压测或完整渗透测试。

## 一次性白盒展示

白盒展示提前运行并留存，验收现场无需再次执行：

```powershell
$env:EBOOKSTORE_ENV_FILE = '.env.test'
.\.venv\Scripts\python.exe scripts/run_whitebox_showcase.py --archive
```

教师主要查看 `docs/reports/whitebox-showcase/readable-report.md`，逐行覆盖页面位于同目录的 `coverage-html/index.html`。

## Selenium 前端展示

Chrome 端到端测试同样提前运行并归档：

```powershell
$env:EBOOKSTORE_ENV_FILE = '.env.test'
.\.venv\Scripts\python.exe scripts/run_selenium_showcase.py --archive
```

教师主要查看 `docs/reports/selenium-showcase/readable-report.md`，原始浏览器测试结果和关键截图位于同一目录。
