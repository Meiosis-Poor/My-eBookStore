IF OBJECT_ID(N'dbo.search_history', N'U') IS NULL
BEGIN
    CREATE TABLE search_history(
        search_id INT PRIMARY KEY IDENTITY(1,1),
        user_id INT NOT NULL FOREIGN KEY REFERENCES users(user_id),
        keyword NVARCHAR(200) NOT NULL,
        keyword_embedding NVARCHAR(MAX) NULL,
        created_time DATETIME2 NOT NULL DEFAULT SYSDATETIME()
    );
END;
GO
