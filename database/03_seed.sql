-- ============================================================
-- My-eBookStore 网上书店系统 - 测试数据脚本
-- 对应 database/01_buildlist.sql 建表结构
-- 用法：建表成功后，在 SSMS 中打开此文件，按 F5 执行
-- ============================================================

USE My_eBookStore;
GO

-- ============================================================
-- 0. 清空旧数据（按外键依赖倒序删除，避免约束冲突）
-- ============================================================
DELETE FROM store_blacklists;      DELETE FROM reviews;
DELETE FROM browse_history;        DELETE FROM points_records;
DELETE FROM checkin_record;        DELETE FROM reward_redemptions;
DELETE FROM user_coupons;          DELETE FROM coupons;
DELETE FROM activity_books;        DELETE FROM store_activity_participation;
DELETE FROM point_rewards;         DELETE FROM refund_records;
DELETE FROM payment_records;       DELETE FROM order_items;
DELETE FROM orders;                DELETE FROM cart_items;
DELETE FROM shipping_addresses;    DELETE FROM book_items;
DELETE FROM book_infos;            DELETE FROM promotion_activities;
DELETE FROM book_categories;       DELETE FROM stores;
DELETE FROM system_admins;         DELETE FROM store_admins;
DELETE FROM ordinary_users;        DELETE FROM users;
GO

-- ============================================================
-- 1. 用户数据（10 普通用户 + 3 书店管理员 + 1 后台管理员）
-- 密码统一为 "123456"，bcrypt 哈希为占位值
-- ============================================================

-- 1.1 后台管理员
INSERT INTO users (user_name, password_hash, phone, email, user_type, status)
VALUES (N'admin_super', N'$2a$10$hashed_placeholder', N'13900000000', N'admin@ebookstore.com', N'系统管理员', N'正常');
INSERT INTO system_admins (user_id, admin_name) VALUES (SCOPE_IDENTITY(), N'超级管理员');
GO

-- 1.2 书店管理员（3 人）
INSERT INTO users (user_name, password_hash, phone, email, user_type, status)
VALUES (N'seller_zhang', N'$2a$10$hashed_placeholder', N'13911111111', N'zhang@ebookstore.com', N'书店管理员', N'正常');
INSERT INTO store_admins (user_id, admin_name, admin_status) VALUES (SCOPE_IDENTITY(), N'张店长', N'正常');
GO

INSERT INTO users (user_name, password_hash, phone, email, user_type, status)
VALUES (N'seller_li', N'$2a$10$hashed_placeholder', N'13922222222', N'li@ebookstore.com', N'书店管理员', N'正常');
INSERT INTO store_admins (user_id, admin_name, admin_status) VALUES (SCOPE_IDENTITY(), N'李店长', N'正常');
GO

INSERT INTO users (user_name, password_hash, phone, email, user_type, status)
VALUES (N'seller_wang', N'$2a$10$hashed_placeholder', N'13933333333', N'wang@ebookstore.com', N'书店管理员', N'正常');
INSERT INTO store_admins (user_id, admin_name, admin_status) VALUES (SCOPE_IDENTITY(), N'王店长', N'正常');
GO

-- 1.3 普通用户（10 人）
DECLARE @uid INT;
DECLARE @idx INT;
DECLARE @name NVARCHAR(50);
DECLARE @names TABLE (id INT IDENTITY, name NVARCHAR(50));

INSERT INTO @names (name) VALUES
(N'buyer_zhou'), (N'buyer_liu'), (N'buyer_chen'), (N'buyer_yang'),
(N'buyer_zhao'), (N'buyer_sun'), (N'buyer_ma'), (N'buyer_hu'),
(N'buyer_lin'), (N'buyer_wu');

