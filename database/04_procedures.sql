USE My_eBookStore;
GO

CREATE PROCEDURE sp_GetNextSeq
	@seq_type NVARCHAR(5),
	@new_no NVARCHAR(50) OUTPUT
AS
BEGIN
	SET NOCOUNT ON;
	DECLARE @today DATE=CAST(SYSDATETIME() AS DATE);
	UPDATE daily_sequences WITH (UPDLOCK,HOLDLOCK)
	SET current_no=current_no+1
	WHERE seq_date=@today AND seq_type=@seq_type;
	IF @@ROWCOUNT=0
	BEGIN
		INSERT INTO daily_sequences(seq_date,seq_type,current_no)
		VALUES (@today,@seq_type,1);
	END
	DECLARE @seq INT;
	SELECT @seq=current_no
	FROM daily_sequences WITH (UPDLOCK,HOLDLOCK)
	WHERE seq_date=@today AND seq_type=@seq_type;
	SET @new_no=@seq_type+FORMAT(@today,'yyyyMMdd')+RIGHT('000000'+CAST(@seq AS NVARCHAR),6);
END;
GO

CREATE PROCEDURE sp_CreateOrder
	@user_id INT,
	@items_json NVARCHAR(MAX),
	@address_id INT,
	@coupon_id INT =NULL,
	@success BIT OUTPUT,
	@order_id INT OUTPUT,
	@order_no NVARCHAR(50) OUTPUT
AS
BEGIN
	SET NOCOUNT ON;
	BEGIN TRANSACTION
	BEGIN TRY
		DECLARE @items TABLE(
			book_item_id INT NOT NULL,
			quantity INT NOT NULL
		);
		INSERT INTO @items(book_item_id,quantity)
		SELECT bid,qty
		FROM OPENJSON(@items_json)
		WITH (bid INT '$.bid',qty INT '$.qty');

		IF EXISTS(
			SELECT 1 FROM @items it
			JOIN book_items bi
			WITH (ROWLOCK,XLOCK) ON bi.book_item_id=it.book_item_id
			WHERE (bi.stock-bi.locked_stock)<it.quantity OR bi.status!=N'在售'
		)
		BEGIN
			RAISERROR(N'部分书目库存不足或已下架',16,1);
		END

		DECLARE @total DECIMAL(10,2);
		SELECT @total=SUM(it.quantity*bi.price)
		FROM @items it
		JOIN book_items bi ON bi.book_item_id=it.book_item_id;

		DECLARE @discount DECIMAL(10,2)=0;
		IF @coupon_id IS NOT NULL
		BEGIN
			SELECT @discount=c.amount
			FROM user_coupons uc
			JOIN coupons c ON uc.coupon_id=c.coupon_id
			WHERE uc.user_coupon_id=@coupon_id AND 
			uc.user_id=@user_id AND 
			uc.status=N'未使用' AND 
			c.min_amount<=@total AND 
			SYSDATETIME() BETWEEN c.valid_start AND c.valid_end;
			IF @discount IS NULL SET @discount=0;
		END

		DECLARE @actual DECIMAL(10,2)=@total-@discount;
		IF @actual<0 SET @actual=0;

		DECLARE @recv_name NVARCHAR(50);
		DECLARE @recv_phone VARCHAR(20);
		DECLARE @recv_addr NVARCHAR(200);
		SELECT @recv_name=receiver_name,@recv_phone=phone,@recv_addr=province+city+district+detail
		FROM shipping_addresses
		WHERE address_id=@address_id AND user_id=@user_id;
		IF @recv_name IS NULL
		BEGIN
			RAISERROR(N'无收货地址',16,1);
		END

		EXEC sp_GetNextSeq N'ORD',@order_no OUTPUT;

		INSERT INTO orders(user_id,order_no,total_amount,discount_amount,actual_amount,order_status,payment_status,receiver_name,receiver_phone,receiver_addr)
		VALUES(@user_id,@order_no,@total,@discount,@actual,N'待支付',N'未支付',@recv_name,@recv_phone,@recv_addr);
		SET @order_id=SCOPE_IDENTITY();

		INSERT INTO order_items(order_id,book_item_id,quantity,unit_price,subtotal)
		SELECT @order_id,it.book_item_id,it.quantity,bi.price,it.quantity*bi.price
		FROM @items it
		JOIN book_items bi ON bi.book_item_id=it.book_item_id;

		UPDATE book_items
		SET locked_stock=locked_stock+it.quantity
		FROM book_items bi
		JOIN @items it ON bi.book_item_id=it.book_item_id;

		IF @coupon_id IS NOT NULL AND @discount>0
		BEGIN
			UPDATE user_coupons
			SET status=N'已使用',used_time=SYSDATETIME(),order_id=@order_id
			WHERE user_coupon_id=@coupon_id;
		END
		DELETE ci
		FROM cart_items ci
		JOIN @items it ON ci.book_item_id=it.book_item_id
		WHERE ci.user_id=@user_id;

		COMMIT TRANSACTION;
		SET @success=1;
