CREATE OR ALTER TRIGGER trg_AfterBlacklists ON store_blacklists
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE u SET status = N'封禁'
    FROM users u
    JOIN (
        SELECT sb.user_id
        FROM store_blacklists sb
        JOIN (SELECT DISTINCT user_id FROM inserted) i ON i.user_id = sb.user_id
        GROUP BY sb.user_id
        HAVING COUNT(DISTINCT sb.store_id) >= 10
    ) blocked ON blocked.user_id = u.user_id
    WHERE u.status = N'正常';
END;
GO

CREATE OR ALTER TRIGGER trg_AutoLevelUp ON ordinary_users
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF NOT UPDATE(total_points) RETURN;
    UPDATE ou
    SET level = CASE
        WHEN i.total_points >= 10000 THEN 5
        WHEN i.total_points >= 5000 THEN 4
        WHEN i.total_points >= 2500 THEN 3
        WHEN i.total_points >= 1250 THEN 2
        ELSE 1
    END
    FROM ordinary_users ou
    JOIN inserted i ON i.user_id = ou.user_id
    WHERE ou.level <> CASE
        WHEN i.total_points >= 10000 THEN 5
        WHEN i.total_points >= 5000 THEN 4
        WHEN i.total_points >= 2500 THEN 3
        WHEN i.total_points >= 1250 THEN 2
        ELSE 1
    END;
END
GO
