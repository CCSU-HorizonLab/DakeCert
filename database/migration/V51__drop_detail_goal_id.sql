-- V51 退役 em_course_examine_detail.goal_id 列（2026-11-12）
-- 背景：V50 起分配事实唯一存于 em_course_examine_detail_goal 映射表，goal_id 列读点已全面退役
--       （table2 子层格子改读映射、明细树死 join 拆除、学生成绩 VO select 与合计门去除）。
--       两侧实体（dk-user-service CourseExamineDetail / dk-exam-service CourseExamineDetail2）的
--       goalId 均已降级 @TableField(exist=false) 纯传输字段，MP 生成的 INSERT/UPDATE/SELECT
--       不再包含该列——列本身已是死结构。
-- ⚠ 部署顺序约束：必须先停应用、再执行本迁移、最后起新镜像；旧镜像的实体列清单仍含
--   goal_id，列已 DROP 时任何 em_course_examine_detail 的 SELECT/INSERT 直接报
--   "column ... does not exist"（init.sh 已按此顺序编排）。
-- 前置门禁（V50 尾部 GATE SQL，四项全 0 才可执行）：
--   ① gate1_cal1_outer_host（cal1 惰性宿主）  ② gate2_goalid_residue（列残留脏值，
--   须先核对：杂交行已由 V50 步骤 1.5 迁为自身映射或确认为死值后方可清列）
--   ③ gate3_orphan_mapping  ④ gate4_dangling_goal
-- 执行前备份：pg_dump -F c 整库留档（建议同时异地/对象存储再存一份）。
-- 幂等：DROP COLUMN IF EXISTS 可重跑；版本行 NOT EXISTS 防重。

ALTER TABLE em_course_examine_detail DROP COLUMN IF EXISTS goal_id;

INSERT INTO sys_schema_version (version, description, script, applied_by)
SELECT 'V51', '退役明细行 goal_id 列（分配事实自 V50 起唯一存映射表，列读点已全退役）',
       'V51__drop_detail_goal_id.sql', 'dake-deploy'
WHERE NOT EXISTS (SELECT 1 FROM sys_schema_version WHERE version = 'V51');