DECLARE cur CURSOR FOR SELECT id, name FROM @names ORDER BY id;
OPEN cur;
FETCH NEXT FROM cur INTO @idx, @name;
WHILE @@FETCH_STATUS = 0
BEGIN
    INSERT INTO users (user_name, password_hash, phone, email, user_type, status)
    VALUES (@name, N'$2a$10$hashed_placeholder',
            N'135' + RIGHT('00000' + CAST(@idx AS NVARCHAR), 4) + N'0000',
            @name + N'@test.com', N'普通用户', N'正常');
    SET @uid = SCOPE_IDENTITY();

    INSERT INTO ordinary_users (user_id, nickname, level, total_points, available_points, continuous_checkin_days)
    VALUES (@uid, N'用户' + @name,
            CASE WHEN @idx <= 3 THEN 3 WHEN @idx <= 6 THEN 2 ELSE 1 END,
            @idx * 500, @idx * 300, @idx % 7);

    FETCH NEXT FROM cur INTO @idx, @name;
END
CLOSE cur;
DEALLOCATE cur;
GO

-- 1.4 被封禁的普通用户（测试封禁逻辑）
INSERT INTO users (user_name, password_hash, phone, email, user_type, status)
VALUES (N'buyer_blocked', N'$2a$10$hashed_placeholder', N'13599990000', N'blocked@test.com', N'普通用户', N'封禁');
INSERT INTO ordinary_users (user_id, nickname, level, total_points, available_points, continuous_checkin_days)
VALUES (SCOPE_IDENTITY(), N'被封禁用户', 1, 100, 100, 0);
GO

-- ============================================================
-- 2. 店铺数据（3 个店铺）
-- ============================================================
DECLARE @s1 INT = (SELECT user_id FROM users WHERE user_name = N'seller_zhang');
DECLARE @s2 INT = (SELECT user_id FROM users WHERE user_name = N'seller_li');
DECLARE @s3 INT = (SELECT user_id FROM users WHERE user_name = N'seller_wang');

INSERT INTO stores (store_name, user_id, description, status) VALUES
(N'科技图书旗舰店', @s1, N'专注计算机与人工智能领域图书', N'正常'),
(N'人文社科书店',   @s2, N'文史哲经典读物，涵盖古今中外',   N'正常'),
(N'考试教辅专营',   @s3, N'考研、考公、考证一站式备考资料', N'正常');
GO

-- ============================================================
-- 3. 图书分类（平台 6 个）
-- ============================================================
INSERT INTO book_categories (category_name, description, status) VALUES
(N'编程语言', N'Java/Python/C++/Go/Rust 等', N'启用'),
(N'人工智能', N'机器学习、深度学习、NLP',     N'启用'),
(N'中国文学', N'古典与现当代',               N'启用'),
(N'外国文学', N'翻译文学经典',               N'启用'),
(N'考研',     N'研究生入学考试',             N'启用'),
(N'考公',     N'公务员考试',                 N'启用');
GO

-- ============================================================
-- 4. 图书资料（24 本）+ 图书商品（分配到 3 个店铺）
-- ============================================================
DECLARE @cat_prog INT = (SELECT category_id FROM book_categories WHERE category_name = N'编程语言');
DECLARE @cat_ai   INT = (SELECT category_id FROM book_categories WHERE category_name = N'人工智能');
DECLARE @cat_zn   INT = (SELECT category_id FROM book_categories WHERE category_name = N'中国文学');
DECLARE @cat_wai  INT = (SELECT category_id FROM book_categories WHERE category_name = N'外国文学');
DECLARE @cat_ky   INT = (SELECT category_id FROM book_categories WHERE category_name = N'考研');
DECLARE @cat_gk   INT = (SELECT category_id FROM book_categories WHERE category_name = N'考公');

DECLARE @st1 INT = (SELECT store_id FROM stores WHERE store_name = N'科技图书旗舰店');
DECLARE @st2 INT = (SELECT store_id FROM stores WHERE store_name = N'人文社科书店');
DECLARE @st3 INT = (SELECT store_id FROM stores WHERE store_name = N'考试教辅专营');

