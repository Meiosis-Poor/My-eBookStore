CREATE DATABASE	My_eBookStore;
GO

USE My_eBookStore;
GO

CREATE TABLE users(
	user_id INT PRIMARY KEY IDENTITY(1,1),
	user_name NVARCHAR(50) NOT NULL UNIQUE,
	password_hash VARCHAR(255) NOT NULL,
	phone VARCHAR(20) NULL,
	email NVARCHAR(100) NULL,
	user_type NVARCHAR(20) NOT NULL CHECK(user_type IN (N'普通用户',N'书店管理员',N'系统管理员')),
	status NVARCHAR(20) NOT NULL DEFAULT N'正常' CHECK(status IN (N'正常',N'封禁')),
	created_time DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

CREATE TABLE ordinary_users(
	user_id INT PRIMARY KEY FOREIGN KEY REFERENCES users(user_id),
	nickname NVARCHAR(50) NOT NULL,
	level INT NOT NULL DEFAULT 1,
	total_points INT NOT NULL DEFAULT 0,
	available_points INT NOT NULL DEFAULT 0,
	continuous_checkin_days INT NOT NULL DEFAULT 0
);
GO

CREATE TABLE store_admins(
	user_id INT PRIMARY KEY FOREIGN KEY REFERENCES users(user_id),
	admin_name NVARCHAR(50) NOT NULL,
	admin_status NVARCHAR(20) NOT NULL DEFAULT N'正常' CHECK (admin_status IN (N'正常',N'停用'))
);
GO

CREATE TABLE system_admins(
	user_id INT PRIMARY KEY FOREIGN KEY REFERENCES users(user_id),
	admin_name NVARCHAR(50) NOT NULL
);
GO

CREATE TABLE stores(
	store_id INT PRIMARY KEY IDENTITY(1,1),
	store_name NVARCHAR(50) NOT NULL UNIQUE,
	user_id INT NOT NULL FOREIGN KEY REFERENCES users(user_id),
	description NVARCHAR(500) NULL,
	status NVARCHAR(20) NOT NULL DEFAULT N'正常' CHECK (status IN (N'正常',N'封禁')),
	created_time DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

CREATE TABLE book_categories(
	category_id INT PRIMARY KEY IDENTITY(1,1),
	category_name NVARCHAR(50) NOT NULL,
	description NVARCHAR(500) NULL,
	status NVARCHAR(20) NOT NULL DEFAULT N'启用' CHECK (status IN (N'启用',N'停用'))
);
GO

CREATE TABLE book_infos(
	book_info_id INT IDENTITY(1,1) CONSTRAINT PK_book_infos PRIMARY KEY,
	category_id INT NOT NULL FOREIGN KEY REFERENCES book_categories(category_id),
	book_name NVARCHAR(50) NOT NULL,
	author NVARCHAR(50) NOT NULL,
	publisher NVARCHAR(50) NULL,
	ISBN NVARCHAR(50) NULL UNIQUE,
	publish_date DATE NULL,
	description NVARCHAR(MAX) NULL,
	cover_image NVARCHAR(500) NULL,
	embedding NVARCHAR(MAX) NULL,
	status NVARCHAR(20) NOT NULL DEFAULT N'正常' CHECK (status IN (N'正常',N'下架'))
);
GO

CREATE TABLE book_items(
	book_item_id INT PRIMARY KEY IDENTITY(1,1),
	book_info_id INT NOT NULL FOREIGN KEY REFERENCES book_infos(book_info_id),
	store_id INT NOT NULL FOREIGN KEY REFERENCES stores(store_id),
	price DECIMAL(10,2) NOT NULL,
	stock INT NOT NULL DEFAULT 0,
	locked_stock INT NOT NULL DEFAULT 0,
	sales_count INT NOT NULL DEFAULT 0,
	status NVARCHAR(20) NOT NULL DEFAULT N'在售' CHECK (status IN (N'在售',N'下架')),
	created_time DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

CREATE TABLE promotion_activities(
	activity_id INT PRIMARY KEY IDENTITY(1,1),
	activity_name NVARCHAR(50) NOT NULL,
	activity_type NVARCHAR(50) NOT NULL,
	description NVARCHAR(MAX) NOT NULL,
	start_time DATETIME2 NOT NULL,
	end_time DATETIME2 NOT NULL,
	status NVARCHAR(20) NOT NULL DEFAULT N'未开始' CHECK(status IN (N'未开始',N'进行中',N'已结束')),
	created_admin INT NOT NULL FOREIGN KEY REFERENCES system_admins(user_id)
);
GO

CREATE TABLE cart_items(
	cart_item_id INT PRIMARY KEY IDENTITY(1,1),
	user_id INT NOT NULL FOREIGN KEY REFERENCES users(user_id),
	book_item_id INT NOT NULL FOREIGN KEY REFERENCES book_items(book_item_id),
	quantity INT NOT NULL DEFAULT 1,
	add_time DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

CREATE TABLE shipping_addresses(
	address_id INT PRIMARY KEY IDENTITY(1,1),
	user_id INT NOT NULL FOREIGN KEY REFERENCES users(user_id),
	receiver_name NVARCHAR(50) NOT NULL,
	phone VARCHAR(20) NOT NULL,
	province NVARCHAR(50) NOT NULL,
	city NVARCHAR(50) NOT NULL,
	district NVARCHAR(50) NOT NULL,
	detail NVARCHAR(200) NOT NULL,
	is_default BIT NOT NULL DEFAULT 0
);
GO

CREATE TABLE orders(
	order_id INT PRIMARY KEY IDENTITY(1,1),
	user_id INT NOT NULL FOREIGN KEY REFERENCES users(user_id),
	order_no NVARCHAR(50) NOT NULL UNIQUE,
	total_amount DECIMAL(10,2) NOT NULL,
	discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
	actual_amount DECIMAL(10,2) NOT NULL,
	order_status NVARCHAR(20) NOT NULL DEFAULT N'待支付' CHECK (order_status IN (N'待支付',N'已完成',N'已取消',N'已退款')),
	payment_status NVARCHAR(20) NOT NULL DEFAULT N'未支付' CHECK (payment_status IN (N'未支付',N'已支付',N'已退款')),
	receiver_name NVARCHAR(50) NOT NULL,
	receiver_phone VARCHAR(20) NOT NULL,
	receiver_addr NVARCHAR(200) NOT NULL,
	created_time DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
	paid_time DATETIME2 NULL
);
GO

CREATE TABLE order_items(
	order_item_id INT PRIMARY KEY IDENTITY(1,1),
	order_id INT NOT NULL FOREIGN KEY REFERENCES orders(order_id),
	book_item_id INT NOT NULL FOREIGN KEY REFERENCES book_items(book_item_id),
	quantity INT NOT NULL,
	unit_price DECIMAL(10,2) NOT NULL,
	subtotal DECIMAL(10,2) NOT NULL
);
GO

CREATE TABLE payment_records(
	payment_id INT PRIMARY KEY IDENTITY(1,1),
	order_id INT NOT NULL FOREIGN KEY REFERENCES orders(order_id),
	user_id INT NOT NULL FOREIGN KEY REFERENCES users(user_id),
	payment_no NVARCHAR(50) NOT NULL,
	amount DECIMAL(10,2) NOT NULL,
	payment_method NVARCHAR(20) NOT NULL,
	payment_status NVARCHAR(20) NOT NULL DEFAULT N'未支付' CHECK (payment_status IN (N'未支付',N'已支付',N'已退款')),
	paid_time DATETIME2 NULL,
	created_time DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

CREATE TABLE refund_records(
	refund_id INT PRIMARY KEY IDENTITY(1,1),
	order_id INT NOT NULL FOREIGN KEY REFERENCES orders(order_id),
	user_id INT NOT NULL FOREIGN KEY REFERENCES users(user_id),
	payment_id INT NOT NULL FOREIGN KEY REFERENCES payment_records(payment_id),
	refund_no NVARCHAR(50) NOT NULL,
	refund_amount DECIMAL(10,2) NOT NULL,
	refund_reason NVARCHAR(MAX) NULL,
	refund_status NVARCHAR(20) NOT NULL DEFAULT N'处理中' CHECK (refund_status IN (N'处理中',N'已退款',N'已拒绝')),
	request_time DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
	refund_time DATETIME2 NULL
);
GO

CREATE TABLE coupons(
	coupon_id INT PRIMARY KEY IDENTITY(1,1),
	activity_id INT NOT NULL FOREIGN KEY REFERENCES promotion_activities(activity_id),
	coupon_name NVARCHAR(50) NOT NULL,
	coupon_type NVARCHAR(20) NOT NULL CHECK (coupon_type IN (N'平台券',N'店铺券')),
	store_id INT NULL FOREIGN KEY REFERENCES stores(store_id),
	amount DECIMAL(10,2) NOT NULL,
	min_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
	valid_start DATETIME2 NOT NULL,
	valid_end DATETIME2 NOT NULL,
	status NVARCHAR(20) NOT NULL DEFAULT N'启用' CHECK (status IN (N'启用',N'停用'))
);
GO

CREATE TABLE user_coupons(
	user_coupon_id INT PRIMARY KEY IDENTITY(1,1),
	user_id INT NOT NULL FOREIGN KEY REFERENCES users(user_id),
	coupon_id INT NOT NULL FOREIGN KEY REFERENCES coupons(coupon_id),
	status NVARCHAR(20) NOT NULL DEFAULT N'未使用' CHECK (status IN (N'未使用',N'已使用',N'已过期')),
	received_time DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
	used_time DATETIME2 NULL,
	order_id INT NULL FOREIGN KEY REFERENCES orders(order_id)
);
GO

CREATE TABLE point_rewards(
	reward_id INT PRIMARY KEY IDENTITY(1,1),
	reward_name NVARCHAR(50) NOT NULL,
	reward_type NVARCHAR(20) NOT NULL CHECK (reward_type IN (N'实物',N'代金券',N'虚拟商品')),
	required_points INT NOT NULL,
	required_level INT NOT NULL DEFAULT 1,
	stock INT NOT NULL DEFAULT 0,
	status NVARCHAR(20) NOT NULL DEFAULT N'启用' CHECK (status IN (N'启用',N'停用')),
	manage_admin INT NOT NULL FOREIGN KEY REFERENCES system_admins(user_id)
);
GO

CREATE TABLE reward_redemptions(
	redemption_id INT PRIMARY KEY IDENTITY(1,1),
	user_id INT NOT NULL FOREIGN KEY REFERENCES users(user_id),
	reward_id INT NOT NULL FOREIGN KEY REFERENCES point_rewards(reward_id),
	used_points INT NOT NULL,
	status NVARCHAR(20) NOT NULL DEFAULT N'已完成' CHECK (status IN (N'已完成',N'已取消')),
	redeemed_time DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

CREATE TABLE store_activity_participation(
	store_id INT NOT NULL FOREIGN KEY REFERENCES stores(store_id),
	activity_id INT NOT NULL FOREIGN KEY REFERENCES promotion_activities(activity_id),
	participate_status NVARCHAR(20) NOT NULL DEFAULT N'已参与' CHECK (participate_status IN (N'已参与',N'已退出')),
	join_time DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
	coupon_amount DECIMAL(10,2) NULL,
	coupon_quantity INT NULL,
	PRIMARY KEY (store_id,activity_id)
);
GO

CREATE TABLE activity_books(
	store_id INT NOT NULL,
	activity_id INT NOT NULL,
	book_item_id INT NOT NULL FOREIGN KEY REFERENCES book_items(book_item_id),
	activity_price DECIMAL(10,2) NULL,
	discount_rate DECIMAL(5,2) NULL,
	activity_stock INT NULL,
	status NVARCHAR(20) NOT NULL DEFAULT N'参与中' CHECK (status IN (N'参与中',N'已结束')),
	PRIMARY KEY(store_id,activity_id,book_item_id),
	FOREIGN KEY(store_id,activity_id) REFERENCES store_activity_participation(store_id,activity_id)
);
GO

CREATE TABLE checkin_record(
	checkin_id INT PRIMARY KEY IDENTITY(1,1),
	user_id	INT NOT NULL FOREIGN KEY REFERENCES users(user_id),
	activity_id INT NULL FOREIGN KEY REFERENCES promotion_activities(activity_id),
	checkin_date DATE NOT NULL,
	continuous_checkin_days INT NOT NULL,
	reward_points INT NOT NULL DEFAULT 0,
	reward_coupon_id INT NULL FOREIGN KEY REFERENCES coupons(coupon_id),
	CONSTRAINT UQ_checkin_user_date UNIQUE(user_id,checkin_date)
);
GO

CREATE TABLE points_records(
	record_id INT PRIMARY KEY IDENTITY(1,1),
	user_id INT NOT NULL FOREIGN KEY REFERENCES users(user_id),
	points_change INT NOT NULL,
	reason NVARCHAR(50) NOT NULL CHECK (reason IN (N'签到',N'购买',N'兑换奖品',N'等级周奖励')),
	related_id INT NOT NULL,
	created_time DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

CREATE TABLE browse_history(
	browse_id INT PRIMARY KEY IDENTITY(1,1),
	user_id INT NOT NULL FOREIGN KEY REFERENCES users(user_id),
	book_item_id INT NOT NULL FOREIGN KEY REFERENCES book_items(book_item_id),
	browse_duration INT NOT NULL DEFAULT 0,
	created_time DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

CREATE TABLE search_history(
	search_id INT PRIMARY KEY IDENTITY(1,1),
	user_id INT NOT NULL FOREIGN KEY REFERENCES users(user_id),
	keyword NVARCHAR(200) NOT NULL,
	keyword_embedding NVARCHAR(MAX) NULL,
	created_time DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

CREATE TABLE reviews(
	review_id INT PRIMARY KEY IDENTITY(1,1),
	user_id INT NOT NULL FOREIGN KEY REFERENCES users(user_id),
	book_item_id INT NOT NULL FOREIGN KEY REFERENCES book_items(book_item_id),
	order_id INT NOT NULL FOREIGN KEY REFERENCES orders(order_id),
	rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
	content NVARCHAR(500) NOT NULL,
	created_time DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
	CONSTRAINT UQ_reviews_user_order_book UNIQUE(user_id,book_item_id,order_id)
);
GO

CREATE TABLE store_blacklists(
	blacklist_id INT PRIMARY KEY IDENTITY(1,1),
	store_id INT NOT NULL FOREIGN KEY REFERENCES stores(store_id),
	user_id INT NOT NULL FOREIGN KEY REFERENCES users(user_id),
	reason NVARCHAR(500) NULL,
	created_time DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO
CREATE TABLE recommendation_settings(
	setting_id INT NOT NULL CONSTRAINT PK_recommendation_settings PRIMARY KEY DEFAULT 1,
	guess_weight FLOAT NOT NULL DEFAULT 1,
	hot_weight FLOAT NOT NULL DEFAULT 1,
	search_embedding_enabled BIT NOT NULL DEFAULT 1,
	detail_same_store_enabled BIT NOT NULL DEFAULT 1,
	updated_time DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
	CONSTRAINT CK_recommendation_settings_singleton CHECK(setting_id = 1)
);
GO

CREATE TABLE daily_sequences(
	seq_date DATE NOT NULL,
	seq_type NVARCHAR(5) NOT NULL CHECK (seq_type IN (N'ORD',N'PAY',N'REF')),
	current_no INT NOT NULL DEFAULT 1,
	PRIMARY KEY(seq_date,seq_type)
);
GO

IF NOT EXISTS (SELECT 1 FROM recommendation_settings WHERE setting_id = 1)
BEGIN
	INSERT INTO recommendation_settings(setting_id) VALUES(1);
END
GO
