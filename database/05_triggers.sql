USE My_eBookStore;
GO

CREATE TRIGGER trg_AfterBlacklists ON store_blacklists
AFTER INSERT
AS
BEGIN
	SET NOCOUNT ON;

	DECLARE @user_id INT;
	DECLARE @count INT;

	SELECT @user_id=user_id FROM inserted;

	IF(
		SELECT COUNT(DISTINCT store_id)
		FROM store_blacklists
		WHERE user_id=@user_id
	)>=10
		UPDATE users
		SET status=N'·â½û'
		WHERE user_id=@user_id AND status=N'Õý³£';
END;
GO

CREATE TRIGGER trg_AutoLevelUp ON ordinary_users
AFTER UPDATE
AS
BEGIN
	SET NOCOUNT ON;

	IF NOT UPDATE(total_points)
		RETURN;
	UPDATE ordinary_users
	SET level=CASE
		WHEN inserted.total_points>=10000 THEN 5
		WHEN inserted.total_points>=5000 THEN 4
		WHEN inserted.total_points>=2500 THEN 3
		WHEN inserted.total_points>=1250 THEN 2
		ELSE ou.level
	END
	FROM ordinary_users ou
	JOIN inserted ON ou.user_id=inserted.user_id
	WHERE inserted.total_points>=1250 AND
		ou.level!=CASE
			WHEN inserted.total_points>=10000 THEN 5
			WHEN inserted.total_points>=5000 THEN 4
			WHEN inserted.total_points>=2500 THEN 3
			WHEN inserted.total_points>=1250 THEN 2
			ELSE ou.level
		END;
END
GO	