-- 4.1 编程语言 - 店铺1
INSERT INTO book_infos (category_id, book_name, author, publisher, ISBN, publish_date, description, cover_image) VALUES
(@cat_prog, N'深入理解Java虚拟机',   N'周志明',        N'机械工业出版社', N'978-7-111-34966-1', '2019-12-01', N'JVM原理与调优的权威指南，涵盖内存管理、类加载、编译优化等核心主题。', N'/images/jvm.jpg'),
(@cat_prog, N'Python编程：从入门到实践', N'Eric Matthes', N'人民邮电出版社', N'978-7-115-54602-7', '2020-10-01', N'零基础学Python的最佳选择，项目驱动式学习。',                N'/images/python.jpg'),
(@cat_prog, N'算法导论',              N'Thomas Cormen', N'机械工业出版社', N'978-7-111-40701-0', '2013-01-01', N'计算机算法领域的经典教材，涵盖排序、图算法、动态规划等。',          N'/images/algo.jpg'),
(@cat_prog, N'深入浅出Vue.js',        N'刘博文',        N'人民邮电出版社', N'978-7-115-48935-7', '2019-06-01', N'从响应式原理到虚拟DOM，全面解读Vue.js内部机制。',               N'/images/vue.jpg'),
(@cat_prog, N'Go语言程序设计',         N'Alan Donovan',  N'机械工业出版社', N'978-7-111-55198-2', '2017-05-01', N'Go语言圣经，K&R风格写作。',                                N'/images/go.jpg'),
(@cat_prog, N'Rust权威指南',           N'Steve Klabnik', N'电子工业出版社', N'978-7-121-35314-1', '2019-03-01', N'Rust官方团队核心成员撰写。',                                 N'/images/rust.jpg');

-- 4.2 人工智能 - 店铺1
INSERT INTO book_infos (category_id, book_name, author, publisher, ISBN, publish_date, description, cover_image) VALUES
(@cat_ai, N'深度学习',           N'Ian Goodfellow',  N'人民邮电出版社', N'978-7-115-46147-1', '2017-08-01', N'深度学习领域奠基性教材，被誉为“花书”。',            N'/images/dl.jpg'),
(@cat_ai, N'机器学习实战',        N'Peter Harrington', N'人民邮电出版社', N'978-7-115-34904-6', '2013-06-01', N'基于Python的机器学习实践指南。',                  N'/images/ml.jpg'),
(@cat_ai, N'自然语言处理综论',     N'Dan Jurafsky',   N'电子工业出版社', N'978-7-121-26378-1', '2015-04-01', N'NLP领域全面而系统的参考书。',                     N'/images/nlp.jpg'),
(@cat_ai, N'PyTorch深度学习实战', N'Eli Stevens',    N'人民邮电出版社', N'978-7-115-53141-7', '2020-08-01', N'从零开始掌握PyTorch框架。',                       N'/images/pytorch.jpg');

-- 4.3 中国文学 - 店铺2
INSERT INTO book_infos (category_id, book_name, author, publisher, ISBN, publish_date, description, cover_image) VALUES
(@cat_zn, N'红楼梦',    N'曹雪芹', N'人民文学出版社',     N'978-7-02-000220-7', '2008-07-01', N'中国古典四大名著之首。',                  N'/images/hlm.jpg'),
(@cat_zn, N'活着',      N'余华',   N'作家出版社',         N'978-7-5063-6543-7', '2012-08-01', N'讲述了农村人福贵悲惨的人生遭遇。',          N'/images/hz.jpg'),
(@cat_zn, N'三体',      N'刘慈欣', N'重庆出版社',         N'978-7-5366-9293-0', '2008-01-01', N'科幻巨著，雨果奖获奖作品。',               N'/images/st.jpg'),
(@cat_zn, N'围城',      N'钱钟书', N'人民文学出版社',     N'978-7-02-002475-9', '1991-02-01', N'中国现代文学经典，钱钟书代表作。',          N'/images/wc.jpg'),
(@cat_zn, N'平凡的世界', N'路遥',   N'北京十月文艺出版社', N'978-7-5302-1675-0', '2012-03-01', N'茅盾文学奖获奖作品。',                    N'/images/pf.jpg');

-- 4.4 外国文学 - 店铺2
INSERT INTO book_infos (category_id, book_name, author, publisher, ISBN, publish_date, description, cover_image) VALUES
(@cat_wai, N'百年孤独',   N'加西亚·马尔克斯', N'南海出版公司',       N'978-7-5442-5399-4', '2011-06-01', N'魔幻现实主义文学的代表作。',            N'/images/bngd.jpg'),
(@cat_wai, N'1984',       N'George Orwell',   N'北京十月文艺出版社', N'978-7-5302-1029-1', '2010-04-01', N'反乌托邦经典之作。',                   N'/images/1984.jpg'),
(@cat_wai, N'挪威的森林', N'村上春树',        N'上海译文出版社',     N'978-7-5327-4618-4', '2007-07-01', N'村上春树最为著名的长篇小说。',          N'/images/nw.jpg'),
(@cat_wai, N'小王子',     N'圣埃克苏佩里',    N'上海译文出版社',     N'978-7-5327-5924-9', '2013-01-01', N'永不过时的童话经典。',                 N'/images/xwz.jpg');

