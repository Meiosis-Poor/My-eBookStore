USE My_eBookStore;
GO

CREATE NONCLUSTERED INDEX idx_users_username ON users(user_name);
CREATE NONCLUSTERED INDEX idx_users_status ON users(status);
CREATE NONCLUSTERED INDEX idx_users_type ON users(user_type);
CREATE NONCLUSTERED INDEX idx_users_type_status ON users(user_type,status);

CREATE NONCLUSTERED INDEX idx_stores_status ON stores(status);
CREATE NONCLUSTERED INDEX idx_stores_owner ON stores(user_id);

CREATE NONCLUSTERED INDEX idx_bookinfos_cat ON book_infos(category_id);
CREATE NONCLUSTERED INDEX idx_bookinfos_name ON book_infos(book_name);
CREATE NONCLUSTERED INDEX idx_bookinfos_status ON book_infos(status);

CREATE NONCLUSTERED INDEX idx_bookitems_store ON book_items(store_id);
CREATE NONCLUSTERED INDEX idx_bookitems_info ON book_items(book_info_id);
CREATE NONCLUSTERED INDEX idx_bookitems_status ON book_items(status);
CREATE NONCLUSTERED INDEX idx_bookitems_price ON book_items(price);
CREATE NONCLUSTERED INDEX idx_bookitems_sales ON book_items(sales_count DESC);
CREATE NONCLUSTERED INDEX idx_bookitems_store_st ON book_items(store_id,status);

CREATE NONCLUSTERED INDEX idx_cart_user ON cart_items(user_id);

CREATE NONCLUSTERED INDEX idx_orders_user ON orders(user_id);
CREATE NONCLUSTERED INDEX idx_orders_status ON orders(order_status);
CREATE NONCLUSTERED INDEX idx_orders_time ON orders(created_time DESC);
CREATE NONCLUSTERED INDEX idx_orders_user_st ON orders(user_id,order_status);
CREATE NONCLUSTERED INDEX idx_orders_paid ON orders(paid_time DESC);

CREATE NONCLUSTERED INDEX idx_orderitems_order ON order_items(order_id);
CREATE NONCLUSTERED INDEX idx_orderitems_book ON order_items(book_item_id);

CREATE NONCLUSTERED INDEX idx_pay_order ON payment_records(order_id);
CREATE NONCLUSTERED INDEX idx_pay_user ON payment_records(user_id);

CREATE NONCLUSTERED INDEX idx_refund_order ON refund_records(order_id);

CREATE NONCLUSTERED INDEX idx_coupons_activity ON coupons(activity_id);
CREATE NONCLUSTERED INDEX idx_coupons_valid ON coupons(valid_start,valid_end);

CREATE NONCLUSTERED INDEX idx_usercoupons_user ON user_coupons(user_id);
CREATE NONCLUSTERED INDEX idx_usercoupons_order ON user_coupons(order_id) WHERE order_id IS NOT NULL;
CREATE NONCLUSTERED INDEX idx_usercoupons_st ON user_coupons(user_id,status);

CREATE NONCLUSTERED INDEX idx_checkin_user ON checkin_record(user_id);

CREATE NONCLUSTERED INDEX idx_points_user ON points_records(user_id);
CREATE NONCLUSTERED INDEX idx_points_time ON points_records(created_time DESC);

CREATE NONCLUSTERED INDEX idx_browse_user ON browse_history(user_id);
CREATE NONCLUSTERED INDEX idx_browse_time ON browse_history(created_time DESC);

CREATE NONCLUSTERED INDEX idx_reviews_book ON reviews(book_item_id);
CREATE NONCLUSTERED INDEX idx_reviews_user ON reviews(user_id);
CREATE NONCLUSTERED INDEX idx_reviews_order ON reviews(order_id);

CREATE NONCLUSTERED INDEX idx_blacklist_store ON store_blacklists(store_id);
CREATE NONCLUSTERED INDEX idx_blacklist_user ON store_blacklists(user_id);

SELECT name FROM sys.indexes 
WHERE object_id=OBJECT_ID('book_infos') AND is_primary_key=1
GO

CREATE FULLTEXT CATALOG ft AS DEFAULT;
CREATE FULLTEXT INDEX ON book_infos(book_name,description) KEY INDEX PK__book_inf__6CE36DDA19857735 ON ft; --用上面查询的结果替换主键索引名
GO
