CREATE OR ALTER PROCEDURE sp_GetNextSeq
    @seq_type NVARCHAR(5),
    @new_no NVARCHAR(50) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @today DATE = CAST(SYSDATETIME() AS DATE);
    UPDATE daily_sequences WITH (UPDLOCK, HOLDLOCK)
    SET current_no = current_no + 1
    WHERE seq_date = @today AND seq_type = @seq_type;
    IF @@ROWCOUNT = 0
        INSERT INTO daily_sequences(seq_date, seq_type, current_no) VALUES (@today, @seq_type, 1);
    DECLARE @seq INT;
    SELECT @seq = current_no FROM daily_sequences WITH (UPDLOCK, HOLDLOCK)
    WHERE seq_date = @today AND seq_type = @seq_type;
    SET @new_no = @seq_type + FORMAT(@today, 'yyyyMMdd')
        + RIGHT('000000' + CAST(@seq AS NVARCHAR), 6);
END;
GO

CREATE OR ALTER PROCEDURE sp_CreateOrder
    @user_id INT,
    @items_json NVARCHAR(MAX),
    @address_id INT,
    @coupon_id INT = NULL,
    @success BIT OUTPUT,
    @order_id INT OUTPUT,
    @order_no NVARCHAR(50) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    SET @success = 0;
    BEGIN TRANSACTION;
    BEGIN TRY
        DECLARE @items TABLE(book_item_id INT NOT NULL PRIMARY KEY, quantity INT NOT NULL);
        INSERT INTO @items(book_item_id, quantity)
        SELECT bid, qty FROM OPENJSON(@items_json)
        WITH (bid INT '$.bid', qty INT '$.qty');

        IF NOT EXISTS(SELECT 1 FROM @items) OR EXISTS(SELECT 1 FROM @items WHERE quantity <= 0)
            RAISERROR(N'订单商品为空或数量不正确', 16, 1);
        IF EXISTS(
            SELECT 1 FROM @items it
            LEFT JOIN book_items bi WITH (ROWLOCK, XLOCK) ON bi.book_item_id = it.book_item_id
            WHERE bi.book_item_id IS NULL OR (bi.stock - bi.locked_stock) < it.quantity OR bi.status <> N'在售'
        )
            RAISERROR(N'部分书目库存不足或已下架', 16, 1);

        DECLARE @total DECIMAL(10, 2);
        SELECT @total = SUM(it.quantity * bi.price)
        FROM @items it JOIN book_items bi ON bi.book_item_id = it.book_item_id;

        DECLARE @discount DECIMAL(10, 2) = 0;
        IF @coupon_id IS NOT NULL
        BEGIN
            SET @discount = NULL;
            SELECT @discount = c.amount
            FROM user_coupons uc WITH (UPDLOCK, HOLDLOCK)
            JOIN coupons c ON c.coupon_id = uc.coupon_id
            WHERE uc.user_coupon_id = @coupon_id AND uc.user_id = @user_id
              AND uc.status = N'未使用' AND c.status = N'启用'
              AND c.min_amount <= @total AND SYSDATETIME() BETWEEN c.valid_start AND c.valid_end;
            IF @discount IS NULL RAISERROR(N'代金券不可用或已被使用', 16, 1);
            IF @discount > @total SET @discount = @total;
        END;

        DECLARE @recv_name NVARCHAR(50), @recv_phone VARCHAR(20), @recv_addr NVARCHAR(200);
        SELECT @recv_name = receiver_name, @recv_phone = phone,
               @recv_addr = CONCAT(province, city, district, detail)
        FROM shipping_addresses WITH (UPDLOCK, HOLDLOCK)
        WHERE address_id = @address_id AND user_id = @user_id;
        IF @recv_name IS NULL RAISERROR(N'收货地址不存在', 16, 1);

        DECLARE @actual DECIMAL(10, 2) = @total - @discount;
        EXEC sp_GetNextSeq N'ORD', @order_no OUTPUT;
        INSERT INTO orders(
            user_id, order_no, total_amount, discount_amount, actual_amount,
            order_status, payment_status, receiver_name, receiver_phone, receiver_addr
        ) VALUES(
            @user_id, @order_no, @total, @discount, @actual,
            N'待支付', N'未支付', @recv_name, @recv_phone, @recv_addr
        );
        SET @order_id = SCOPE_IDENTITY();

        INSERT INTO order_items(order_id, book_item_id, quantity, unit_price, subtotal)
        SELECT @order_id, it.book_item_id, it.quantity, bi.price, it.quantity * bi.price
        FROM @items it JOIN book_items bi ON bi.book_item_id = it.book_item_id;
        UPDATE bi SET locked_stock = locked_stock + it.quantity
        FROM book_items bi JOIN @items it ON it.book_item_id = bi.book_item_id;

        IF @coupon_id IS NOT NULL
            UPDATE user_coupons SET status = N'已使用', used_time = SYSDATETIME(), order_id = @order_id
            WHERE user_coupon_id = @coupon_id;
        DELETE ci FROM cart_items ci JOIN @items it ON it.book_item_id = ci.book_item_id
        WHERE ci.user_id = @user_id;

        COMMIT TRANSACTION;
        SET @success = 1;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