-- 4.5 考研 - 店铺3
INSERT INTO book_infos (category_id, book_name, author, publisher, ISBN, publish_date, description, cover_image) VALUES
(@cat_ky, N'考研英语词汇红宝书', N'俞敏洪', N'群言出版社',           N'978-7-80080-931-8', '2023-01-01', N'考研英语词汇必备。',     N'/images/ky_en.jpg'),
(@cat_ky, N'考研数学复习全书',   N'李永乐', N'国家行政学院出版社',   N'978-7-5150-2530-1', '2023-01-01', N'考研数学全面复习用书。', N'/images/ky_math.jpg'),
(@cat_ky, N'考研政治1000题',     N'肖秀荣', N'北京航空航天大学出版社', N'978-7-5124-3576-8', '2023-04-01', N'刷题提分利器。',         N'/images/ky_zz.jpg');

-- 4.6 考公 - 店铺3
INSERT INTO book_infos (category_id, book_name, author, publisher, ISBN, publish_date, description, cover_image) VALUES
(@cat_gk, N'行政职业能力测验', N'李永新', N'人民日报出版社', N'978-7-5115-6602-1', '2023-02-01', N'行测备考权威教材。',   N'/images/xc.jpg'),
(@cat_gk, N'申论范文宝典',     N'半月谈', N'新华出版社',     N'978-7-5166-5403-1', '2023-02-01', N'高分申论范文精讲。',   N'/images/sl.jpg');
GO

-- ============================================================
-- 4.7 为每个 book_info 创建 book_item（每个 INSERT 独立子查询，不依赖变量）
-- ============================================================

-- 编程语言 - 店铺1
INSERT INTO book_items (book_info_id, store_id, price, stock, locked_stock, sales_count, status)
SELECT bi.book_info_id, (SELECT store_id FROM stores WHERE store_name = N'科技图书旗舰店'),
       CASE bi.book_name
            WHEN N'深入理解Java虚拟机' THEN 89.00
            WHEN N'Python编程：从入门到实践' THEN 69.00
            WHEN N'算法导论' THEN 128.00
            WHEN N'深入浅出Vue.js' THEN 79.00
            WHEN N'Go语言程序设计' THEN 65.00
            WHEN N'Rust权威指南' THEN 99.00 END,
       CASE WHEN bi.book_name = N'Python编程：从入门到实践' THEN 200 ELSE 50 END,
       0,
       CASE WHEN bi.book_name = N'Python编程：从入门到实践' THEN 856
            WHEN bi.book_name = N'算法导论' THEN 423
            ELSE ABS(CHECKSUM(NEWID()) % 100) END,
       N'在售'
FROM book_infos bi
WHERE bi.category_id = (SELECT category_id FROM book_categories WHERE category_name = N'编程语言');
GO

-- 人工智能 - 店铺1
INSERT INTO book_items (book_info_id, store_id, price, stock, locked_stock, sales_count, status)
SELECT bi.book_info_id, (SELECT store_id FROM stores WHERE store_name = N'科技图书旗舰店'),
       CASE bi.book_name
            WHEN N'深度学习' THEN 168.00
            WHEN N'机器学习实战' THEN 79.00
            WHEN N'自然语言处理综论' THEN 138.00
            WHEN N'PyTorch深度学习实战' THEN 89.00 END,
       45, 0,
       CASE WHEN bi.book_name = N'深度学习' THEN 678
            WHEN bi.book_name = N'机器学习实战' THEN 512
            ELSE ABS(CHECKSUM(NEWID()) % 80) END,
       N'在售'
FROM book_infos bi
WHERE bi.category_id = (SELECT category_id FROM book_categories WHERE category_name = N'人工智能');
GO

