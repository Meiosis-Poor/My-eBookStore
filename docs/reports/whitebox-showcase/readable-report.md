# 网上书店白盒测试教师展示报告

> 本报告为提前执行并留存的测试结果，课程验收现场无需重新运行。

## 一、总体结论

| 项目 | 结果 |
| --- | --- |
| 测试结论 | 通过 |
| Git 提交 | `2885461` |
| Python | `3.13.0` |
| 测试数据库 | `My_eBookStore_Test` |
| 固定 seed | `20260716` |
| 用例总数 | 64 |
| 通过 / 失败 / 错误 / 跳过 | 64 / 0 / 0 / 0 |
| 执行耗时 | 14.79 秒 |
| 数据库隔离 | 通过（pytest 会话守卫未报告差异） |

## 二、覆盖率

| 指标 | 实际结果 | 展示目标 | 结论 |
| --- | ---: | ---: | --- |
| 纳入统计代码语句覆盖率 | 59.6% | ≥ 75% | 未达到，详见未覆盖清单 |
| 纳入统计代码分支覆盖率 | 46.9% | 记录实际值 | 已记录 |
| 已覆盖 / 总语句 | 983 / 1562 | - | - |
| 已覆盖 / 总分支 | 194 / 414 | - | - |

### 模块覆盖明细

| 模块 | 语句覆盖率 | 分支覆盖率 | 未覆盖行数 |
| --- | ---: | ---: | ---: |
| `backend/app/__init__.py` | 100.0% | 100.0% | 0 |
| `backend/app/config.py` | 94.1% | 50.0% | 1 |
| `backend/app/dao/__init__.py` | 100.0% | 100.0% | 0 |
| `backend/app/dao/address_dao.py` | 46.9% | 16.7% | 12 |
| `backend/app/dao/book_dao.py` | 54.8% | 50.0% | 40 |
| `backend/app/dao/cart_dao.py` | 60.6% | 25.0% | 10 |
| `backend/app/dao/order_dao.py` | 71.0% | 61.8% | 47 |
| `backend/app/dao/points_dao.py` | 25.0% | 0.0% | 7 |
| `backend/app/dao/promotion_dao.py` | 53.1% | 44.3% | 128 |
| `backend/app/dao/review_dao.py` | 100.0% | 100.0% | 0 |
| `backend/app/dao/stats_dao.py` | 16.4% | 0.0% | 41 |
| `backend/app/dao/store_dao.py` | 41.9% | 0.0% | 16 |
| `backend/app/dao/user_dao.py` | 50.8% | 25.0% | 20 |
| `backend/app/db.py` | 87.8% | 62.5% | 3 |
| `backend/app/embedding.py` | 57.8% | 30.0% | 24 |
| `backend/app/main.py` | 56.6% | 40.8% | 230 |
| `backend/app/response.py` | 100.0% | 100.0% | 0 |
| `backend/app/security.py` | 100.0% | 100.0% | 0 |

## 三、关键条件矩阵

| 判定 | 条件组合 | 预期路径 | 覆盖方式 |
| --- | --- | --- | --- |
| 当前用户认证 | 无凭证 / 非法Token / 用户不存在 / 禁用 / 正常 | 401 / 401 / 401 / 403 / 返回用户 | 直接单元测试 |
| 角色权限 | 角色属于允许集合 / 不属于 | 返回用户 / 403 | 直接单元测试 |
| 支付状态 | 不存在 / 已支付完成 / 非待支付 / 待支付 | 拒绝 / 幂等 / 拒绝 / 继续 | Mock DAO |
| 支付库存 | 无明细 / stock < quantity / 库存足 | 拒绝 / 拒绝 / 调用支付过程 | Mock DAO |
| 评价资格 | 未购买 / 未支付 / 已评价 / 合法 | 拒绝 / 拒绝 / 拒绝 / 写入 | Mock DAO |
| 事务 | 正常退出 / 抛出异常 | commit / rollback，均 close | 直接单元测试 |

## 四、逐条测试用例

