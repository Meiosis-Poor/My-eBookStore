-- ============================================================
-- My-eBookStore 网上书店系统 — 存储过程
-- 用法：建表 + 种子数据后，在 SSMS 中执行此文件
-- ============================================================

USE My_eBookStore;
GO

-- ============================================================
-- 0. sp_GetNextSeq  获取当日序列号（内部辅助过程）
-- 参数：
--   @seq_type   ORD / PAY / REF
--   @new_no     输出：下一条编号（格式：日期 + 3位流水号，如 20260709001）
-- ============================================================
IF OBJECT_ID('sp_GetNextSeq', 'P') IS NOT NULL DROP PROCEDURE sp_GetNextSeq;
GO
CREATE PROCEDURE sp_GetNextSeq
    @seq_type   NVARCHAR(5),
    @new_no     NVARCHAR(50) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @today DATE = CAST(SYSDATETIME() AS DATE);

    -- 更新或插入今日序号（UPDLOCK + HOLDLOCK 确保同一类型每天只有一个事务拿到当前序号）
    UPDATE daily_sequences WITH (UPDLOCK, HOLDLOCK)
    SET current_no = current_no + 1
    WHERE seq_date = @today AND seq_type = @seq_type;

    IF @@ROWCOUNT = 0
    BEGIN
        INSERT INTO daily_sequences (seq_date, seq_type, current_no)
        VALUES (@today, @seq_type, 1);
    END

    -- 读取最新序号
    DECLARE @seq INT;
    SELECT @seq = current_no
    FROM daily_sequences WITH (UPDLOCK, HOLDLOCK)
    WHERE seq_date = @today AND seq_type = @seq_type;

    -- 组装：前缀 + 日期 + 3位序号
    SET @new_no = @seq_type + FORMAT(@today, 'yyyyMMdd') + RIGHT('000' + CAST(@seq AS NVARCHAR), 3);
END;
GO

PRINT N'sp_GetNextSeq 创建完成';
GO