-- 中国文学 - 店铺2
INSERT INTO book_items (book_info_id, store_id, price, stock, locked_stock, sales_count, status)
SELECT bi.book_info_id, (SELECT store_id FROM stores WHERE store_name = N'人文社科书店'),
       CASE bi.book_name
            WHEN N'红楼梦' THEN 59.80 WHEN N'活着' THEN 35.00
            WHEN N'三体' THEN 93.00   WHEN N'围城' THEN 36.00
            WHEN N'平凡的世界' THEN 79.80 END,
       60, 0,
       CASE WHEN bi.book_name = N'三体' THEN 1234
            WHEN bi.book_name = N'活着' THEN 987
            WHEN bi.book_name = N'红楼梦' THEN 756
            ELSE ABS(CHECKSUM(NEWID()) % 200) END,
       N'在售'
FROM book_infos bi
WHERE bi.category_id = (SELECT category_id FROM book_categories WHERE category_name = N'中国文学');
GO

-- 外国文学 - 店铺2
INSERT INTO book_items (book_info_id, store_id, price, stock, locked_stock, sales_count, status)
SELECT bi.book_info_id, (SELECT store_id FROM stores WHERE store_name = N'人文社科书店'),
       CASE bi.book_name
            WHEN N'百年孤独' THEN 55.00   WHEN N'1984' THEN 32.00
            WHEN N'挪威的森林' THEN 36.00 WHEN N'小王子' THEN 28.00 END,
       50, 0,
       CASE WHEN bi.book_name = N'百年孤独' THEN 543
            WHEN bi.book_name = N'1984' THEN 432
            ELSE ABS(CHECKSUM(NEWID()) % 100) END,
       N'在售'
FROM book_infos bi
WHERE bi.category_id = (SELECT category_id FROM book_categories WHERE category_name = N'外国文学');
GO

-- 考研 - 店铺3
INSERT INTO book_items (book_info_id, store_id, price, stock, locked_stock, sales_count, status)
SELECT bi.book_info_id, (SELECT store_id FROM stores WHERE store_name = N'考试教辅专营'),
       CASE WHEN bi.book_name LIKE N'考研英语%' THEN 46.00
            WHEN bi.book_name LIKE N'考研数学%' THEN 72.00
            WHEN bi.book_name LIKE N'考研政治%' THEN 58.00 END,
       100, 0,
       CASE WHEN bi.book_name LIKE N'考研英语%' THEN 2345
            WHEN bi.book_name LIKE N'考研数学%' THEN 1987
            WHEN bi.book_name LIKE N'考研政治%' THEN 1654 END,
       N'在售'
FROM book_infos bi
WHERE bi.category_id = (SELECT category_id FROM book_categories WHERE category_name = N'考研');
GO

-- 考公 - 店铺3
INSERT INTO book_items (book_info_id, store_id, price, stock, locked_stock, sales_count, status)
SELECT bi.book_info_id, (SELECT store_id FROM stores WHERE store_name = N'考试教辅专营'),
       CASE WHEN bi.book_name LIKE N'行政职业%' THEN 52.00
            WHEN bi.book_name LIKE N'申论%' THEN 38.00 END,
       80, 0,
       CASE WHEN bi.book_name LIKE N'行政职业%' THEN 3456 ELSE 2876 END,
       N'在售'
FROM book_infos bi
WHERE bi.category_id = (SELECT category_id FROM book_categories WHERE category_name = N'考公');
GO

-- 把店铺 1 中序号最小的那本 book_item 设为下架（测试边界条件）
UPDATE TOP (1) book_items SET status = N'下架', stock = 0
WHERE store_id = (SELECT store_id FROM stores WHERE store_name = N'科技图书旗舰店')
  AND status = N'在售';
GO

-- ============================================================
-- 5. 收货地址
-- ============================================================
DECLARE @u1 INT = (SELECT user_id FROM users WHERE user_name = N'buyer_zhou');
DECLARE @u2 INT = (SELECT user_id FROM users WHERE user_name = N'buyer_liu');

