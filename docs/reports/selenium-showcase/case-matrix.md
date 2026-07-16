# Selenium 场景矩阵

| 编号 | 角色 | 场景 | 预期结果 | pytest 用例 |
| --- | --- | --- | --- | --- |
| UI-01 | 公共 | 首页加载 | 首页品牌、导航和图书区域可见 | `test_public_pages_and_search` |
| UI-02 | 公共 | 页面导航 | 搜索、促销和登录页面可访问 | `test_public_pages_and_search` |
| UI-03 | 公共 | 图书搜索 | 临时图书可被标题搜索命中 | `test_public_pages_and_search` |
| UI-04 | 公共 | 图书详情 | 详情页显示临时图书信息 | `test_public_pages_and_search` |
| UI-05 | 认证 | 空表单 | 显示用户名必填错误 | `test_login_validation_and_wrong_password` |
| UI-06 | 认证 | 错误密码 | 显示错误提示且不写入Token | `test_login_validation_and_wrong_password` |
| UI-07 | 顾客 | 顾客登录 | 登录后跳转首页并保存会话 | `test_role_login` |
| UI-08 | 卖家 | 卖家登录 | 登录后跳转后台 | `test_role_login` |
| UI-09 | 管理员 | 管理员登录 | 登录后跳转后台 | `test_role_login` |
| UI-10 | 认证 | 退出登录 | 本地会话清除 | `test_logout` |
| UI-11 | 顾客 | 加入购物车 | 购物车出现临时图书 | `test_customer_checkout_payment_review` |
| UI-12 | 顾客 | 修改数量 | 数量修改为2并保持 | `test_customer_checkout_payment_review` |
| UI-13 | 顾客 | 库存边界 | 非法数量被限制为合法值 | `test_customer_checkout_payment_review` |
| UI-14 | 顾客 | 结算与地址 | 临时地址和商品正确显示 | `test_customer_checkout_payment_review` |
| UI-15 | 顾客 | 创建订单 | 跳转支付页并生成订单 | `test_customer_checkout_payment_review` |
| UI-16 | 顾客 | 模拟支付 | 支付成功并跳转结果页 | `test_customer_checkout_payment_review` |
| UI-17 | 顾客 | 订单查询 | 订单详情与支付结果一致 | `test_customer_checkout_payment_review` |
| UI-18 | 顾客 | 评价 | 首次评价成功且重复评价拒绝 | `test_customer_checkout_payment_review` |
| UI-19 | 顾客 | 取消订单 | 待支付订单取消后状态更新 | `test_cancel_pending_order` |
| UI-20 | 安全 | 未登录访问 | 受保护页面跳转登录 | `test_session_and_admin_guards` |
| UI-21 | 安全 | 伪造会话 | 无效Token不能读取受保护数据 | `test_session_and_admin_guards` |
| UI-22 | 顾客 | 刷新保持 | 刷新后登录和数据保持 | `test_customer_checkout_payment_review` |
| UI-23 | 卖家 | 卖家图书列表 | 本店图书管理页面可见 | `test_seller_admin_pages` |
| UI-24 | 卖家 | 维护图书 | 新增图书入口和表单可用 | `test_seller_admin_pages` |
| UI-25 | 卖家 | 订单范围 | 订单页面可用且平台入口受限 | `test_seller_admin_pages` |
| UI-26 | 管理员 | 统计页面 | 统计和导出入口可见 | `test_platform_admin_pages` |
| UI-27 | 管理员 | 平台权限 | 用户、店铺、促销和推荐页面可访问 | `test_platform_admin_pages` |
| UI-28 | 安全 | 顾客越权后台 | 顾客不能使用后台页面 | `test_session_and_admin_guards` |
