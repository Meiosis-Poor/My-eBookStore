# 网上书店 Selenium 前端测试教师展示报告

> 本报告为提前执行并留存的测试结果，课程验收现场无需重新运行。

## 一、总体结论

| 项目 | 结果 |
| --- | --- |
| 测试结论 | 通过 |
| Git 提交 | `4a5f6ea` |
| Chrome | `149.0.7827.199` |
| 场景总数 | 28 |
| 通过 / 失败错误 / 未执行跳过 | 28 / 0 / 0 |
| 执行耗时 | 67.18 秒 |
| 本地服务端口 | `61302` |
| 数据库隔离 | pytest 会话状态守卫未报告差异 |

## 二、逐场景结果

| 编号 | 角色 | 场景 | 预期结果 | 实际结果 | pytest 用例 |
| --- | --- | --- | --- | --- | --- |
| UI-01 | 公共 | 首页加载 | 首页品牌、导航和图书区域可见 | 通过 | `test_public_pages_and_search` |
| UI-02 | 公共 | 页面导航 | 搜索、促销和登录页面可访问 | 通过 | `test_public_pages_and_search` |
| UI-03 | 公共 | 图书搜索 | 临时图书可被标题搜索命中 | 通过 | `test_public_pages_and_search` |
| UI-04 | 公共 | 图书详情 | 详情页显示临时图书信息 | 通过 | `test_public_pages_and_search` |
| UI-05 | 认证 | 空表单 | 显示用户名必填错误 | 通过 | `test_login_validation_and_wrong_password` |
| UI-06 | 认证 | 错误密码 | 显示错误提示且不写入Token | 通过 | `test_login_validation_and_wrong_password` |
| UI-07 | 顾客 | 顾客登录 | 登录后跳转首页并保存会话 | 通过 | `test_role_login` |
| UI-08 | 卖家 | 卖家登录 | 登录后跳转后台 | 通过 | `test_role_login` |
| UI-09 | 管理员 | 管理员登录 | 登录后跳转后台 | 通过 | `test_role_login` |
| UI-10 | 认证 | 退出登录 | 本地会话清除 | 通过 | `test_logout` |
| UI-11 | 顾客 | 加入购物车 | 购物车出现临时图书 | 通过 | `test_customer_checkout_payment_review` |
| UI-12 | 顾客 | 修改数量 | 数量修改为2并保持 | 通过 | `test_customer_checkout_payment_review` |
| UI-13 | 顾客 | 库存边界 | 非法数量被限制为合法值 | 通过 | `test_customer_checkout_payment_review` |
| UI-14 | 顾客 | 结算与地址 | 临时地址和商品正确显示 | 通过 | `test_customer_checkout_payment_review` |
| UI-15 | 顾客 | 创建订单 | 跳转支付页并生成订单 | 通过 | `test_customer_checkout_payment_review` |
| UI-16 | 顾客 | 模拟支付 | 支付成功并跳转结果页 | 通过 | `test_customer_checkout_payment_review` |
| UI-17 | 顾客 | 订单查询 | 订单详情与支付结果一致 | 通过 | `test_customer_checkout_payment_review` |
| UI-18 | 顾客 | 评价 | 首次评价成功且重复评价拒绝 | 通过 | `test_customer_checkout_payment_review` |
| UI-19 | 顾客 | 取消订单 | 待支付订单取消后状态更新 | 通过 | `test_cancel_pending_order` |
| UI-20 | 安全 | 未登录访问 | 受保护页面跳转登录 | 通过 | `test_session_and_admin_guards` |
| UI-21 | 安全 | 伪造会话 | 无效Token不能读取受保护数据 | 通过 | `test_session_and_admin_guards` |
| UI-22 | 顾客 | 刷新保持 | 刷新后登录和数据保持 | 通过 | `test_customer_checkout_payment_review` |
| UI-23 | 卖家 | 卖家图书列表 | 本店图书管理页面可见 | 通过 | `test_seller_admin_pages` |
| UI-24 | 卖家 | 维护图书 | 新增图书入口和表单可用 | 通过 | `test_seller_admin_pages` |
| UI-25 | 卖家 | 订单范围 | 订单页面可用且平台入口受限 | 通过 | `test_seller_admin_pages` |
| UI-26 | 管理员 | 统计页面 | 统计和导出入口可见 | 通过 | `test_platform_admin_pages` |
| UI-27 | 管理员 | 平台权限 | 用户、店铺、促销和推荐页面可访问 | 通过 | `test_platform_admin_pages` |
| UI-28 | 安全 | 顾客越权后台 | 顾客不能使用后台页面 | 通过 | `test_session_and_admin_guards` |

## 三、失败与错误

失败和错误场景为 0。

## 四、未执行与遗留风险

未执行和跳过场景为 0。

遗留范围：未覆盖 Edge、移动端真机、视觉像素差异、无障碍、并发和性能压测。

浏览器日志观察到部分种子图书封面和 favicon 路径返回 404；页面已使用封面回退元素，未造成空白页或未处理 JavaScript 异常。

## 五、关键截图

| 截图 | 文件 |
| --- | --- |
| customer-cart | [打开截图](screenshots/customer-cart.png) |
| customer-order-detail | [打开截图](screenshots/customer-order-detail.png) |
| customer-payment-success | [打开截图](screenshots/customer-payment-success.png) |
| customer-payment | [打开截图](screenshots/customer-payment.png) |
| login-customer | [打开截图](screenshots/login-customer.png) |
| login-platform_admin | [打开截图](screenshots/login-platform_admin.png) |
| login-seller | [打开截图](screenshots/login-seller.png) |
| platform-admin | [打开截图](screenshots/platform-admin.png) |
| public-book-detail | [打开截图](screenshots/public-book-detail.png) |
| seller-books | [打开截图](screenshots/seller-books.png) |

## 六、附件

| 文件 | 用途 |
| --- | --- |
| `report.html` | 可筛选的 pytest HTML 报告 |
| `junit.xml` | 机器可读测试结果 |
| `screenshots/` | 成功流程关键截图 |
| `failures/` | 失败截图、页面源码和控制台日志 |
| `case-matrix.md` | 28 个计划场景矩阵 |
| `summary.md` | 环境、提交和执行命令 |