INSERT INTO shipping_addresses (user_id, receiver_name, phone, province, city, district, detail, is_default) VALUES
(@u1, N'周同学', N'13800000001', N'北京市', N'北京市', N'海淀区', N'中关村大街 1 号', 1),
(@u1, N'周同学', N'13800000001', N'广东省', N'深圳市', N'南山区', N'科技园路 88 号',   0),
(@u2, N'刘女士', N'13800000002', N'上海市', N'上海市', N'浦东新区', N'张江高科技园区 100 号', 1);
GO

-- ============================================================
-- 6. 订单（覆盖全部四种状态 + 一个订单含多本图书）
-- ============================================================
DECLARE @zhou INT = (SELECT user_id FROM users WHERE user_name = N'buyer_zhou');
DECLARE @liu  INT = (SELECT user_id FROM users WHERE user_name = N'buyer_liu');

-- 6.1 已完成订单（zhou - 购买了两本书）
INSERT INTO orders (user_id, order_no, total_amount, discount_amount, actual_amount,
                    order_status, payment_status,
                    receiver_name, receiver_phone, receiver_addr,
                    created_time, paid_time)
VALUES (@zhou, N'ORD202606280001', 158.00, 0, 158.00,
        N'已完成', N'已支付',
        N'周同学', N'13800000001', N'北京市海淀区中关村大街 1 号',
        '2026-06-28 10:30:00', '2026-06-28 10:35:00');
DECLARE @ord1 INT = SCOPE_IDENTITY();

-- 取两本不同店铺的书
DECLARE @bk1 INT = (SELECT MIN(book_item_id) FROM book_items WHERE status = N'在售' AND store_id = (SELECT store_id FROM stores WHERE store_name = N'科技图书旗舰店'));
DECLARE @bk2 INT = (SELECT MIN(book_item_id) FROM book_items WHERE status = N'在售' AND store_id = (SELECT store_id FROM stores WHERE store_name = N'人文社科书店') AND book_item_id > @bk1);

INSERT INTO order_items (order_id, book_item_id, quantity, unit_price, subtotal) VALUES
(@ord1, @bk1, 1, 89.00, 89.00),
(@ord1, @bk2, 1, 69.00, 69.00);

-- 6.2 已完成订单（liu - 使用代金券）
INSERT INTO orders (user_id, order_no, total_amount, discount_amount, actual_amount,
                    order_status, payment_status,
                    receiver_name, receiver_phone, receiver_addr,
                    created_time, paid_time)
VALUES (@liu, N'ORD202606280002', 128.00, 10.00, 118.00,
        N'已完成', N'已支付',
        N'刘女士', N'13800000002', N'上海市浦东新区张江高科技园区 100 号',
        '2026-06-28 14:00:00', '2026-06-28 14:08:00');
DECLARE @ord2 INT = SCOPE_IDENTITY();

DECLARE @bk3 INT = (SELECT MIN(book_item_id) FROM book_items WHERE status = N'在售' AND store_id = (SELECT store_id FROM stores WHERE store_name = N'考试教辅专营'));
INSERT INTO order_items (order_id, book_item_id, quantity, unit_price, subtotal) VALUES
(@ord2, @bk3, 1, 128.00, 128.00);

-- 6.3 待支付订单
DECLARE @bk4 INT = (SELECT MIN(book_item_id) FROM book_items WHERE status = N'在售' AND book_item_id NOT IN (@bk1, @bk2, @bk3));

INSERT INTO orders (user_id, order_no, total_amount, discount_amount, actual_amount,
                    order_status, payment_status,
                    receiver_name, receiver_phone, receiver_addr, created_time)
VALUES (@zhou, N'ORD202607010001', 89.00, 0, 89.00,
        N'待支付', N'未支付',
        N'周同学', N'13800000001', N'北京市海淀区中关村大街 1 号',
        '2026-07-01 09:15:00');
DECLARE @ord3 INT = SCOPE_IDENTITY();
INSERT INTO order_items (order_id, book_item_id, quantity, unit_price, subtotal) VALUES
(@ord3, @bk4, 1, 89.00, 89.00);

-- 6.4 已退款订单
INSERT INTO orders (user_id, order_no, total_amount, discount_amount, actual_amount,
                    order_status, payment_status,
                    receiver_name, receiver_phone, receiver_addr,
                    created_time, paid_time)
