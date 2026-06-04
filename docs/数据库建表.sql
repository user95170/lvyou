-- 内蒙古旅游智能推荐与出行指南系统 - 数据库建表脚本
-- 说明：
-- 1. 请在创建好目标数据库并切换至该库后执行本脚本。
-- 2. 可根据实际 MySQL 版本和部署需求，适当调整字符集、存储引擎等设置。
-- 3. 当前应用代码已使用 user/user_profile/user_behavior_log/scenic_spot/hotel/food_place/rating/content_standard/trip/trip_day/trip_item；
--    其中 trip 系列表已支持单日路线保存与多日 Agent 草案落库；
--    souvenir/social_raw/ecommerce_raw 仍为规划保留。
-- 4. 开发环境运行时，Flask 应用会通过 SQLAlchemy 的 db.create_all() 非破坏性补齐缺失表；
--    本脚本更适合全量初始化或重建数据库时使用。

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- =============================
-- 1. 用户与画像相关表
-- =============================

DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(50) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `email` VARCHAR(100) DEFAULT NULL,
  `phone` VARCHAR(20) DEFAULT NULL,
  `gender` ENUM('unknown','male','female') NOT NULL DEFAULT 'unknown',
  `age` TINYINT UNSIGNED DEFAULT NULL,
  `home_region` VARCHAR(100) DEFAULT NULL,
  `register_source` VARCHAR(50) DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_username` (`username`),
  UNIQUE KEY `uk_user_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP TABLE IF EXISTS `user_profile`;
CREATE TABLE `user_profile` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` INT UNSIGNED NOT NULL,
  `cluster_id` INT DEFAULT NULL,
  `prefer_scenic_types` TEXT DEFAULT NULL,
  `prefer_food_types` TEXT DEFAULT NULL,
  `travel_style` VARCHAR(50) DEFAULT NULL,
  `budget_level` TINYINT DEFAULT NULL,
  `travel_frequency` TINYINT DEFAULT NULL,
  `feature_vector` TEXT DEFAULT NULL,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_profile_user` (`user_id`),
  CONSTRAINT `fk_user_profile_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP TABLE IF EXISTS `user_behavior_log`;
CREATE TABLE `user_behavior_log` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` INT UNSIGNED DEFAULT NULL,
  `target_type` VARCHAR(50) NOT NULL,
  `target_id` INT UNSIGNED NOT NULL,
  `behavior_type` VARCHAR(50) NOT NULL,
  `behavior_value` DECIMAL(10,2) DEFAULT NULL,
  `device` VARCHAR(100) DEFAULT NULL,
  `ip` VARCHAR(45) DEFAULT NULL,
  `occurred_at` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ubl_user` (`user_id`),
  KEY `idx_ubl_target` (`target_type`,`target_id`),
  CONSTRAINT `fk_ubl_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =============================
-- 2. 旅游资源相关表
-- =============================

DROP TABLE IF EXISTS `scenic_spot`;
CREATE TABLE `scenic_spot` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(200) NOT NULL,
  `city` VARCHAR(100) DEFAULT NULL,
  `district` VARCHAR(100) DEFAULT NULL,
  `address` VARCHAR(255) DEFAULT NULL,
  `longitude` DECIMAL(10,6) DEFAULT NULL,
  `latitude` DECIMAL(10,6) DEFAULT NULL,
  `type` VARCHAR(100) DEFAULT NULL,
  `tags` TEXT DEFAULT NULL,
  `opening_hours` VARCHAR(200) DEFAULT NULL,
  `ticket_price` DECIMAL(10,2) DEFAULT NULL,
  `rating_avg` DECIMAL(3,2) DEFAULT NULL,
  `rating_count` INT UNSIGNED DEFAULT 0,
  `description` TEXT DEFAULT NULL,
  `images` TEXT DEFAULT NULL,
  `status` TINYINT NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_scenic_city` (`city`),
  KEY `idx_scenic_type` (`type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP TABLE IF EXISTS `food_place`;