GO

CREATE OR ALTER PROCEDURE sp_PayOrder
    @order_id INT,
    @payment_method NVARCHAR(20),
    @success BIT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    SET @success = 0;
    BEGIN TRANSACTION;
    BEGIN TRY
        DECLARE @user_id INT, @actual_amount DECIMAL(10, 2), @payment_no NVARCHAR(50);
        SELECT @user_id = user_id, @actual_amount = actual_amount
        FROM orders WITH (ROWLOCK, XLOCK)
        WHERE order_id = @order_id AND order_status = N'待支付' AND payment_status = N'未支付';
        IF @user_id IS NULL RAISERROR(N'订单状态异常，无法支付', 16, 1);
        IF NOT EXISTS(SELECT 1 FROM order_items WHERE order_id = @order_id)
            RAISERROR(N'订单明细为空，无法支付', 16, 1);
        IF EXISTS(
            SELECT 1 FROM order_items oi
            JOIN book_items bi WITH (ROWLOCK, XLOCK) ON bi.book_item_id = oi.book_item_id
            WHERE oi.order_id = @order_id AND (bi.stock < oi.quantity OR bi.locked_stock < oi.quantity)
        ) RAISERROR(N'部分商品库存不足，无法支付', 16, 1);

        EXEC sp_GetNextSeq N'PAY', @payment_no OUTPUT;
        INSERT INTO payment_records(
            order_id, user_id, payment_no, amount, payment_method, payment_status, paid_time
        ) VALUES(
            @order_id, @user_id, @payment_no, @actual_amount, @payment_method, N'已支付', SYSDATETIME()
        );
        UPDATE bi
        SET stock = stock - oi.quantity, locked_stock = locked_stock - oi.quantity,
            sales_count = sales_count + oi.quantity
        FROM book_items bi JOIN order_items oi ON oi.book_item_id = bi.book_item_id
        WHERE oi.order_id = @order_id;
        UPDATE orders SET order_status = N'已完成', payment_status = N'已支付', paid_time = SYSDATETIME()
        WHERE order_id = @order_id;

        DECLARE @points INT = FLOOR(@actual_amount);
        INSERT INTO points_records(user_id, points_change, reason, related_id)
        VALUES(@user_id, @points, N'购买', @order_id);
        UPDATE ordinary_users
        SET total_points = total_points + @points, available_points = available_points + @points
        WHERE user_id = @user_id;

        COMMIT TRANSACTION;
        SET @success = 1;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
GO

CREATE OR ALTER PROCEDURE sp_RefundOrder
    @order_id INT,
    @refund_id INT,
    @success BIT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    SET @success = 0;
    BEGIN TRANSACTION;
    BEGIN TRY
        DECLARE @payment_id INT;
        SELECT @payment_id = rr.payment_id
        FROM refund_records rr WITH (ROWLOCK, XLOCK)
        JOIN orders o WITH (ROWLOCK, XLOCK) ON o.order_id = rr.order_id
        WHERE rr.refund_id = @refund_id AND rr.order_id = @order_id
          AND rr.refund_status = N'处理中'
          AND o.order_status = N'已完成' AND o.payment_status = N'已支付';
        IF @payment_id IS NULL RAISERROR(N'未找到可批准的退款申请', 16, 1);

        UPDATE refund_records SET refund_status = N'已退款', refund_time = SYSDATETIME()
        WHERE refund_id = @refund_id;
        UPDATE orders SET order_status = N'已退款', payment_status = N'已退款'
        WHERE order_id = @order_id;
        UPDATE payment_records SET payment_status = N'已退款' WHERE payment_id = @payment_id;
        UPDATE bi
        SET stock = stock + oi.quantity,
            sales_count = CASE WHEN sales_count >= oi.quantity THEN sales_count - oi.quantity ELSE 0 END
        FROM book_items bi JOIN order_items oi ON oi.book_item_id = bi.book_item_id
        WHERE oi.order_id = @order_id;

        COMMIT TRANSACTION;
        SET @success = 1;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
GO

