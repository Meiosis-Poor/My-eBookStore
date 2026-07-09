USE My_eBookStore;

DECLARE @pwd VARCHAR(255) = '$2b$12$AJpMibOMZgtXO2mp1ceVue8JguWrXeWq43Qj42PpRtNwLZriJpBD2';

IF NOT EXISTS (SELECT 1 FROM users WHERE user_name = N'reader_demo')
BEGIN
    INSERT INTO users(user_name, password_hash, phone, email, user_type, status)
    VALUES (N'reader_demo', @pwd, '13810000001', N'reader_demo@test.local', N'普通用户', N'正常');
    INSERT INTO ordinary_users(user_id, nickname, level, total_points, available_points, continuous_checkin_days)
    VALUES (SCOPE_IDENTITY(), N'读者测试号', 3, 300, 300, 2);
END
ELSE
BEGIN
    UPDATE users
    SET password_hash = @pwd, user_type = N'普通用户', status = N'正常'
    WHERE user_name = N'reader_demo';
    IF NOT EXISTS (SELECT 1 FROM ordinary_users WHERE user_id = (SELECT user_id FROM users WHERE user_name = N'reader_demo'))
        INSERT INTO ordinary_users(user_id, nickname, level, total_points, available_points, continuous_checkin_days)
        SELECT user_id, N'读者测试号', 3, 300, 300, 2 FROM users WHERE user_name = N'reader_demo';
END

IF NOT EXISTS (SELECT 1 FROM users WHERE user_name = N'seller_demo')
BEGIN
    INSERT INTO users(user_name, password_hash, phone, email, user_type, status)
    VALUES (N'seller_demo', @pwd, '13810000002', N'seller_demo@test.local', N'书店管理员', N'正常');
    INSERT INTO store_admins(user_id, admin_name, admin_status)
    VALUES (SCOPE_IDENTITY(), N'卖家测试号', N'正常');
END
ELSE
BEGIN
    UPDATE users
    SET password_hash = @pwd, user_type = N'书店管理员', status = N'正常'
    WHERE user_name = N'seller_demo';
    IF NOT EXISTS (SELECT 1 FROM store_admins WHERE user_id = (SELECT user_id FROM users WHERE user_name = N'seller_demo'))
        INSERT INTO store_admins(user_id, admin_name, admin_status)
        SELECT user_id, N'卖家测试号', N'正常' FROM users WHERE user_name = N'seller_demo';
END

IF NOT EXISTS (SELECT 1 FROM users WHERE user_name = N'admin')
BEGIN
    INSERT INTO users(user_name, password_hash, phone, email, user_type, status)
    VALUES (N'admin', @pwd, '13810000003', N'admin@test.local', N'系统管理员', N'正常');
    INSERT INTO system_admins(user_id, admin_name)
    VALUES (SCOPE_IDENTITY(), N'平台管理员测试号');
END
ELSE
BEGIN
    UPDATE users
    SET password_hash = @pwd, user_type = N'系统管理员', status = N'正常'
    WHERE user_name = N'admin';
    IF NOT EXISTS (SELECT 1 FROM system_admins WHERE user_id = (SELECT user_id FROM users WHERE user_name = N'admin'))
        INSERT INTO system_admins(user_id, admin_name)
        SELECT user_id, N'平台管理员测试号' FROM users WHERE user_name = N'admin';
END

DECLARE @reader INT = (SELECT user_id FROM users WHERE user_name = N'reader_demo');
DECLARE @seller INT = (SELECT user_id FROM users WHERE user_name = N'seller_demo');
DECLARE @admin INT = (SELECT user_id FROM users WHERE user_name = N'admin');

IF NOT EXISTS (SELECT 1 FROM stores WHERE store_name = N'测试书店')
    INSERT INTO stores(store_name, user_id, description, status)
    VALUES (N'测试书店', @seller, N'前后端联调用测试店铺', N'正常');
ELSE
    UPDATE stores SET user_id = @seller, status = N'正常', description = N'前后端联调用测试店铺'
    WHERE store_name = N'测试书店';

DECLARE @store INT = (SELECT store_id FROM stores WHERE store_name = N'测试书店');

IF NOT EXISTS (SELECT 1 FROM book_categories WHERE category_name = N'测试分类')
    INSERT INTO book_categories(category_name, description, status)
    VALUES (N'测试分类', N'联调测试图书分类', N'启用');
ELSE
    UPDATE book_categories SET status = N'启用' WHERE category_name = N'测试分类';

