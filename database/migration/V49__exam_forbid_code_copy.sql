-- V49 考试级代码题防作弊开关（2026-11-11 生产反馈：代码区禁复制粘贴）
-- exam.forbid_code_copy：教师按考试开启后，学生端代码题编辑器（CodeFilesEditor 根节点
-- capture）拦截 copy/cut/paste/contextmenu/drop，防场外代码直接粘贴。默认关。
-- 纯客户端门槛（防君子），后端无对应校验——已在开关 helpMessage 与设计文档注明边界。
-- 编号说明：V48 被 feature/class-assistant 分支占用，主干顺延 V49。
-- 幂等：ADD COLUMN IF NOT EXISTS + 登记守卫，本地 dake_local/dake_prod_copy 已直改
-- 过列的库可直接重跑（只补登记行）。
ALTER TABLE exam ADD COLUMN IF NOT EXISTS forbid_code_copy boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN exam.forbid_code_copy IS '禁止代码题编辑器复制/剪切/粘贴（含右键菜单与拖入），考试防作弊开关，默认 false';

INSERT INTO sys_schema_version (version, description, script, applied_by)
SELECT 'V49', '考试表加 forbid_code_copy 防作弊开关（代码题禁复制粘贴）', 'V49__exam_forbid_code_copy.sql', 'lsyer'
WHERE NOT EXISTS (SELECT 1 FROM sys_schema_version WHERE version = 'V49');
