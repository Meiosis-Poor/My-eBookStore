# 网上书店 Selenium 前端测试教师展示报告

> 本报告为提前执行并留存的测试结果，课程验收现场无需重新运行。

## 一、总体结论

| 项目 | 结果 |
| --- | --- |
| 测试结论 | 通过 |
| Git 提交 | `0ae3424` |
| Chrome | `149.0.7827.199` |
| 场景总数 | 104 |
| 通过 / 失败错误 / 未执行跳过 | 104 / 0 / 0 |
| 执行耗时 | 132.69 秒 |
| 本地服务端口 | `63005` |
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
| UI-29 | 顾客 | 每日签到 | 首次签到成功并增加积分 | 通过 | `test_customer_promotions_and_points` |
| UI-30 | 顾客 | 重复签到 | 同日重复签到被拒绝 | 通过 | `test_customer_promotions_and_points` |
| UI-31 | 顾客 | 积分流水 | 签到积分流水可查询 | 通过 | `test_customer_promotions_and_points` |
| UI-32 | 顾客 | 积分奖励列表 | 奖励条件和库存正常展示 | 通过 | `test_customer_promotions_and_points` |
| UI-33 | 顾客 | 积分不足兑换 | 积分不足时不产生兑换 | 通过 | `test_customer_reward_boundaries` |
| UI-34 | 顾客 | 等级不足兑换 | 等级不足时不产生兑换 | 通过 | `test_customer_reward_boundaries` |
| UI-35 | 顾客 | 奖励库存不足 | 库存为0时拒绝兑换 | 通过 | `test_customer_reward_boundaries` |
| UI-36 | 顾客 | 成功兑换实物 | 积分和库存正确扣减 | 通过 | `test_customer_reward_boundaries` |
| UI-37 | 顾客 | 成功兑换代金券 | 券包出现兑换所得券 | 通过 | `test_customer_reward_boundaries` |
| UI-38 | 顾客 | 领取每周优惠券 | 满足等级时领取成功 | 通过 | `test_customer_promotions_and_points` |
| UI-39 | 顾客 | 重复领取周券 | 同周期重复领取被拒绝 | 通过 | `test_customer_promotions_and_points` |
| UI-40 | 顾客 | 参加促销活动 | 活动参与成功 | 通过 | `test_customer_activity_and_coupon_paths` |
| UI-41 | 顾客 | 重复参加活动 | 重复参加保持幂等或拒绝 | 通过 | `test_customer_activity_and_coupon_paths` |
| UI-42 | 顾客 | 活动发放优惠券 | 参加活动后券包增加 | 通过 | `test_customer_activity_and_coupon_paths` |
| UI-43 | 顾客 | 优惠券结算 | 有效券正确抵扣 | 通过 | `test_customer_activity_and_coupon_paths` |
| UI-44 | 顾客 | 未达门槛用券 | 差0.01时不可使用 | 通过 | `test_customer_activity_and_coupon_paths` |
| UI-45 | 顾客 | 跨店优惠券 | 其他店铺商品不可使用 | 通过 | `test_customer_activity_and_coupon_paths` |
| UI-46 | 顾客 | 过期优惠券 | 过期券不可结算 | 通过 | `test_customer_activity_and_coupon_paths` |
| UI-47 | 卖家 | 参加平台活动 | 参与配置刷新后保持 | 通过 | `test_seller_promotion_paths` |
| UI-48 | 卖家 | 退出平台活动 | 参与图书和券配置清理 | 通过 | `test_seller_promotion_paths` |
| UI-49 | 管理员 | 创建促销活动 | 活动在后台与顾客端可见 | 通过 | `test_admin_promotion_reward_paths` |
| UI-50 | 管理员 | 编辑促销活动 | 修改内容刷新后保持 | 通过 | `test_admin_promotion_reward_paths` |
| UI-51 | 管理员 | 创建积分奖励 | 奖励出现在兑换列表 | 通过 | `test_admin_promotion_reward_paths` |
| UI-52 | 管理员 | 编辑积分奖励 | 条件和库存修改后保持 | 通过 | `test_admin_promotion_reward_paths` |
| UI-53 | 卖家 | 新增图书 | 新图书出现在本店和前台 | 通过 | `test_seller_book_crud_paths` |
| UI-54 | 卖家 | 重复ISBN | 重复ISBN被拒绝 | 通过 | `test_seller_book_crud_paths` |
| UI-55 | 卖家 | 编辑图书 | 价格库存简介更新后保持 | 通过 | `test_seller_book_crud_paths` |
| UI-56 | 卖家 | 下架图书 | 前台不可继续购买 | 通过 | `test_seller_book_crud_paths` |
| UI-57 | 卖家 | 下架购物车商品 | 结算拒绝且不创建订单 | 通过 | `test_seller_book_crud_paths` |
| UI-58 | 卖家 | 库存设置为0 | 前台显示售罄 | 通过 | `test_seller_book_crud_paths` |
| UI-59 | 卖家 | 非法价格 | 负数空值非数字被拒绝 | 通过 | `test_seller_book_validation_paths` |
| UI-60 | 卖家 | 非法库存 | 负数小数非数字被拒绝 | 通过 | `test_seller_book_validation_paths` |
| UI-61 | 卖家 | 本店订单列表 | 仅显示本店相关订单 | 通过 | `test_seller_order_refund_paths` |
| UI-62 | 卖家 | 跨店订单隔离 | 跨店订单访问返回无权限 | 通过 | `test_seller_order_refund_paths` |
| UI-63 | 卖家 | 更新订单状态 | 允许的状态转换保存成功 | 通过 | `test_seller_order_refund_paths` |
| UI-64 | 卖家 | 非法状态转换 | 非法转换被拒绝 | 通过 | `test_seller_order_refund_paths` |
| UI-65 | 卖家 | 查看退款申请 | 本店待处理退款可见 | 通过 | `test_seller_order_refund_paths` |
| UI-66 | 卖家 | 批准退款 | 退款后库存销量恢复 | 通过 | `test_seller_order_refund_paths` |
| UI-67 | 卖家 | 拒绝退款 | 交易数据保持不变 | 通过 | `test_seller_order_refund_paths` |
| UI-68 | 卖家 | 跨店退款审批 | 其他店退款返回403 | 通过 | `test_seller_order_refund_paths` |
| UI-69 | 卖家 | 编辑店铺资料 | 前台同步显示新资料 | 通过 | `test_seller_store_blacklist_paths` |
| UI-70 | 卖家 | 空店铺名称 | 空名称被拒绝且原值保持 | 通过 | `test_seller_store_blacklist_paths` |
| UI-71 | 卖家 | 查看经营统计 | 统计仅包含本店数据 | 通过 | `test_seller_store_blacklist_paths` |
| UI-72 | 卖家 | 导出本店统计 | CSV仅包含本店数据 | 通过 | `test_seller_store_blacklist_paths` |
| UI-73 | 卖家 | 用户黑名单 | 临时顾客被禁止购买 | 通过 | `test_seller_store_blacklist_paths` |
| UI-74 | 卖家 | 解除黑名单 | 顾客恢复访问和购买 | 通过 | `test_seller_store_blacklist_paths` |
| UI-75 | 卖家 | 重复拉黑 | 操作幂等且无重复记录 | 通过 | `test_seller_store_blacklist_paths` |
| UI-76 | 卖家 | 越权平台页 | 平台管理页拒绝卖家 | 通过 | `test_seller_store_blacklist_paths` |
| UI-77 | 管理员 | 用户列表与搜索 | 临时用户名可搜索 | 通过 | `test_admin_user_store_paths` |
| UI-78 | 管理员 | 禁用用户 | 登录和已有Token均失效 | 通过 | `test_admin_user_store_paths` |
| UI-79 | 管理员 | 恢复用户 | 顾客恢复登录 | 通过 | `test_admin_user_store_paths` |
| UI-80 | 管理员 | 禁用卖家 | 临时卖家不能操作后台 | 通过 | `test_admin_user_store_paths` |
| UI-81 | 管理员 | 店铺列表与搜索 | 临时店铺信息正确显示 | 通过 | `test_admin_user_store_paths` |
| UI-82 | 管理员 | 禁用店铺 | 前台不能购买店铺商品 | 通过 | `test_admin_user_store_paths` |
| UI-83 | 管理员 | 恢复店铺 | 店铺恢复访问 | 通过 | `test_admin_user_store_paths` |
| UI-84 | 管理员 | 强制下架图书 | 违规图书从前台消失 | 通过 | `test_admin_book_order_paths` |
| UI-85 | 管理员 | 重复强制下架 | 重复操作保持幂等 | 通过 | `test_admin_book_order_paths` |
| UI-86 | 管理员 | 全平台订单查询 | 按订单号返回正确数据 | 通过 | `test_admin_book_order_paths` |
| UI-87 | 管理员 | 平台退款批准 | 交易和库存恢复 | 通过 | `test_admin_book_order_paths` |
| UI-88 | 管理员 | 平台退款拒绝 | 申请拒绝且交易不变 | 通过 | `test_admin_book_order_paths` |
| UI-89 | 管理员 | 创建平台优惠券 | 优惠券保存并可使用 | 通过 | `test_admin_promotion_reward_paths` |
| UI-90 | 管理员 | 无效优惠券金额 | 非法金额不创建券 | 通过 | `test_admin_promotion_reward_paths` |
| UI-91 | 管理员 | 过期时间校验 | 结束早于开始时拒绝保存 | 通过 | `test_admin_promotion_reward_paths` |
| UI-92 | 管理员 | 创建实物奖励 | 实物奖励出现在顾客端 | 通过 | `test_admin_promotion_reward_paths` |
| UI-93 | 管理员 | 创建代金券奖励 | 兑换生成正确代金券 | 通过 | `test_admin_promotion_reward_paths` |
| UI-94 | 管理员 | 重复奖励名称 | 同名奖励被拒绝 | 通过 | `test_admin_promotion_reward_paths` |
| UI-95 | 管理员 | 推荐设置读取 | 当前设置正确回显 | 通过 | `test_admin_recommendation_statistics_paths` |
| UI-96 | 管理员 | 修改推荐权重 | 刷新后配置保持 | 通过 | `test_admin_recommendation_statistics_paths` |
| UI-97 | 管理员 | 关闭详情推荐 | 详情相似推荐关闭 | 通过 | `test_admin_recommendation_statistics_paths` |
| UI-98 | 管理员 | 恢复推荐配置 | 配置恢复测试前基线 | 通过 | `test_admin_recommendation_statistics_paths` |
| UI-99 | 管理员 | 平台统计总览 | 平台KPI正确展示 | 通过 | `test_admin_recommendation_statistics_paths` |
| UI-100 | 管理员 | 风险店铺分析 | 仅展示风险分数大于0店铺 | 通过 | `test_admin_recommendation_statistics_paths` |
| UI-101 | 管理员 | 全平台报表导出 | CSV表头和格式正确 | 通过 | `test_admin_recommendation_statistics_paths` |
| UI-102 | 管理员 | 错误角色访问 | 顾客卖家均被平台页拒绝 | 通过 | `test_admin_recommendation_statistics_paths` |
| UI-103 | 管理员 | 管理员自身保护 | 危险操作不破坏管理入口 | 通过 | `test_admin_recommendation_statistics_paths` |
| UI-104 | 管理员 | 操作后刷新 | 页面与数据库状态一致 | 通过 | `test_admin_recommendation_statistics_paths` |

