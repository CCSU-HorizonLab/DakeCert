-- V53: 班级助教权限矩阵（2026-11-17）
-- permissions 存逗号分隔的权限 code（注册表：dk-api AssistantPermission）：
--   NULL  = 全部权限（存量行兼容 + 新任职缺省全选）
--   ''    = 无权限（任职仍在：可见班级考试列表，但无任何操作权限）
--   明细  = 显式授予集
-- 试卷发布（时间窗/排期/上架）与删除考试不在权限表内，按产品口径不授予助教。
ALTER TABLE em_teaching_class_assistant ADD COLUMN IF NOT EXISTS permissions varchar(200);

COMMENT ON COLUMN em_teaching_class_assistant.permissions IS '助教权限code集合(逗号分隔,NULL=全部,空串=无)；注册表=dk-api AssistantPermission';

-- 版本登记（幂等）：生产 2026-11-17 已在线执行并手工补记同文描述，此处补齐脚本登记，
-- 新环境重放时 ON CONFLICT 保证与手工行不冲突
INSERT INTO sys_schema_version (version, description, script, applied_by)
VALUES ('V53', '班级助教权限矩阵（permissions 列，脚本补记）', 'V53__assistant_permissions.sql', 'migration')
ON CONFLICT (version) DO NOTHING;