VALUES (@liu, N'ORD202606200001', 59.80, 0, 59.80,
        N'已退款', N'已退款',
        N'刘女士', N'13800000002', N'上海市浦东新区张江高科技园区 100 号',
        '2026-06-20 11:00:00', '2026-06-20 11:06:00');
DECLARE @ord4 INT = SCOPE_IDENTITY();
INSERT INTO order_items (order_id, book_item_id, quantity, unit_price, subtotal) VALUES
(@ord4, @bk2, 1, 59.80, 59.80);
GO

-- ============================================================
-- 7. 支付记录
-- ============================================================
DECLARE @z INT = (SELECT user_id FROM users WHERE user_name = N'buyer_zhou');
DECLARE @l INT = (SELECT user_id FROM users WHERE user_name = N'buyer_liu');
DECLARE @po1 INT = (SELECT order_id FROM orders WHERE order_no = N'ORD202606280001');
DECLARE @po2 INT = (SELECT order_id FROM orders WHERE order_no = N'ORD202606280002');
DECLARE @po4 INT = (SELECT order_id FROM orders WHERE order_no = N'ORD202606200001');

INSERT INTO payment_records (order_id, user_id, payment_no, amount, payment_method, payment_status, paid_time) VALUES
(@po1, @z, N'PAY202606280001', 158.00, N'微信支付', N'已支付', '2026-06-28 10:35:00'),
(@po2, @l, N'PAY202606280002', 118.00, N'支付宝',   N'已支付', '2026-06-28 14:08:00'),
(@po4, @l, N'PAY202606200001',  59.80, N'微信支付', N'已支付', '2026-06-20 11:06:00');
GO

-- ============================================================
-- 8. 退款记录
-- ============================================================
DECLARE @ro4 INT = (SELECT order_id FROM orders WHERE order_no = N'ORD202606200001');
DECLARE @ru4 INT = (SELECT user_id FROM users WHERE user_name = N'buyer_liu');
DECLARE @rp4 INT = (SELECT payment_id FROM payment_records WHERE order_id = @ro4);

INSERT INTO refund_records (order_id, user_id, payment_id, refund_no, refund_amount, refund_reason, refund_status, refund_time)
VALUES (@ro4, @ru4, @rp4, N'REF202606210001', 59.80, N'图书印刷质量问题', N'已退款', '2026-06-21 10:00:00');
GO

-- ============================================================
-- 9. 促销活动
-- ============================================================
DECLARE @adm INT = (SELECT user_id FROM users WHERE user_name = N'admin_super');

INSERT INTO promotion_activities (activity_name, activity_type, description, start_time, end_time, status, created_admin) VALUES
(N'每日签到',   N'签到',   N'每日签到得积分，连续7天奖励10元代金券，连续30天奖励50元代金券', '2026-01-01', '2026-12-31', N'进行中', @adm),
(N'618年中大促', N'限时折扣', N'全平台图书折扣活动，参与店铺设置专属优惠',                     '2026-06-15', '2026-07-01', N'已结束', @adm),
(N'暑期阅读季', N'小游戏', N'参与答题赢取平台代金券和店铺券',                                 '2026-07-01', '2026-08-31', N'进行中', @adm);
GO

-- ============================================================
-- 10. 代金券模块
-- ============================================================
DECLARE @act_c INT = (SELECT activity_id FROM promotion_activities WHERE activity_name = N'每日签到');
DECLARE @act_s INT = (SELECT activity_id FROM promotion_activities WHERE activity_name = N'暑期阅读季');
DECLARE @st2  INT = (SELECT store_id FROM stores WHERE store_name = N'人文社科书店');

INSERT INTO coupons (activity_id, coupon_name, coupon_type, store_id, amount, min_amount, valid_start, valid_end, status) VALUES
(@act_c, N'连续7天签到券',     N'平台券', NULL,   10.00,  0.00, '2026-01-01', '2026-12-31', N'启用'),
(@act_c, N'连续30天签到券',    N'平台券', NULL,   50.00,  0.00, '2026-01-01', '2026-12-31', N'启用'),
(@act_s, N'暑期答题10元券',    N'平台券', NULL,   10.00, 50.00, '2026-07-01', '2026-09-01', N'启用'),
(@act_s, N'暑期科幻专享券',    N'店铺券', @st2,    5.00, 30.00, '2026-07-01', '2026-09-01', N'启用');
GO