-- ============================================================
-- 1. sp_CreateOrder  下单
-- ============================================================
-- 参数说明：
--   @user_id          下单用户 ID
--   @items_json       商品列表 JSON：[{"bid":book_item_id,"qty":quantity}, ...]
--   @address_id       收货地址 ID
--   @coupon_id        代金券 ID（可选，不用传 NULL）
--   @success          输出：1=成功 0=失败
--   @order_id         输出：新订单 ID
--   @order_no         输出：新订单号
-- ============================================================
IF OBJECT_ID('sp_CreateOrder', 'P') IS NOT NULL DROP PROCEDURE sp_CreateOrder;
GO
CREATE PROCEDURE sp_CreateOrder
    @user_id          INT,
    @items_json       NVARCHAR(MAX),         -- [{"bid":1,"qty":2},{"bid":3,"qty":1}]
    @address_id       INT,
    @coupon_id        INT           = NULL,
    @success          BIT           OUTPUT,
    @order_id         INT           OUTPUT,
    @order_no         NVARCHAR(50)  OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    BEGIN TRANSACTION
    BEGIN TRY
        -- ===== 步骤 0：解析 JSON → 临时表 =====
        DECLARE @items TABLE (
            book_item_id INT NOT NULL,
            quantity     INT NOT NULL
        );
        INSERT INTO @items (book_item_id, quantity)
        SELECT bid, qty
        FROM OPENJSON(@items_json)
        WITH (bid INT '$.bid', qty INT '$.qty');

        -- ===== 步骤 1：逐行验库存（行级排他锁，防超卖） =====
        IF EXISTS (
            SELECT 1 FROM @items it
            JOIN book_items bi WITH (ROWLOCK, XLOCK) ON bi.book_item_id = it.book_item_id
            WHERE (bi.stock - bi.locked_stock) < it.quantity
               OR bi.status != N'在售'
        )
        BEGIN
            RAISERROR(N'部分商品库存不足或已下架', 16, 1);
        END

        -- ===== 步骤 2：算总金额 =====
        DECLARE @total DECIMAL(10,2);
        SELECT @total = SUM(it.quantity * bi.price)
        FROM @items it
        JOIN book_items bi ON bi.book_item_id = it.book_item_id;

        -- ===== 步骤 3：算优惠金额（代金券）=====
        DECLARE @discount DECIMAL(10,2) = 0;
        IF @coupon_id IS NOT NULL
        BEGIN
            SELECT @discount = c.amount
            FROM user_coupons uc
            JOIN coupons c ON uc.coupon_id = c.coupon_id
            WHERE uc.user_coupon_id = @coupon_id              -- 用 user_coupon_id 不是 coupon_id
              AND uc.user_id = @user_id
              AND uc.status = N'未使用'
              AND c.min_amount <= @total
              AND GETDATE() BETWEEN c.valid_start AND c.valid_end;

            IF @discount IS NULL SET @discount = 0;
        END

        DECLARE @actual DECIMAL(10,2) = @total - @discount;
        IF @actual < 0 SET @actual = 0;

        -- ===== 步骤 4：取收货地址快照 =====
        DECLARE @recv_name  NVARCHAR(50);
        DECLARE @recv_phone VARCHAR(20);
        DECLARE @recv_addr  NVARCHAR(200);

        SELECT @recv_name = receiver_name,
               @recv_phone = phone,
               @recv_addr  = province + city + district + detail
        FROM shipping_addresses
        WHERE address_id = @address_id AND user_id = @user_id;

        IF @recv_name IS NULL
        BEGIN
            RAISERROR(N'收货地址不存在', 16, 1);
        END

        -- ===== 步骤 5：生成订单号 + 建订单 =====
        EXEC sp_GetNextSeq N'ORD', @order_no OUTPUT;

        INSERT INTO orders
            (user_id, order_no, total_amount, discount_amount, actual_amount,
             order_status, payment_status,
             receiver_name, receiver_phone, receiver_addr)
        VALUES
            (@user_id, @order_no, @total, @discount, @actual,
             N'待支付', N'未支付',
             @recv_name, @recv_phone, @recv_addr);

        SET @order_id = SCOPE_IDENTITY();

        -- ===== 步骤 6：建订单明细（快照当时单价）+ 锁定库存 =====
        INSERT INTO order_items (order_id, book_item_id, quantity, unit_price, subtotal)
        SELECT @order_id, it.book_item_id, it.quantity, bi.price, it.quantity * bi.price
        FROM @items it
        JOIN book_items bi ON bi.book_item_id = it.book_item_id;

        UPDATE book_items
        SET locked_stock = locked_stock + it.quantity
        FROM book_items bi
        JOIN @items it ON bi.book_item_id = it.book_item_id;

        -- ===== 步骤 7：核销代金券 =====
        IF @coupon_id IS NOT NULL AND @discount > 0
        BEGIN
            UPDATE user_coupons
            SET status = N'已使用', used_time = SYSDATETIME(), order_id = @order_id
            WHERE user_coupon_id = @coupon_id;
        END

        -- ===== 步骤 8：清空购物车中对应商品 =====
        DELETE ci
        FROM cart_items ci
        JOIN @items it ON ci.book_item_id = it.book_item_id
        WHERE ci.user_id = @user_id;

        COMMIT TRANSACTION;
        SET @success = 1;
    END TRY
    BEGIN CATCH
        ROLLBACK TRANSACTION;
        SET @success = 0;
        DECLARE @msg NVARCHAR(4000) = ERROR_MESSAGE();
        RAISERROR(@msg, 16, 1);
    END CATCH
END;
GO

PRINT N'sp_CreateOrder 创建完成';
GO

