-- ==========================================================
-- 亿级企业智能旅游平台 - 核心业务数据库初始化脚本
-- 适用数据库: MySQL 8.0+ / TiDB (推荐用于高并发分布式场景)
-- 包含分库分表设计思想（此处为逻辑表，物理部署结合 ShardingSphere）
-- ==========================================================

CREATE DATABASE IF NOT EXISTS `travel_agent_db` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `travel_agent_db`;

-- --------------------------------------------------------
-- 1. 用户中心表 (支持按 user_id Hash 分库分表)
-- --------------------------------------------------------
CREATE TABLE `users` (
    `user_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '全局唯一用户ID(雪花算法)',
    `phone` VARCHAR(20) NOT NULL COMMENT '手机号(加密存储)',
    `nickname` VARCHAR(50) DEFAULT NULL COMMENT '昵称',
    `avatar_url` VARCHAR(255) DEFAULT NULL COMMENT '头像OSS路径',
    `status` TINYINT DEFAULT 1 COMMENT '状态: 1正常 0禁用',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`user_id`),
    UNIQUE KEY `idx_phone` (`phone`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户核心资产表';

-- --------------------------------------------------------
-- 2. 智能体对话记忆表 (冷数据存储，热数据在 Redis/RocksDB)
-- --------------------------------------------------------
CREATE TABLE `agent_conversations` (
    `conversation_id` VARCHAR(64) NOT NULL COMMENT '会话全局唯一ID',
    `user_id` BIGINT UNSIGNED NOT NULL COMMENT '所属用户ID(Sharding Key)',
    `title` VARCHAR(100) DEFAULT NULL COMMENT '随机会话生成标题',
    `turn_count` INT DEFAULT 0 COMMENT '对话轮数',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`conversation_id`),
    KEY `idx_user_time` (`user_id`, `updated_at` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='智能体主会话记录表';

CREATE TABLE `agent_messages` (
    `message_id` BIGINT UNSIGNED NOT NULL COMMENT '消息ID(雪花算法)',
    `conversation_id` VARCHAR(64) NOT NULL COMMENT '所属会话ID',
    `role` VARCHAR(20) NOT NULL COMMENT '角色: user, agent, system, tool',
    `content` TEXT NOT NULL COMMENT '消息文本内容',
    `tokens_used` INT DEFAULT 0 COMMENT '消耗Token数',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`message_id`),
    KEY `idx_conversation` (`conversation_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='会话明细行表';

-- --------------------------------------------------------
-- 3. 旅游行程计划(订单)表 (核心交易表)
-- --------------------------------------------------------
CREATE TABLE `trip_plans` (
    `plan_id` BIGINT UNSIGNED NOT NULL COMMENT '行程ID',
    `user_id` BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    `conversation_id` VARCHAR(64) DEFAULT NULL COMMENT '来源会话ID',
    `destination` VARCHAR(100) NOT NULL COMMENT '目的地',
    `start_date` DATE NOT NULL COMMENT '出发日期',
    `end_date` DATE NOT NULL COMMENT '结束日期',
    `budget_total` DECIMAL(10,2) DEFAULT NULL COMMENT '总预算',
    `plan_detail_json` JSON NOT NULL COMMENT 'Agent生成的结构化行程JSON',
    `status` TINYINT DEFAULT 1 COMMENT '状态: 1草稿 2确认出行 3已取消',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`plan_id`),
    KEY `idx_user_status` (`user_id`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='智能体生成的旅游行程表';

-- --------------------------------------------------------
-- 4. 向量化知识库挂载表 (配合 Milvus/Qdrant 知识库映射)
-- --------------------------------------------------------
CREATE TABLE `knowledge_base_meta` (
    `kb_id` VARCHAR(64) NOT NULL COMMENT '知识片段ID',
    `city_code` VARCHAR(20) NOT NULL COMMENT '关联城市代码',
    `category` VARCHAR(50) NOT NULL COMMENT '分类: attraction, hotel, traffic',
    `oss_path` VARCHAR(255) DEFAULT NULL COMMENT '原始文档路径',
    `chunk_count` INT DEFAULT 0 COMMENT '切片数量',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`kb_id`),
    KEY `idx_city` (`city_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='景点与策略知识库元数据';