DECLARE @category INT = (SELECT category_id FROM book_categories WHERE category_name = N'测试分类');

IF NOT EXISTS (SELECT 1 FROM book_infos WHERE ISBN = N'TEST-BOOK-001')
    INSERT INTO book_infos(category_id, book_name, author, publisher, ISBN, publish_date, description, cover_image, status)
    VALUES (@category, N'数据库联调指南', N'课程设计小组', N'My-eBookStore Press', N'TEST-BOOK-001', '2026-07-01', N'用于测试购物车、下单和支付链路。', N'📘', N'正常');
ELSE
    UPDATE book_infos SET category_id = @category, book_name = N'数据库联调指南', status = N'正常', cover_image = N'📘'
    WHERE ISBN = N'TEST-BOOK-001';

IF NOT EXISTS (SELECT 1 FROM book_infos WHERE ISBN = N'TEST-BOOK-002')
    INSERT INTO book_infos(category_id, book_name, author, publisher, ISBN, publish_date, description, cover_image, status)
    VALUES (@category, N'FastAPI 网上书店实战', N'课程设计小组', N'My-eBookStore Press', N'TEST-BOOK-002', '2026-07-02', N'用于测试推荐、搜索和订单展示。', N'📗', N'正常');
ELSE
    UPDATE book_infos SET category_id = @category, book_name = N'FastAPI 网上书店实战', status = N'正常', cover_image = N'📗'
    WHERE ISBN = N'TEST-BOOK-002';

IF NOT EXISTS (SELECT 1 FROM book_infos WHERE ISBN = N'TEST-BOOK-003')
    INSERT INTO book_infos(category_id, book_name, author, publisher, ISBN, publish_date, description, cover_image, status)
    VALUES (@category, N'SQL Server 事务测试', N'课程设计小组', N'My-eBookStore Press', N'TEST-BOOK-003', '2026-07-03', N'用于测试支付后库存、销量和积分一致性。', N'📙', N'正常');
ELSE
    UPDATE book_infos SET category_id = @category, book_name = N'SQL Server 事务测试', status = N'正常', cover_image = N'📙'
    WHERE ISBN = N'TEST-BOOK-003';

DECLARE @info1 INT = (SELECT book_info_id FROM book_infos WHERE ISBN = N'TEST-BOOK-001');
DECLARE @info2 INT = (SELECT book_info_id FROM book_infos WHERE ISBN = N'TEST-BOOK-002');
DECLARE @info3 INT = (SELECT book_info_id FROM book_infos WHERE ISBN = N'TEST-BOOK-003');

IF NOT EXISTS (SELECT 1 FROM book_items WHERE book_info_id = @info1 AND store_id = @store)
    INSERT INTO book_items(book_info_id, store_id, price, stock, locked_stock, sales_count, status)
    VALUES (@info1, @store, 59.90, 50, 0, 12, N'在售');
ELSE
    UPDATE book_items SET price = 59.90, stock = CASE WHEN stock < 20 THEN 50 ELSE stock END, status = N'在售'
    WHERE book_info_id = @info1 AND store_id = @store;

IF NOT EXISTS (SELECT 1 FROM book_items WHERE book_info_id = @info2 AND store_id = @store)
    INSERT INTO book_items(book_info_id, store_id, price, stock, locked_stock, sales_count, status)
    VALUES (@info2, @store, 79.00, 50, 0, 25, N'在售');
ELSE
    UPDATE book_items SET price = 79.00, stock = CASE WHEN stock < 20 THEN 50 ELSE stock END, status = N'在售'
    WHERE book_info_id = @info2 AND store_id = @store;

IF NOT EXISTS (SELECT 1 FROM book_items WHERE book_info_id = @info3 AND store_id = @store)
    INSERT INTO book_items(book_info_id, store_id, price, stock, locked_stock, sales_count, status)
    VALUES (@info3, @store, 88.00, 50, 0, 18, N'在售');
ELSE
    UPDATE book_items SET price = 88.00, stock = CASE WHEN stock < 20 THEN 50 ELSE stock END, status = N'在售'
    WHERE book_info_id = @info3 AND store_id = @store;

DECLARE @book1 INT = (SELECT book_item_id FROM book_items WHERE book_info_id = @info1 AND store_id = @store);
DECLARE @book2 INT = (SELECT book_item_id FROM book_items WHERE book_info_id = @info2 AND store_id = @store);
DECLARE @book3 INT = (SELECT book_item_id FROM book_items WHERE book_info_id = @info3 AND store_id = @store);