-- ============================================================
-- 2. sp_PayOrder  支付
-- ============================================================
IF OBJECT_ID('sp_PayOrder', 'P') IS NOT NULL DROP PROCEDURE sp_PayOrder;
GO
CREATE PROCEDURE sp_PayOrder
    @order_id         INT,
    @payment_method   NVARCHAR(20),        -- 微信支付 / 支付宝
    @success          BIT           OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    BEGIN TRANSACTION
    BEGIN TRY
        DECLARE @user_id       INT;
        DECLARE @actual_amount DECIMAL(10,2);
        DECLARE @payment_no    NVARCHAR(50);

        -- 查订单（排他锁）
        SELECT @user_id       = user_id,
               @actual_amount = actual_amount
        FROM orders WITH (ROWLOCK, XLOCK)
        WHERE order_id   = @order_id
          AND order_status = N'待支付';

        IF @user_id IS NULL
        BEGIN
            RAISERROR(N'订单状态异常，无法支付', 16, 1);
        END

        EXEC sp_GetNextSeq N'PAY', @payment_no OUTPUT;

        -- ① 更新订单
        UPDATE orders
        SET order_status   = N'已完成',
            payment_status = N'已支付',
            paid_time      = SYSDATETIME()
        WHERE order_id = @order_id;

        -- ② 写支付记录
        INSERT INTO payment_records
            (order_id, user_id, payment_no, amount, payment_method, payment_status, paid_time)
        VALUES
            (@order_id, @user_id, @payment_no, @actual_amount, @payment_method, N'已支付', SYSDATETIME());

        -- ③ 释放锁定 + 扣真实库存 + 加销量
        UPDATE book_items
        SET stock        = stock - oi.quantity,
            locked_stock = locked_stock - oi.quantity,
            sales_count  = sales_count + oi.quantity
        FROM book_items bi
        JOIN order_items oi ON bi.book_item_id = oi.book_item_id
        WHERE oi.order_id = @order_id;

        -- ④ 加积分（1 元 = 1 分）
        DECLARE @points INT = FLOOR(@actual_amount);
        INSERT INTO points_records
            (user_id, points_change, reason, related_id)
        VALUES
            (@user_id, @points, N'购买', @order_id);

        UPDATE ordinary_users
        SET total_points     = total_points     + @points,
            available_points = available_points + @points
        WHERE user_id = @user_id;

        COMMIT TRANSACTION;
        SET @success = 1;
    END TRY
    BEGIN CATCH
        ROLLBACK TRANSACTION;
        SET @success = 0;
        DECLARE @msg2 NVARCHAR(4000) = ERROR_MESSAGE();
        RAISERROR(@msg2, 16, 1);
    END CATCH
END;
GO

PRINT N'sp_PayOrder 创建完成';
GO

-- ============================================================
-- 3. sp_RefundOrder  退款
-- ============================================================
IF OBJECT_ID('sp_RefundOrder', 'P') IS NOT NULL DROP PROCEDURE sp_RefundOrder;
GO
CREATE PROCEDURE sp_RefundOrder
    @order_id         INT,
    @refund_reason    NVARCHAR(500),
    @success          BIT           OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    BEGIN TRANSACTION
    BEGIN TRY
        DECLARE @user_id       INT;
        DECLARE @actual_amount DECIMAL(10,2);
        DECLARE @payment_id    INT;

        SELECT @user_id       = user_id,
               @actual_amount = actual_amount,
               @payment_id    = p.payment_id
        FROM orders o
        LEFT JOIN payment_records p ON p.order_id = o.order_id
        WHERE o.order_id = @order_id
          AND o.order_status = N'已完成';

        IF @user_id IS NULL
        BEGIN
            RAISERROR(N'订单状态不允许退款', 16, 1);
        END

        -- ① 更新订单
        UPDATE orders
        SET order_status   = N'已退款',
            payment_status = N'已退款'
        WHERE order_id = @order_id;

        -- ② 生成退款流水号 + 写退款记录
        DECLARE @refund_no NVARCHAR(50);
        EXEC sp_GetNextSeq N'REF', @refund_no OUTPUT;

        INSERT INTO refund_records
            (order_id, user_id, payment_id, refund_no, refund_amount,
             refund_reason, refund_status, refund_time)
        VALUES
            (@order_id, @user_id, @payment_id, @refund_no, @actual_amount,
             @refund_reason, N'已退款', SYSDATETIME());

        -- ③ 回滚库存
        UPDATE book_items
        SET stock       = stock + oi.quantity,
            sales_count = sales_count - oi.quantity
        FROM book_items bi
        JOIN order_items oi ON bi.book_item_id = oi.book_item_id
        WHERE oi.order_id = @order_id;

        COMMIT TRANSACTION;
        SET @success = 1;
    END TRY
    BEGIN CATCH
        ROLLBACK TRANSACTION;
        SET @success = 0;
        DECLARE @msg3 NVARCHAR(4000) = ERROR_MESSAGE();
        RAISERROR(@msg3, 16, 1);
    END CATCH