## 三、失败与错误

失败和错误场景为 0。

## 四、未执行与遗留风险

未执行和跳过场景为 0。

遗留范围：未覆盖 Edge、移动端真机、视觉像素差异、无障碍、并发和性能压测。

浏览器日志观察到部分种子图书封面和 favicon 路径返回 404；页面已使用封面回退元素，未造成空白页或未处理 JavaScript 异常。

## 五、关键截图

| 截图 | 文件 |
| --- | --- |
| admin-statistics-extended | [打开截图](screenshots/admin-statistics-extended.png) |
| customer-cart | [打开截图](screenshots/customer-cart.png) |
| customer-order-detail | [打开截图](screenshots/customer-order-detail.png) |
| customer-payment-success | [打开截图](screenshots/customer-payment-success.png) |
| customer-payment | [打开截图](screenshots/customer-payment.png) |
| customer-promotions | [打开截图](screenshots/customer-promotions.png) |
| login-customer | [打开截图](screenshots/login-customer.png) |
| login-platform_admin | [打开截图](screenshots/login-platform_admin.png) |
| login-seller | [打开截图](screenshots/login-seller.png) |
| platform-admin | [打开截图](screenshots/platform-admin.png) |
| public-book-detail | [打开截图](screenshots/public-book-detail.png) |
| seller-books | [打开截图](screenshots/seller-books.png) |
| seller-promotions-extended | [打开截图](screenshots/seller-promotions-extended.png) |

## 六、附件

| 文件 | 用途 |
| --- | --- |
| `report.html` | 可筛选的 pytest HTML 报告 |
| `junit.xml` | 机器可读测试结果 |
| `screenshots/` | 成功流程关键截图 |
| `failures/` | 失败截图、页面源码和控制台日志 |
| `case-matrix.md` | 104 个计划场景矩阵 |
| `summary.md` | 环境、提交和执行命令 |