IF NOT EXISTS (SELECT 1 FROM shipping_addresses WHERE user_id = @reader AND detail = N'联调测试地址 1 号')
    INSERT INTO shipping_addresses(user_id, receiver_name, phone, province, city, district, detail, is_default)
    VALUES (@reader, N'读者测试号', '13810000001', N'测试省', N'测试市', N'测试区', N'联调测试地址 1 号', 1);

DELETE FROM cart_items WHERE user_id = @reader AND book_item_id IN (@book1, @book2, @book3);
INSERT INTO cart_items(user_id, book_item_id, quantity) VALUES (@reader, @book1, 1);

DECLARE @addr NVARCHAR(200) = N'测试省测试市测试区联调测试地址 1 号';

IF NOT EXISTS (SELECT 1 FROM orders WHERE order_no = N'TEST-PENDING-001')
BEGIN
    INSERT INTO orders(user_id, order_no, total_amount, discount_amount, actual_amount, order_status, payment_status,
                       receiver_name, receiver_phone, receiver_addr)
    VALUES (@reader, N'TEST-PENDING-001', 79.00, 0, 79.00, N'待支付', N'未支付',
            N'读者测试号', '13810000001', @addr);
END
ELSE
BEGIN
    UPDATE orders
    SET user_id = @reader, total_amount = 79.00, discount_amount = 0, actual_amount = 79.00,
        order_status = N'待支付', payment_status = N'未支付', paid_time = NULL,
        receiver_name = N'读者测试号', receiver_phone = '13810000001', receiver_addr = @addr
    WHERE order_no = N'TEST-PENDING-001';
END

DECLARE @pendingOrder INT = (SELECT order_id FROM orders WHERE order_no = N'TEST-PENDING-001');
DELETE FROM order_items WHERE order_id = @pendingOrder;
INSERT INTO order_items(order_id, book_item_id, quantity, unit_price, subtotal)
VALUES (@pendingOrder, @book2, 1, 79.00, 79.00);
DELETE FROM payment_records WHERE order_id = @pendingOrder;

IF NOT EXISTS (SELECT 1 FROM orders WHERE order_no = N'TEST-PAID-001')
BEGIN
    INSERT INTO orders(user_id, order_no, total_amount, discount_amount, actual_amount, order_status, payment_status,
                       receiver_name, receiver_phone, receiver_addr, paid_time)
    VALUES (@reader, N'TEST-PAID-001', 88.00, 0, 88.00, N'已完成', N'已支付',
            N'读者测试号', '13810000001', @addr, SYSDATETIME());
END
ELSE
BEGIN
    UPDATE orders
    SET user_id = @reader, total_amount = 88.00, discount_amount = 0, actual_amount = 88.00,
        order_status = N'已完成', payment_status = N'已支付',
        receiver_name = N'读者测试号', receiver_phone = '13810000001', receiver_addr = @addr,
        paid_time = COALESCE(paid_time, SYSDATETIME())
    WHERE order_no = N'TEST-PAID-001';
END

DECLARE @paidOrder INT = (SELECT order_id FROM orders WHERE order_no = N'TEST-PAID-001');
DELETE FROM order_items WHERE order_id = @paidOrder;
INSERT INTO order_items(order_id, book_item_id, quantity, unit_price, subtotal)
VALUES (@paidOrder, @book3, 1, 88.00, 88.00);

IF NOT EXISTS (SELECT 1 FROM payment_records WHERE payment_no = N'TEST-PAY-001')
    INSERT INTO payment_records(order_id, user_id, payment_no, amount, payment_method, payment_status)
    VALUES (@paidOrder, @reader, N'TEST-PAY-001', 88.00, N'支付宝', N'未支付');

UPDATE payment_records
SET order_id = @paidOrder, user_id = @reader, amount = 88.00, payment_method = N'支付宝',
    payment_status = N'已支付', paid_time = COALESCE(paid_time, SYSDATETIME())
WHERE payment_no = N'TEST-PAY-001';

IF NOT EXISTS (SELECT 1 FROM points_records WHERE user_id = @reader AND reason = N'购买' AND related_id = @paidOrder)
    INSERT INTO points_records(user_id, points_change, reason, related_id)
    VALUES (@reader, 88, N'购买', @paidOrder);

PRINT N'99_test_seed.sql completed: reader_demo/seller_demo/admin password Demo123';