END;
GO

PRINT N'sp_RefundOrder 创建完成';
GO

-- ============================================================
-- 4. sp_CheckIn  每日签到
-- ============================================================
IF OBJECT_ID('sp_CheckIn', 'P') IS NOT NULL DROP PROCEDURE sp_CheckIn;
GO
CREATE PROCEDURE sp_CheckIn
    @user_id          INT,
    @success          BIT           OUTPUT,
    @continuous_days  INT           OUTPUT,   -- 当前连续天数
    @reward_points    INT           OUTPUT,   -- 本次奖励积分
    @got_coupon       BIT           OUTPUT    -- 是否获得代金券
AS
BEGIN
    SET NOCOUNT ON;

    BEGIN TRANSACTION
    BEGIN TRY
        -- ① 查今天是否已签
        IF EXISTS (
            SELECT 1 FROM checkin_record
            WHERE user_id = @user_id AND checkin_date = CAST(SYSDATETIME() AS DATE)
        )
        BEGIN
            RAISERROR(N'今日已签到，请勿重复操作', 16, 1);
        END

        -- ② 查昨天签到 → 算连续天数
        DECLARE @yesterday DATE = DATEADD(DAY, -1, CAST(SYSDATETIME() AS DATE));
        DECLARE @last_cont INT = 0;

        SELECT TOP 1 @last_cont = continuous_checkin_days
        FROM checkin_record
        WHERE user_id = @user_id AND checkin_date = @yesterday
        ORDER BY checkin_id DESC;

        IF @@ROWCOUNT > 0
            SET @last_cont = @last_cont + 1;
        ELSE
            SET @last_cont = 1;

        -- ③ 算积分奖励（每周循环：第1天5 第2天5 第3天10 第4天10 第5天10 第6天15 第7天30）
        SET @reward_points = CASE (@last_cont - 1) % 7
            WHEN 0 THEN 5
            WHEN 1 THEN 5
            WHEN 2 THEN 10
            WHEN 3 THEN 10
            WHEN 4 THEN 10
            WHEN 5 THEN 15
            WHEN 6 THEN 30
        END;

        -- ④ 写签到记录
        DECLARE @act_id INT = (SELECT activity_id FROM promotion_activities
                               WHERE activity_name = N'每日签到' AND status = N'进行中');

        INSERT INTO checkin_record
            (user_id, activity_id, checkin_date, continuous_checkin_days, reward_points)
        VALUES
            (@user_id, @act_id, CAST(SYSDATETIME() AS DATE), @last_cont, @reward_points);

        -- ⑤ 更新用户表
        INSERT INTO points_records (user_id, points_change, reason, related_id)
        VALUES (@user_id, @reward_points, N'签到', SCOPE_IDENTITY());

        UPDATE ordinary_users
        SET total_points           = total_points           + @reward_points,
            available_points       = available_points       + @reward_points,
            continuous_checkin_days = @last_cont
        WHERE user_id = @user_id;

        -- ⑥ 连续 7 天或 30 天 → 发放代金券
        SET @got_coupon = 0;
        IF @last_cont % 7 = 0
        BEGIN
            INSERT INTO user_coupons (user_id, coupon_id, status)
            SELECT @user_id, coupon_id, N'未使用'
            FROM coupons
            WHERE coupon_name = N'连续7天签到券' AND status = N'启用';
            SET @got_coupon = 1;
        END
        IF @last_cont % 30 = 0
        BEGIN
            INSERT INTO user_coupons (user_id, coupon_id, status)
            SELECT @user_id, coupon_id, N'未使用'
            FROM coupons
            WHERE coupon_name = N'连续30天签到券' AND status = N'启用';
            SET @got_coupon = 1;
        END

        COMMIT TRANSACTION;
        SET @success        = 1;
        SET @continuous_days = @last_cont;
    END TRY
    BEGIN CATCH
        ROLLBACK TRANSACTION;
        SET @success = 0;
        THROW;
    END CATCH