-- ============================================================
-- 11. 积分兑换奖品
-- ============================================================
DECLARE @adm2 INT = (SELECT user_id FROM users WHERE user_name = N'admin_super');

INSERT INTO point_rewards (reward_name, reward_type, required_points, required_level, stock, manage_admin) VALUES
(N'5元代金券',      N'代金券',   500, 1, 1000, @adm2),
(N'20元代金券',     N'代金券',  2000, 2,  500, @adm2),
(N'精美书签套装',   N'实物',    3000, 3,  200, @adm2),
(N'蓝牙耳机',       N'实物',   10000, 5,   50, @adm2);
GO

-- ============================================================
-- 12. 签到记录（buyer_zhou 连续 4 天）
-- ============================================================
DECLARE @zz INT = (SELECT user_id FROM users WHERE user_name = N'buyer_zhou');
DECLARE @a1 INT = (SELECT activity_id FROM promotion_activities WHERE activity_name = N'每日签到');

INSERT INTO checkin_record (user_id, activity_id, checkin_date, continuous_checkin_days, reward_points) VALUES
(@zz, @a1, '2026-06-27', 3, 5),
(@zz, @a1, '2026-06-28', 4, 5),
(@zz, @a1, '2026-06-29', 5, 5),
(@zz, @a1, '2026-06-30', 6, 5);
GO

-- ============================================================
-- 13. 评价数据
-- ============================================================
DECLARE @zz2 INT = (SELECT user_id FROM users WHERE user_name = N'buyer_zhou');
DECLARE @bk_a INT = (SELECT MIN(book_item_id) FROM book_items WHERE status = N'在售' AND store_id = (SELECT store_id FROM stores WHERE store_name = N'科技图书旗舰店'));
DECLARE @bk_b INT = (SELECT MIN(book_item_id) FROM book_items WHERE status = N'在售' AND store_id = (SELECT store_id FROM stores WHERE store_name = N'人文社科书店'));
DECLARE @oid1 INT = (SELECT order_id FROM orders WHERE order_no = N'ORD202606280001');

INSERT INTO reviews (user_id, book_item_id, order_id, rating, content) VALUES
(@zz2, @bk_a, @oid1, 5, N'经典中的经典，JVM 入门必读。'),
(@zz2, @bk_b, @oid1, 4, N'适合零基础，例子丰富、通俗易懂。');
GO

-- ============================================================
-- 14. 积分流水
-- ============================================================
DECLARE @zz3 INT = (SELECT user_id FROM users WHERE user_name = N'buyer_zhou');
DECLARE @li3 INT = (SELECT user_id FROM users WHERE user_name = N'buyer_liu');
DECLARE @qo1 INT = (SELECT order_id FROM orders WHERE order_no = N'ORD202606280001');
DECLARE @qo2 INT = (SELECT order_id FROM orders WHERE order_no = N'ORD202606280002');

INSERT INTO points_records (user_id, points_change, reason, related_id) VALUES
(@zz3, 158, N'购买', @qo1),
(@zz3,   5, N'签到', 1),
(@li3, 118, N'购买', @qo2);
GO

-- ============================================================
-- 15. 浏览记录（给推荐算法提供数据）
-- ============================================================
DECLARE @zz4 INT = (SELECT user_id FROM users WHERE user_name = N'buyer_zhou');
DECLARE @b1 INT = (SELECT MIN(book_item_id) FROM book_items WHERE status = N'在售');
DECLARE @b2 INT = (SELECT MIN(book_item_id) FROM book_items WHERE status = N'在售' AND book_item_id > @b1);
DECLARE @b3 INT = (SELECT MIN(book_item_id) FROM book_items WHERE status = N'在售' AND book_item_id > @b2);

INSERT INTO browse_history (user_id, book_item_id, browse_duration) VALUES
(@zz4, @b1, 120),
(@zz4, @b2,  45),
(@zz4, @b3,  30);

PRINT N'================================';
PRINT N'测试数据全部导入完成';
PRINT N'================================';
GO