END TRY
BEGIN CATCH
	ROLLBACK TRANSACTION;
	SET @success=0;
	THROW;
END CATCH
END;
GO

CREATE PROCEDURE sp_PayOrder
	@order_id INT,
	@success BIT OUTPUT
AS
BEGIN
	SET NOCOUNT ON;
	BEGIN TRANSACTION
	BEGIN TRY
		DECLARE @user_id INT;
		DECLARE @actual_amount DECIMAL(10,2);
		DECLARE @payment_no NVARCHAR(50);

		SELECT @user_id=user_id,@actual_amount=actual_amount
		FROM orders WITH (ROWLOCK,XLOCK)
		WHERE order_id=@order_id AND order_status=N'待支付';
		IF @user_id IS NULL
		BEGIN
			RAISERROR(N'订单状态异常',16,1);
		END
		EXEC sp_GetNextSeq N'PAY',@payment_no OUTPUT;

		UPDATE orders
		SET order_status=N'已完成',payment_status=N'已支付',paid_time=SYSDATETIME()
		WHERE order_id=@order_id;

		INSERT INTO payment_records(order_id,user_id,payment_no,amount,payment_status,paid_time)
		VALUES(@order_id,@user_id,@payment_no,@actual_amount,N'已支付',SYSDATETIME());
		
		UPDATE book_items
		SET stock=stock-oi.quantity,locked_stock=locked_stock-oi.quantity,sales_count=sales_count+oi.quantity
		FROM book_items bi
		JOIN order_items oi ON bi.book_item_id=oi.book_item_id
		WHERE oi.order_id=@order_id;

		DECLARE @points INT =FLOOR(@actual_amount)
		INSERT INTO points_records(user_id,points_change,reason,related_id)
		VALUES(@user_id,@points,N'购买消费',@order_id);

		UPDATE ordinary_users
		SET total_points=total_points+@points,available_points=available_points+@points
		WHERE user_id=@user_id;

		COMMIT TRANSACTION;
		SET @success=1;
	END TRY
	BEGIN CATCH
		ROLLBACK TRANSACTION;
		SET @success=0;
		THROW;
	END CATCH
END;
GO

CREATE PROCEDURE sp_RefundOrder
	@order_id INT,
	@refund_reason NVARCHAR(500),
	@success BIT OUTPUT
AS
BEGIN
	SET NOCOUNT ON;

	BEGIN TRANSACTION
	BEGIN TRY
		DECLARE @user_id INT;
		DECLARE @actual_amount DECIMAL(10,2);
		DECLARE @payment_id INT;
		SELECT @user_id=orders.user_id,@actual_amount=actual_amount,@payment_id=payment_id
		FROM orders
		LEFT JOIN payment_records pr ON pr.order_id=orders.order_id
		WHERE orders.order_id=@order_id AND orders.order_status=N'已完成';
		IF @user_id IS NULL
		BEGIN
			RAISERROR(N'订单状态不允许退款或订单不存在',16,1);
		END

		UPDATE orders
		SET order_status=N'已退款',payment_status=N'已退款'
		WHERE order_id=@order_id;

		DECLARE @refund_no NVARCHAR(50);
		EXEC sp_GetNextSeq N'REF',@refund_no OUTPUT;

		INSERT INTO refund_records(order_id,user_id,payment_id,refund_no,refund_amount,refund_reason,refund_status,refund_time)
		VALUES(@order_id,@user_id,@payment_id,@refund_no,@actual_amount,@refund_reason,N'已退款',SYSDATETIME());

		UPDATE book_items
		SET stock=stock+oi.quantity,sales_count=sales_count-oi.quantity
		FROM book_items bi
		JOIN order_items oi ON bi.book_item_id=oi.book_item_id
		WHERE oi.order_id=@order_id;

		COMMIT TRANSACTION;
		SET @success=1;
	END TRY
	BEGIN CATCH
		ROLLBACK TRANSACTION;
		SET @success=0;
		THROW;
	END CATCH
END;
GO

CREATE PROCEDURE sp_CheckIn
	@user_id INT,
	@success BIT OUTPUT,
	@continuous_days INT OUTPUT,
	@reward_points INT OUTPUT,
	@got_coupon BIT OUTPUT