| 编号 | 类别 | pytest 用例 | 验证内容 | 状态 | 耗时（秒） |
| ---: | --- | --- | --- | --- | ---: |
| 1 | 白盒单元/Mock | `test_order_sequence_success_and_failure` | 执行该用例定义的白盒路径和状态断言 | 通过 | 0.107 |
| 2 | 白盒单元/Mock | `test_order_procedure_error_known_and_fallback_paths` | 执行该用例定义的白盒路径和状态断言 | 通过 | 0.001 |
| 3 | 白盒单元/Mock | `test_pay_order_not_found_invalid_and_idempotent_paths` | 订单不存在、状态非法和重复支付幂等路径 | 通过 | 0.003 |
| 4 | 白盒单元/Mock | `test_pay_empty_items_stock_shortage_and_procedure_failure` | 空明细、库存不足和过程失败路径 | 通过 | 0.003 |
| 5 | 白盒单元/Mock | `test_pay_database_error_is_translated` | 支付数据库异常转换路径 | 通过 | 0.002 |
| 6 | 白盒单元/Mock | `test_review_rating_false_paths[0]` | 评分0和6拒绝路径 | 通过 | 0.001 |
| 7 | 白盒单元/Mock | `test_review_rating_false_paths[6]` | 评分0和6拒绝路径 | 通过 | 0.001 |
| 8 | 白盒单元/Mock | `test_review_purchase_payment_duplicate_and_success_paths` | 未购买、未支付、重复和成功评价路径 | 通过 | 0.002 |
| 9 | 白盒单元/Mock | `test_reward_type_and_procedure_error_paths` | 奖励类型和过程异常转换路径 | 通过 | 0.001 |
| 10 | 白盒单元/Mock | `test_page_slice_paths[1-2-expected0]` | 分页首、中、末页以及越界路径 | 通过 | 0.001 |
| 11 | 白盒单元/Mock | `test_page_slice_paths[2-2-expected1]` | 分页首、中、末页以及越界路径 | 通过 | 0.001 |
| 12 | 白盒单元/Mock | `test_page_slice_paths[3-2-expected2]` | 分页首、中、末页以及越界路径 | 通过 | 0.001 |
| 13 | 白盒单元/Mock | `test_page_slice_paths[9-2-expected3]` | 分页首、中、末页以及越界路径 | 通过 | 0.001 |
| 14 | 白盒单元/Mock | `test_page_slice_paths[0-2-expected4]` | 分页首、中、末页以及越界路径 | 通过 | 0.001 |
| 15 | 白盒单元/Mock | `test_page_slice_paths[-1-2-expected5]` | 分页首、中、末页以及越界路径 | 通过 | 0.001 |
| 16 | 白盒单元/Mock | `test_payload_int_valid_paths[payload0-None-7]` | 整数、数字字符串和默认值路径 | 通过 | 0.001 |
| 17 | 白盒单元/Mock | `test_payload_int_valid_paths[payload1-None--8]` | 整数、数字字符串和默认值路径 | 通过 | 0.001 |
| 18 | 白盒单元/Mock | `test_payload_int_valid_paths[payload2-3-3]` | 整数、数字字符串和默认值路径 | 通过 | 0.001 |
| 19 | 白盒单元/Mock | `test_payload_int_invalid_paths[None]` | 缺失、布尔及非法类型拒绝路径 | 通过 | 0.001 |
| 20 | 白盒单元/Mock | `test_payload_int_invalid_paths[True]` | 缺失、布尔及非法类型拒绝路径 | 通过 | 0.001 |
| 21 | 白盒单元/Mock | `test_payload_int_invalid_paths[False]` | 缺失、布尔及非法类型拒绝路径 | 通过 | 0.001 |
| 22 | 白盒单元/Mock | `test_payload_int_invalid_paths[1.2]` | 缺失、布尔及非法类型拒绝路径 | 通过 | 0.001 |
| 23 | 白盒单元/Mock | `test_payload_int_invalid_paths[abc]` | 缺失、布尔及非法类型拒绝路径 | 通过 | 0.001 |
| 24 | 白盒单元/Mock | `test_payload_int_invalid_paths[value5]` | 缺失、布尔及非法类型拒绝路径 | 通过 | 0.001 |
| 25 | 白盒单元/Mock | `test_payload_int_invalid_paths[value6]` | 缺失、布尔及非法类型拒绝路径 | 通过 | 0.001 |
| 26 | 白盒单元/Mock | `test_address_required_fields_true_and_false_paths` | 地址字段完整与分别缺失路径 | 通过 | 0.001 |
| 27 | 白盒单元/Mock | `test_normalize_book_all_default_and_conversion_paths` | 图书默认值和类型转换路径 | 通过 | 0.001 |
| 28 | 白盒单元/Mock | `test_response_envelope_and_exception_handler_paths` | 成功、业务异常和普通异常响应路径 | 通过 | 0.002 |
| 29 | 白盒单元/Mock | `test_database_row_conversion_and_result_set_paths` | 空行、多行、Decimal和结果集路径 | 通过 | 0.003 |
| 30 | 白盒单元/Mock | `test_get_conn_commit_rollback_and_close_paths` | 事务提交、异常回滚和连接关闭路径 | 通过 | 0.002 |
| 31 | 白盒单元/Mock | `test_payment_method_mapping_paths[alipay-\u652f\u4ed8\u5b9d]` | 支付方式映射和默认路径 | 通过 | 0.002 |
| 32 | 白盒单元/Mock | `test_payment_method_mapping_paths[wechat-\u5fae\u4fe1\u652f\u4ed8]` | 支付方式映射和默认路径 | 通过 | 0.001 |
| 33 | 白盒单元/Mock | `test_payment_method_mapping_paths[card-\u94f6\u884c\u5361]` | 支付方式映射和默认路径 | 通过 | 0.001 |
| 34 | 白盒单元/Mock | `test_payment_method_mapping_paths[cash-cash]` | 支付方式映射和默认路径 | 通过 | 0.001 |
| 35 | 白盒单元/Mock | `test_payment_method_mapping_paths[None-\u652f\u4ed8\u5b9d]` | 支付方式映射和默认路径 | 通过 | 0.002 |
| 36 | 白盒单元/Mock | `test_coupon_type_condition_paths[store-None-\u5e97\u94fa\u5238]` | 平台券与店铺券条件路径 | 通过 | 0.001 |
| 37 | 白盒单元/Mock | `test_coupon_type_condition_paths[None-3-\u5e97\u94fa\u5238]` | 平台券与店铺券条件路径 | 通过 | 0.002 |
| 38 | 白盒单元/Mock | `test_coupon_type_condition_paths[platform-None-\u5e73\u53f0\u5238]` | 平台券与店铺券条件路径 | 通过 | 0.001 |
| 39 | 白盒单元/Mock | `test_statistics_range_mapping_paths[7d-7]` | 统计日期范围映射和回退路径 | 通过 | 0.001 |
| 40 | 白盒单元/Mock | `test_statistics_range_mapping_paths[30d-30]` | 统计日期范围映射和回退路径 | 通过 | 0.001 |
| 41 | 白盒单元/Mock | `test_statistics_range_mapping_paths[90d-90]` | 统计日期范围映射和回退路径 | 通过 | 0.002 |
| 42 | 白盒单元/Mock | `test_statistics_range_mapping_paths[bad-7]` | 统计日期范围映射和回退路径 | 通过 | 0.001 |
| 43 | 白盒单元/Mock | `test_statistics_range_mapping_paths[None-7]` | 统计日期范围映射和回退路径 | 通过 | 0.001 |
| 44 | 白盒单元/Mock | `test_reward_amount_and_threshold_valid_invalid_paths` | 奖励金额、门槛有效和无效路径 | 通过 | 0.002 |
| 45 | 白盒单元/Mock | `test_current_user_missing_invalid_and_unknown_paths` | 缺失、伪造Token和用户不存在路径 | 通过 | 0.001 |
| 46 | 白盒单元/Mock | `test_current_user_banned_and_success_paths` | 禁用用户与合法认证路径 | 通过 | 0.001 |
| 47 | 白盒单元/Mock | `test_optional_user_and_role_condition_paths` | 可选认证和角色允许/拒绝路径 | 通过 | 0.002 |
| 48 | 白盒单元/Mock | `test_public_user_optional_store_and_default_paths` | 用户默认字段与卖家店铺字段路径 | 通过 | 0.002 |
| 49 | 真实数据库回归 | `test_embedding_fallback_is_deterministic` | 执行该用例定义的白盒路径和状态断言 | 通过 | 0.001 |
| 50 | 真实数据库回归 | `test_cosine_distance_identity_is_zero` | 执行该用例定义的白盒路径和状态断言 | 通过 | 0.002 |
| 51 | 真实数据库回归 | `test_title_token_coverage_normalizes_and_deduplicates_tokens` | 执行该用例定义的白盒路径和状态断言 | 通过 | 0.001 |
| 52 | 真实数据库回归 | `test_title_search_places_coverage_matches_before_embedding_fallback` | 执行该用例定义的白盒路径和状态断言 | 通过 | 0.001 |
| 53 | 真实数据库回归 | `test_title_search_compares_match_count_before_coverage` | 执行该用例定义的白盒路径和状态断言 | 通过 | 0.001 |
| 54 | 真实数据库回归 | `test_checkout_payment_is_idempotent_and_persists_consistent_state` | 执行该用例定义的白盒路径和状态断言 | 通过 | 1.808 |
| 55 | 真实数据库回归 | `test_insufficient_stock_does_not_create_an_order_or_change_inventory` | 执行该用例定义的白盒路径和状态断言 | 通过 | 1.212 |
| 56 | 真实数据库回归 | `test_cancel_and_approved_refund_restore_reserved_or_sold_inventory` | 执行该用例定义的白盒路径和状态断言 | 通过 | 1.392 |
| 57 | 真实数据库回归 | `test_authentication_and_role_boundaries` | 执行该用例定义的白盒路径和状态断言 | 通过 | 0.947 |
| 58 | 真实数据库回归 | `test_search_input_is_treated_as_data[title-False]` | 执行该用例定义的白盒路径和状态断言 | 通过 | 0.051 |
| 59 | 真实数据库回归 | `test_search_input_is_treated_as_data[author-True]` | 执行该用例定义的白盒路径和状态断言 | 通过 | 0.047 |
| 60 | 真实数据库回归 | `test_search_input_is_treated_as_data[isbn-True]` | 执行该用例定义的白盒路径和状态断言 | 通过 | 0.053 |
| 61 | 真实数据库回归 | `test_database_objects_and_blacklist_trigger` | 执行该用例定义的白盒路径和状态断言 | 通过 | 0.561 |
| 62 | 真实数据库回归 | `test_checkin_level_reward_and_coupon_expiration_procedures` | 执行该用例定义的白盒路径和状态断言 | 通过 | 0.684 |
| 63 | 真实数据库回归 | `test_admin_reward_coupon_configuration_and_redemption_delivery` | 执行该用例定义的白盒路径和状态断言 | 通过 | 1.849 |
| 64 | 真实数据库回归 | `test_refund_request_store_scope_and_approval_procedure` | 执行该用例定义的白盒路径和状态断言 | 通过 | 2.143 |

