-- ============================================================
-- My-eBookStore 网上书店系统 — 触发器
-- 用法：建表 + 存过之后，在 SSMS 中执行此文件
-- 注意：如果 sp_PayOrder 已有积分逻辑，trg_AfterPayment 会重复加分
--       实际部署时二选一 —— 存过加分 or 触发器加分，不要两个都用
--       这里写出来供答辩展示
-- ============================================================

USE My_eBookStore;
GO

-- ============================================================
-- 1. trg_AfterPayment  支付成功后自动加积分 + 更新销量
-- 绑定表：payment_records
-- 触发时机：INSERT 之后
-- 逻辑：若插入的是"已支付"记录 → 给对应用户加积分
-- ============================================================
IF OBJECT_ID('trg_AfterPayment', 'TR') IS NOT NULL DROP TRIGGER trg_AfterPayment;
GO
CREATE TRIGGER trg_AfterPayment
ON payment_records
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;

    -- inserted 是系统自动生成的虚拟表，存本次 INSERT 的所有行
    -- 只处理"已支付"的记录
    IF NOT EXISTS (SELECT 1 FROM inserted WHERE payment_status = N'已支付')
        RETURN;   -- 不是支付 → 不触发，直接退出

    -- ① 扣真实库存 + 加销量（从 locked_stock 移到 sales_count）
    UPDATE book_items
    SET stock        = stock - oi.quantity,
        locked_stock = locked_stock - oi.quantity,
        sales_count  = sales_count + oi.quantity
    FROM book_items bi
    JOIN order_items oi ON bi.book_item_id = oi.book_item_id
    JOIN inserted i   ON oi.order_id = i.order_id        -- 只更新本次支付的订单
    WHERE i.payment_status = N'已支付';

    -- ② 加积分（1 元 = 1 分）
    INSERT INTO points_records (user_id, points_change, reason, related_id)
    SELECT i.user_id, FLOOR(i.amount), N'购买', i.order_id
    FROM inserted i
    WHERE i.payment_status = N'已支付';

    -- ③ 更新普通用户积分余额
    UPDATE ordinary_users
    SET total_points     = total_points     + FLOOR(i.amount),
        available_points = available_points + FLOOR(i.amount)
    FROM ordinary_users ou
    JOIN inserted i ON ou.user_id = i.user_id
    WHERE i.payment_status = N'已支付';

    PRINT N'[trg_AfterPayment] 支付后自动处理完成';
END;
GO

PRINT N'trg_AfterPayment 创建完成';
GO

-- ============================================================
-- 2. trg_AfterBlacklist  拉黑后自动检测 ≥10 家封禁
-- 绑定表：store_blacklists
-- 触发时机：INSERT 之后
-- 逻辑：统计被拉黑用户涉及多少家店 → ≥10 自动封禁
-- ============================================================
IF OBJECT_ID('trg_AfterBlacklist', 'TR') IS NOT NULL DROP TRIGGER trg_AfterBlacklist;
GO
CREATE TRIGGER trg_AfterBlacklist
ON store_blacklists
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;

    -- 对每条新插入的黑名单记录，检查对应用户是否达到封禁阈值
    DECLARE @uid INT;
    DECLARE @count INT;

    -- 游标遍历 inserted（因为可能一次 INSERT 多条）
    DECLARE cur CURSOR LOCAL FAST_FORWARD FOR
        SELECT DISTINCT user_id FROM inserted;

    OPEN cur;
    FETCH NEXT FROM cur INTO @uid;

    WHILE @@FETCH_STATUS = 0
    BEGIN
        -- 统计该用户被多少家不同的店铺拉黑
        SELECT @count = COUNT(DISTINCT store_id)
        FROM store_blacklists
        WHERE user_id = @uid;

        -- ≥10 家 → 自动平台封禁
        IF @count >= 10
        BEGIN
            UPDATE users
            SET status = N'封禁'
            WHERE user_id = @uid AND status = N'正常';

            PRINT N'[trg_AfterBlacklist] 用户 ' + CAST(@uid AS NVARCHAR) +
                  N' 被 ' + CAST(@count AS NVARCHAR) + N' 家店铺拉黑，已自动封禁';
        END

        FETCH NEXT FROM cur INTO @uid;
    END

    CLOSE cur;
    DEALLOCATE cur;
END;
GO

PRINT N'trg_AfterBlacklist 创建完成';
GO

-- ============================================================
-- 3. trg_AutoLevelUp  积分达到阈值自动升级（额外赠送）
-- 绑定表：ordinary_users
-- 触发时机：UPDATE 之后（积分字段变化时）
-- 升级规则：≥1000 → Lv2   ≥3000 → Lv3   ≥5000 → Lv4   ≥10000 → Lv5
-- ============================================================
IF OBJECT_ID('trg_AutoLevelUp', 'TR') IS NOT NULL DROP TRIGGER trg_AutoLevelUp;
GO
CREATE TRIGGER trg_AutoLevelUp
ON ordinary_users
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    -- 只在 total_points 字段变化时才触发
    IF NOT UPDATE(total_points)
        RETURN;

    UPDATE ordinary_users
    SET level = CASE
        WHEN i.total_points >= 10000 THEN 5
        WHEN i.total_points >= 5000  THEN 4
        WHEN i.total_points >= 3000  THEN 3
        WHEN i.total_points >= 1000  THEN 2
        ELSE level
    END
    FROM ordinary_users ou
    JOIN inserted i ON ou.user_id = i.user_id
    WHERE i.total_points >= 1000
      AND ou.level !=                                            -- 只更新确实要升级的
          CASE
              WHEN i.total_points >= 10000 THEN 5
              WHEN i.total_points >= 5000  THEN 4
              WHEN i.total_points >= 3000  THEN 3
              WHEN i.total_points >= 1000  THEN 2
              ELSE ou.level
          END;
END;
GO

PRINT N'trg_AutoLevelUp 创建完成';
GO

-- ============================================================
-- 测试触发器
-- ============================================================
/*
-- 测试 1：支付触发器 — 随便查一条待支付订单，手动模拟支付
SELECT * FROM orders WHERE order_status = N'待支付';

INSERT INTO payment_records (order_id, user_id, payment_no, amount, payment_method, payment_status, paid_time)
SELECT order_id, user_id, N'PAYTEST' + FORMAT(SYSDATETIME(),'HHmmssfff'),
       actual_amount, N'测试', N'已支付', SYSDATETIME()
FROM orders WHERE order_no = N'ORD202607010001';

-- 验证：库存是否减少了、积分是否增加了
SELECT book_item_id, stock, locked_stock, sales_count FROM book_items WHERE book_item_id IN (
    SELECT book_item_id FROM order_items WHERE order_id =
        (SELECT order_id FROM orders WHERE order_no = N'ORD202607010001')
);

SELECT user_id, total_points, available_points FROM ordinary_users
WHERE user_id = (SELECT user_id FROM orders WHERE order_no = N'ORD202607010001');

-- 测试 2：黑名单触发器 — 给某个用户插入 10 条拉黑记录
DECLARE @i INT = 1;
WHILE @i <= 10
BEGIN
    INSERT INTO store_blacklists (store_id, user_id, reason) VALUES (1, (SELECT user_id FROM users WHERE user_name = N'buyer_lin'), N'测试自动封禁');
    SET @i = @i + 1;
END

-- 验证：该用户是否被自动封禁
SELECT user_name, status FROM users WHERE user_name = N'buyer_lin';
*/