AS
BEGIN
	SET NOCOUNT ON;
	BEGIN TRANSACTION
	BEGIN TRY
		IF EXISTS(
			SELECT 1
			FROM checkin_record
			WHERE user_id=@user_id AND checkin_date=CAST(SYSDATETIME() AS DATE)
		)
		BEGIN
			RAISERROR(N'今日已签到',16,1);
		END

		DECLARE @yesterday DATE =DATEADD(DAY,-1,CAST(SYSDATETIME() AS DATE));
		DECLARE @last_count INT =0;
		SELECT TOP 1 @last_count=continuous_checkin_days
		FROM checkin_record
		WHERE user_id=@user_id AND checkin_date=@yesterday;

		IF @@ROWCOUNT>0
			SET @last_count=@last_count+1;
		ELSE
			SET @last_count=1;

		SET @reward_points = CASE(@last_count-1)%7
            WHEN 0 THEN 5
            WHEN 1 THEN 5
            WHEN 2 THEN 10
            WHEN 3 THEN 10
            WHEN 4 THEN 10
            WHEN 5 THEN 15
            WHEN 6 THEN 30
        END;
		
		DECLARE @checkin_activity_id INT =(
			SELECT activity_id
			FROM promotion_activities
			WHERE activity_name=N'每日签到' AND status=N'进行中'
		);
		INSERT INTO checkin_record(user_id,activity_id,checkin_date,continuous_checkin_days,reward_points)
		VALUES(@user_id,@checkin_activity_id,CAST(SYSDATETIME() AS DATE),@last_count,@reward_points);

		INSERT INTO points_records(user_id,points_change,reason,related_id)
		VALUES(@user_id,@reward_points,N'签到',SCOPE_IDENTITY());

		UPDATE ordinary_users
		SET total_points=total_points+@reward_points,available_points=available_points+@reward_points,continuous_checkin_days=@last_count
		WHERE user_id=@user_id;

		SET @got_coupon=0;
		IF @last_count%7=0
		BEGIN
			INSERT INTO user_coupons(user_id,coupon_id,status)
			SELECT @user_id,coupon_id,N'未使用'
			FROM coupons
			WHERE coupon_name=N'连续7天签到券' AND status=N'启用';
			SET @got_coupon=1;
		END
		IF @last_count%30=0
		BEGIN
			INSERT INTO user_coupons(user_id,coupon_id,status)
			SELECT @user_id,coupon_id,N'未使用'
			FROM coupons
			WHERE coupon_name=N'连续30天签到券' AND status=N'启用';
			SET @got_coupon=1;
		END

		COMMIT TRANSACTION;
		SET @success=1;
		SET @continuous_days=@last_count;
	END TRY
	BEGIN CATCH
		ROLLBACK TRANSACTION;
		SET @success=0;
		THROW;
	END CATCH
END;
GO

CREATE PROCEDURE sp_RedeemReward
	@user_id INT,
	@reward_id INT,
	@success BIT OUTPUT
AS
BEGIN
	SET NOCOUNT ON;
	BEGIN TRANSACTION
	BEGIN TRY
		DECLARE @user_points INT;
		DECLARE @user_level INT;
		SELECT @user_points=available_points,@user_level=level
		FROM ordinary_users WITH (ROWLOCK, XLOCK)
		WHERE user_id=@user_id;

		DECLARE @req_points INT;
		DECLARE @req_level INT;
		DECLARE @stock INT;
		SELECT @req_points=required_points,@req_level=required_level,@stock=stock
		FROM point_rewards WITH (ROWLOCK,XLOCK)
		WHERE reward_id=@reward_id AND status=N'启动';
		
		IF @user_points<@req_points
			RAISERROR(N'可用积分不足',16,1);
		IF @user_level<@req_level
			RAISERROR(N'会员登记不足',16,1);
		IF @stock<=0
			RAISERROR(N'奖品已兑完',16,1);

		UPDATE ordinary_users
		SET available_points=available_points-@req_points
		WHERE user_id=@user_id;

		UPDATE point_rewards
		SET stock=stock-1
		WHERE reward_id=@reward_id;

		INSERT INTO reward_redemptions(user_id,reward_id,used_points,redeemed_time)
		VALUES(@user_id,@reward_id,@req_points,SYSDATETIME());
		INSERT INTO points_records(user_id,points_change,reason,related_id)
		VALUES(@user_id,@req_points,N'积分兑换奖品',SCOPE_IDENTITY());

		COMMIT TRANSACTION;
		SET @success=1;
	END TRY
	BEGIN CATCH
		ROLLBACK TRANSACTION;
		SET @success=0;
		THROW;
	END CATCH
END;
GO