## 五、失败与错误用例

本次执行失败 0 个、错误 0 个。

## 六、未覆盖代码与遗留风险

| 模块 | 未覆盖行 | 说明 |
| --- | --- | --- |
| `backend/app/main.py` | 38, 58, 62, 63, 64, 65, 66, 67, 70, 71, 72, 73, 74, 121, 122, 123, 125, 132 等230行 | 未覆盖不等于测试失败；主要为未纳入本次短时展示的管理和查询路径 |
| `backend/app/dao/promotion_dao.py` | 86, 141, 154, 184, 202, 215, 227, 239, 240, 241, 242, 257, 258, 270, 271, 272, 284, 285 等128行 | 未覆盖不等于测试失败；主要为未纳入本次短时展示的管理和查询路径 |
| `backend/app/dao/order_dao.py` | 55, 77, 80, 82, 111, 117, 133, 134, 135, 136, 137, 140, 141, 142, 163, 164, 166, 170 等47行 | 未覆盖不等于测试失败；主要为未纳入本次短时展示的管理和查询路径 |
| `backend/app/dao/stats_dao.py` | 15, 16, 17, 18, 31, 44, 53, 61, 79, 80, 90, 91, 92, 111, 112, 113, 114, 128 等41行 | 未覆盖不等于测试失败；主要为未纳入本次短时展示的管理和查询路径 |
| `backend/app/dao/book_dao.py` | 71, 72, 74, 75, 77, 103, 104, 120, 121, 125, 129, 130, 131, 132, 133, 148, 149, 150 等40行 | 未覆盖不等于测试失败；主要为未纳入本次短时展示的管理和查询路径 |
| `backend/app/embedding.py` | 28, 34, 35, 36, 37, 38, 42, 43, 44, 45, 47, 48, 49, 50, 51, 52, 53, 54 等24行 | 未覆盖不等于测试失败；主要为未纳入本次短时展示的管理和查询路径 |
| `backend/app/dao/user_dao.py` | 38, 73, 75, 110, 111, 117, 118, 126, 127, 128, 129, 130, 131, 133, 134, 135, 136, 156 等20行 | 未覆盖不等于测试失败；主要为未纳入本次短时展示的管理和查询路径 |
| `backend/app/dao/store_dao.py` | 11, 12, 29, 30, 39, 40, 60, 61, 65, 66, 71, 72, 78, 82, 86, 87 | 未覆盖不等于测试失败；主要为未纳入本次短时展示的管理和查询路径 |
| `backend/app/dao/address_dao.py` | 11, 12, 25, 26, 27, 61, 62, 63, 64, 65, 84, 85 | 未覆盖不等于测试失败；主要为未纳入本次短时展示的管理和查询路径 |
| `backend/app/dao/cart_dao.py` | 49, 64, 65, 74, 75, 83, 84, 85, 86, 87 | 未覆盖不等于测试失败；主要为未纳入本次短时展示的管理和查询路径 |
| `backend/app/dao/points_dao.py` | 9, 10, 17, 28, 32, 33, 34 | 未覆盖不等于测试失败；主要为未纳入本次短时展示的管理和查询路径 |
| `backend/app/db.py` | 53, 59, 60 | 未覆盖不等于测试失败；主要为未纳入本次短时展示的管理和查询路径 |
| `backend/app/config.py` | 45 | 未覆盖不等于测试失败；主要为未纳入本次短时展示的管理和查询路径 |

## 七、附件

| 文件 | 用途 |
| --- | --- |
| `coverage-html/index.html` | 浏览源码逐行覆盖情况 |
| `coverage.json` | 机器可读覆盖数据 |
| `junit.xml` | 逐条 pytest 执行结果 |
| `condition-matrix.md` | 关键复合条件覆盖矩阵 |
| `summary.md` | 执行命令和基础环境 |
