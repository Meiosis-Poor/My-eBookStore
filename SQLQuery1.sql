CREATE DATABASE	My_eBookStore;
GO

USE My_eBookStore;
GO

CREATE TABLE users(
	user_id INT PRIMARY KEY IDENTITY(1,1),
	user_name NVARCHAR(50) NOT NULL UNIQUE,
	password_hash VARCHAR(255) NOT NULL,
	phone_number VARCHAR(20) NULL,
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
	continous_checkin_days INT NOT NULL DEFAULT 0
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
	admin_name NVARCHAR(50) NOT NULL,
);
GO

CREATE TABLE stores(
	store_id INT PRIMARY KEY IDENTITY(1,1),
	store_name NVARCHAR(50) NOT NULL UNIQUE,
	user_id INT NOT NULL FOREIGN KEY REFERENCES users(user_id),
	description NVARCHAR(500) NULL,
	status NVARCHAR(20) NOT NULL DEFAULT N'正常' CHECK (status IN (N'正常',N'封禁')),

);