END;
GO

PRINT N'sp_CheckIn 创建完成';
GO

-- ============================================================
-- 5. sp_RedeemReward  积分兑换奖品
-- ============================================================
IF OBJECT_ID('sp_RedeemReward', 'P') IS NOT NULL DROP PROCEDURE sp_RedeemReward;
GO
CREATE PROCEDURE sp_RedeemReward
    @user_id          INT,
    @reward_id        INT,
    @success          BIT           OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    BEGIN TRANSACTION
    BEGIN TRY
        -- ① 查用户
        DECLARE @user_points INT;
        DECLARE @user_level  INT;

        SELECT @user_points = available_points,
               @user_level  = level
        FROM ordinary_users WITH (ROWLOCK, XLOCK)
        WHERE user_id = @user_id;

        -- ② 查奖品（排他锁）
        DECLARE @req_points INT;
        DECLARE @req_level  INT;
        DECLARE @stock      INT;

        SELECT @req_points = required_points,
               @req_level  = required_level,
               @stock      = stock
        FROM point_rewards WITH (ROWLOCK, XLOCK)
        WHERE reward_id = @reward_id AND status = N'启用';

        -- ③ 校验
        IF @user_points < @req_points
            RAISERROR(N'可用积分不足', 16, 1);
        IF @user_level < @req_level
            RAISERROR(N'会员等级不足', 16, 1);
        IF @stock <= 0
            RAISERROR(N'奖品已兑完', 16, 1);

        -- ④ 扣积分
        UPDATE ordinary_users
        SET available_points = available_points - @req_points
        WHERE user_id = @user_id;

        -- ⑤ 扣库存
        UPDATE point_rewards
        SET stock = stock - 1
        WHERE reward_id = @reward_id;

        -- ⑥ 写兑换记录
        INSERT INTO reward_redemptions
            (user_id, reward_id, used_points, redeemed_time)
        VALUES
            (@user_id, @reward_id, @req_points, SYSDATETIME());

        -- ⑦ 写积分流水
        INSERT INTO points_records
            (user_id, points_change, reason, related_id)
        VALUES
            (@user_id, -@req_points, N'兑换奖品', SCOPE_IDENTITY());

        COMMIT TRANSACTION;
        SET @success = 1;
    END TRY
    BEGIN CATCH
        ROLLBACK TRANSACTION;
        SET @success = 0;
        THROW;
    END CATCH
END;
GO

PRINT N'sp_RedeemReward 创建完成';
GO

-- ============================================================
-- 测试脚本（在 SSMS 中选中执行）
-- ============================================================
/*
-- 测试 1：下单
DECLARE @ok BIT, @oid INT, @ono NVARCHAR(50);
EXEC sp_CreateOrder
    @user_id    = (SELECT user_id FROM users WHERE user_name = N'buyer_zhou'),
    @items_json = N'[{"bid":1,"qty":1},{"bid":2,"qty":1}]',
    @address_id = 1,
    @coupon_id  = NULL,
    @success    = @ok OUTPUT,
    @order_id   = @oid OUTPUT,
    @order_no   = @ono OUTPUT;
SELECT @ok AS 下单成功, @oid AS 订单ID, @ono AS 订单号;

-- 测试 2：支付
DECLARE @ok2 BIT;
EXEC sp_PayOrder @order_id = @oid, @payment_method = N'微信支付', @success = @ok2 OUTPUT;
SELECT @ok2 AS 支付成功;

-- 测试 3：签到
DECLARE @ok3 BIT, @cd INT, @rp INT, @gc BIT;
EXEC sp_CheckIn @user_id = (SELECT user_id FROM users WHERE user_name = N'buyer_zhou'),
     @success = @ok3 OUTPUT, @continuous_days = @cd OUTPUT,
     @reward_points = @rp OUTPUT, @got_coupon = @gc OUTPUT;
SELECT @ok3 AS 签到成功, @cd AS 连续天数, @rp AS 奖励积分, @gc AS 获得代金券;
*/