CREATE OR ALTER PROCEDURE sp_CheckIn
    @user_id INT,
    @success BIT OUTPUT,
    @continuous_days INT OUTPUT,
    @reward_points INT OUTPUT,
    @got_coupon BIT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    SET @success = 0;
    SET @got_coupon = 0;
    BEGIN TRANSACTION;
    BEGIN TRY
        IF EXISTS(
            SELECT 1 FROM checkin_record WITH (UPDLOCK, HOLDLOCK)
            WHERE user_id = @user_id AND checkin_date = CAST(SYSDATETIME() AS DATE)
        ) RAISERROR(N'今日已签到，请勿重复操作', 16, 1);
        IF NOT EXISTS(SELECT 1 FROM ordinary_users WHERE user_id = @user_id)
            RAISERROR(N'用户资料不存在', 16, 1);

        DECLARE @yesterday DATE = DATEADD(DAY, -1, CAST(SYSDATETIME() AS DATE));
        DECLARE @last_count INT = 0;
        SELECT TOP 1 @last_count = continuous_checkin_days
        FROM checkin_record WHERE user_id = @user_id AND checkin_date = @yesterday
        ORDER BY checkin_id DESC;
        IF @@ROWCOUNT > 0 SET @last_count = @last_count + 1;
        ELSE SET @last_count = 1;

        SET @reward_points = CASE (@last_count - 1) % 7
            WHEN 0 THEN 5 WHEN 1 THEN 5 WHEN 2 THEN 10 WHEN 3 THEN 10
            WHEN 4 THEN 10 WHEN 5 THEN 15 WHEN 6 THEN 30 END;
        DECLARE @activity_id INT;
        SELECT TOP 1 @activity_id = activity_id FROM promotion_activities
        WHERE activity_name = N'每日签到' AND status = N'进行中' ORDER BY activity_id DESC;

        INSERT INTO checkin_record(
            user_id, activity_id, checkin_date, continuous_checkin_days, reward_points
        ) VALUES(
            @user_id, @activity_id, CAST(SYSDATETIME() AS DATE), @last_count, @reward_points
        );
        DECLARE @checkin_id INT = SCOPE_IDENTITY();
        INSERT INTO points_records(user_id, points_change, reason, related_id)
        VALUES(@user_id, @reward_points, N'签到', @checkin_id);
        UPDATE ordinary_users
        SET total_points = total_points + @reward_points,
            available_points = available_points + @reward_points,
            continuous_checkin_days = @last_count
        WHERE user_id = @user_id;

        IF @last_count % 7 = 0
        BEGIN
            INSERT INTO user_coupons(user_id, coupon_id, status)
            SELECT @user_id, coupon_id, N'未使用' FROM coupons
            WHERE coupon_name = N'连续7天签到券' AND status = N'启用';
            IF @@ROWCOUNT > 0 SET @got_coupon = 1;
        END;
        IF @last_count % 30 = 0
        BEGIN
            INSERT INTO user_coupons(user_id, coupon_id, status)
            SELECT @user_id, coupon_id, N'未使用' FROM coupons
            WHERE coupon_name = N'连续30天签到券' AND status = N'启用';
            IF @@ROWCOUNT > 0 SET @got_coupon = 1;
        END;

        COMMIT TRANSACTION;
        SET @success = 1;
        SET @continuous_days = @last_count;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
GO

CREATE OR ALTER PROCEDURE sp_RedeemReward
    @user_id INT,
    @reward_id INT,
    @success BIT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    SET @success = 0;
    BEGIN TRANSACTION;
    BEGIN TRY
        DECLARE @user_points INT, @user_level INT;
        SELECT @user_points = available_points, @user_level = level
        FROM ordinary_users WITH (ROWLOCK, XLOCK) WHERE user_id = @user_id;
        IF @user_points IS NULL RAISERROR(N'用户资料不存在', 16, 1);

        DECLARE @req_points INT, @req_level INT, @stock INT;
        SELECT @req_points = required_points, @req_level = required_level, @stock = stock
        FROM point_rewards WITH (ROWLOCK, XLOCK)
        WHERE reward_id = @reward_id AND status = N'启用';
        IF @req_points IS NULL RAISERROR(N'奖品不存在', 16, 1);
        IF @user_points < @req_points RAISERROR(N'积分不足', 16, 1);
        IF @user_level < @req_level RAISERROR(N'等级不够', 16, 1);
        IF @stock <= 0 RAISERROR(N'库存不足', 16, 1);

        UPDATE ordinary_users SET available_points = available_points - @req_points
        WHERE user_id = @user_id;
        UPDATE point_rewards SET stock = stock - 1 WHERE reward_id = @reward_id;
        INSERT INTO reward_redemptions(user_id, reward_id, used_points)
        VALUES(@user_id, @reward_id, @req_points);
        DECLARE @redemption_id INT = SCOPE_IDENTITY();
        INSERT INTO points_records(user_id, points_change, reason, related_id)
        VALUES(@user_id, -@req_points, N'兑换奖品', @redemption_id);

        COMMIT TRANSACTION;
        SET @success = 1;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
GO

CREATE OR ALTER PROCEDURE sp_ExpireCoupons
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE uc SET status = N'已过期'
    FROM user_coupons uc JOIN coupons c ON c.coupon_id = uc.coupon_id
    WHERE uc.status = N'未使用' AND c.valid_end < SYSDATETIME();
END;
GO