CREATE TABLE `food_place` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(200) NOT NULL,
  `city` VARCHAR(100) DEFAULT NULL,
  `district` VARCHAR(100) DEFAULT NULL,
  `address` VARCHAR(255) DEFAULT NULL,
  `longitude` DECIMAL(10,6) DEFAULT NULL,
  `latitude` DECIMAL(10,6) DEFAULT NULL,
  `cuisine_type` VARCHAR(100) DEFAULT NULL,
  `avg_price` DECIMAL(10,2) DEFAULT NULL,
  `rating_avg` DECIMAL(3,2) DEFAULT NULL,
  `rating_count` INT UNSIGNED DEFAULT 0,
  `tags` TEXT DEFAULT NULL,
  `source` VARCHAR(50) DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_food_city` (`city`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP TABLE IF EXISTS `hotel`;
CREATE TABLE `hotel` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(200) NOT NULL,
  `city` VARCHAR(100) DEFAULT NULL,
  `district` VARCHAR(100) DEFAULT NULL,
  `address` VARCHAR(255) DEFAULT NULL,
  `longitude` DECIMAL(10,6) DEFAULT NULL,
  `latitude` DECIMAL(10,6) DEFAULT NULL,
  `star_level` VARCHAR(50) DEFAULT NULL,
  `avg_price` DECIMAL(10,2) DEFAULT NULL,
  `rating_avg` DECIMAL(3,2) DEFAULT NULL,
  `rating_count` INT UNSIGNED DEFAULT 0,
  `tags` TEXT DEFAULT NULL,
  `source` VARCHAR(50) DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_hotel_city` (`city`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP TABLE IF EXISTS `souvenir`;
CREATE TABLE `souvenir` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(200) NOT NULL,
  `category` VARCHAR(100) DEFAULT NULL,
  `origin_city` VARCHAR(100) DEFAULT NULL,
  `price` DECIMAL(10,2) DEFAULT NULL,
  `rating_avg` DECIMAL(3,2) DEFAULT NULL,
  `rating_count` INT UNSIGNED DEFAULT 0,
  `sales_volume` INT UNSIGNED DEFAULT 0,
  `tags` TEXT DEFAULT NULL,
  `image` VARCHAR(255) DEFAULT NULL,
  `source` VARCHAR(50) DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_souvenir_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =============================
-- 3. 行程与评价相关表
-- =============================

DROP TABLE IF EXISTS `trip`;
CREATE TABLE `trip` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` INT UNSIGNED NOT NULL,
  `title` VARCHAR(200) NOT NULL,
  `start_date` DATE DEFAULT NULL,
  `end_date` DATE DEFAULT NULL,
  `days` TINYINT UNSIGNED DEFAULT NULL,
  `origin_city` VARCHAR(100) DEFAULT NULL,
  `budget_level` TINYINT DEFAULT NULL,
  `travel_style` VARCHAR(50) DEFAULT NULL,
  `created_by` VARCHAR(20) DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_trip_user` (`user_id`),
  CONSTRAINT `fk_trip_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP TABLE IF EXISTS `trip_day`;
CREATE TABLE `trip_day` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `trip_id` BIGINT UNSIGNED NOT NULL,
  `day_index` TINYINT UNSIGNED NOT NULL,
  `date` DATE DEFAULT NULL,
  `note` VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_trip_day_trip` (`trip_id`),
  CONSTRAINT `fk_trip_day_trip` FOREIGN KEY (`trip_id`) REFERENCES `trip` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP TABLE IF EXISTS `trip_item`;
CREATE TABLE `trip_item` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `trip_day_id` BIGINT UNSIGNED NOT NULL,
  `item_index` SMALLINT UNSIGNED NOT NULL,
  `item_type` VARCHAR(50) NOT NULL,
  `ref_id` INT UNSIGNED DEFAULT NULL,
  `title_snapshot` VARCHAR(255) NOT NULL,
  `city_snapshot` VARCHAR(100) DEFAULT NULL,
  `address_snapshot` VARCHAR(255) DEFAULT NULL,
  `start_time` TIME DEFAULT NULL,
  `end_time` TIME DEFAULT NULL,
  `transport_mode` VARCHAR(20) DEFAULT NULL,
  `note` VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_trip_item_day` (`trip_day_id`),
  CONSTRAINT `fk_trip_item_trip_day` FOREIGN KEY (`trip_day_id`) REFERENCES `trip_day` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP TABLE IF EXISTS `rating`;
CREATE TABLE `rating` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` INT UNSIGNED NOT NULL,
  `target_type` VARCHAR(50) NOT NULL,
  `target_id` INT UNSIGNED NOT NULL,
  `score` TINYINT UNSIGNED NOT NULL,
  `comment` TEXT DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_rating_user` (`user_id`),
  KEY `idx_rating_target` (`target_type`,`target_id`),
  CONSTRAINT `fk_rating_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =============================
-- 4. 多源数据相关表（规划保留）
-- =============================

DROP TABLE IF EXISTS `social_raw`;
CREATE TABLE `social_raw` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `platform` VARCHAR(50) NOT NULL,
  `post_id` VARCHAR(100) NOT NULL,
  `user_name` VARCHAR(100) DEFAULT NULL,
  `user_external_id` VARCHAR(100) DEFAULT NULL,
  `content` TEXT DEFAULT NULL,
  `images` TEXT DEFAULT NULL,
  `likes` INT UNSIGNED DEFAULT 0,
  `comments` INT UNSIGNED DEFAULT 0,
  `shares` INT UNSIGNED DEFAULT 0,
  `publish_time` DATETIME DEFAULT NULL,
  `crawl_time` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_social_platform` (`platform`),
  KEY `idx_social_post` (`platform`,`post_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP TABLE IF EXISTS `ecommerce_raw`;
CREATE TABLE `ecommerce_raw` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `platform` VARCHAR(50) NOT NULL,
  `product_id` VARCHAR(100) NOT NULL,
  `title` VARCHAR(255) DEFAULT NULL,
  `price` DECIMAL(10,2) DEFAULT NULL,
  `sales_volume` INT UNSIGNED DEFAULT 0,
  `rating_avg` DECIMAL(3,2) DEFAULT NULL,
  `rating_count` INT UNSIGNED DEFAULT 0,
  `shop_name` VARCHAR(255) DEFAULT NULL,
  `crawl_time` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ecom_platform` (`platform`),
  KEY `idx_ecom_product` (`platform`,`product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP TABLE IF EXISTS `content_standard`;
CREATE TABLE `content_standard` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `entity_type` VARCHAR(50) NOT NULL,
  `entity_id` INT UNSIGNED NOT NULL,
  `source_type` VARCHAR(50) NOT NULL,
  `title` VARCHAR(255) DEFAULT NULL,
  `summary` TEXT DEFAULT NULL,
  `sentiment_score` DECIMAL(4,3) DEFAULT NULL,
  `popularity_score` DECIMAL(6,3) DEFAULT NULL,
  `last_update` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_cs_entity` (`entity_type`,`entity_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SET FOREIGN_KEY_CHECKS = 1;
