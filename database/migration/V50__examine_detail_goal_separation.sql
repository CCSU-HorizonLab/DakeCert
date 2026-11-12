-- V50 考核明细-课程目标映射表分离（达成度矩阵 toggle 根因修复，2026-11-12）
-- 背景：goal_id 物化在明细行身份上，「取消分配」=物理删行（生产事故：小题 5164→8730，
--       149 条成绩孤儿 → 达成度计算 NPE）；且单值列表达不了 M:N（一题多目标只能靠
--       孪生标记行硬凑，examine 506 第1题×5 行）。
-- 方案：分配关系移入 em_course_examine_detail_goal，明细行只承载事实（结构/分值），
--       身份永不被分配操作触碰；矩阵 toggle 只 INSERT/DELETE 映射。
--   - cal_type 0/1（按比例/按大题）：原「无成绩的目标标记子行」折叠为事实行上的映射，
--     score = 该目标规定分值（v-loop ecJson 加权分母的语义原样迁移）；
--   - cal_type 2（按小题）：goal_id 列值迁为小题行自身映射（映射 score 为 NULL，
--     小题分值仍在明细行）。
-- 折叠防线（与旧读路径逐位对齐）：
--   1) 只折「无成绩且无绑定引用」的标记行——带引用的杂交行（如 outline 47 的
--      3468/3471：带成绩且自带 goal）不迁自身 goal：旧 calc 对 cal0/1 只认标记子行，
--      行自身 goal 是死值，迁了反而改变数字；
--   2) 只折 name 与父行一致（或为 NULL）的标记行——旧 table2 有 name 残留过滤
--      （考核环节2 等不匹配名会被整个滤掉，不进格子/分母），不匹配者仅删除不建映射；
--   3) 标记行先整表备份到 backup_ced_goal_marker_v50 再删。
-- goal_id 列暂保留；清列门禁（第29轮审查 P2-2，清列=V51 DROP COLUMN 前必须全部满足）：
--   a. 读路径已全面退役：table2 子层格子已改读映射（原 :704 s.getGoalId() 分支）、
--      明细树 goalSerial 死 join 已拆、学生成绩 VO select 与合计门已去除 goal_id；
--   b. 存量脏值清零：em_course_examine_detail 中 goal_id IS NOT NULL 的存活行应为 0
--      （V50 折叠防线有意保留的杂交行 3468/3471 等须先手工置 NULL——其归属已由映射表达）；
--   c. 对账绿（四项，见下方 GATE SQL）：
--      ① cal0/1 映射宿主层级合法：cal1 宿主必须 parent_id<>0（环节根无格子，映射不渲染）；
--      ② goalid_only/map_only 分裂 tier 均 0（取消分配只删映射、行上残留列值=分裂源）；
--      ③ 孤儿映射 0（明细/考核已删而映射残留）；
--      ④ 映射不可 JOIN 课程目标 0。
-- 幂等：可重跑；引用 goal_id 列的语句均带列存在守卫——V51 掉列后的库重放本脚本
--   只发 NOTICE 跳过（部署器全量重放迁移时的安全前提，2026-11-12 实测修复）。
--   步骤序敏感：步骤 4（杂交行补映射）必须在步骤 3（删标记行）之后（详见步骤 4 注释）。
-- 回滚口径（不支持静默跨 V50 回滚）：旧代码只认行上 goal_id，直接回滚会让 V50 后
--   新增的映射不可见（cal0/1 表观为「漏分配」）。确需回滚时先停用矩阵入口，用
--   backup_ced_goal_marker_v50 + 映射表手工回填 goal_id，核对后再换旧 jar。
-- 备份表清理时间点：backup_ced_goal_marker_v50 仅供上述手工回滚兜底；上线后
--   持续观察一个教学周期（或至少一轮全量对账绿）即可 DROP（本地库与交付种子
--   已于 2026-11-12 清除，生产待各自部署后按此时间点处理）。
-- 编号说明：V48 被 feature/class-assistant 分支占用，V49 之后顺延 V50。

CREATE SEQUENCE IF NOT EXISTS em_course_examine_detail_goal_id_seq;

CREATE TABLE IF NOT EXISTS em_course_examine_detail_goal (
  id        BIGINT      PRIMARY KEY DEFAULT nextval('em_course_examine_detail_goal_id_seq'::regclass),
  detail_id BIGINT      NOT NULL,
  goal_id   BIGINT      NOT NULL,
  score     NUMERIC(10,2)
);

COMMENT ON TABLE em_course_examine_detail_goal IS '考核明细行-课程目标映射（分配关系分离）：cal0/1 为题型/模块行的目标分值映射，cal2 为小题行的目标归属映射；矩阵分配/取消只动本表';
COMMENT ON COLUMN em_course_examine_detail_goal.detail_id IS '明细行 id（事实行：cal0/1=题型/模块行，cal2=小题行）';
COMMENT ON COLUMN em_course_examine_detail_goal.goal_id IS '课程目标 id（em_course_goal.goal_id）';
COMMENT ON COLUMN em_course_examine_detail_goal.score IS '该目标规定分值，仅 cal0/1 有值（加权分母材料）；cal2 小题分值在明细行自身';

CREATE UNIQUE INDEX IF NOT EXISTS uq_cedg_detail_goal ON em_course_examine_detail_goal (detail_id, goal_id);
CREATE INDEX IF NOT EXISTS idx_cedg_goal ON em_course_examine_detail_goal (goal_id);

-- ── 1) cal0/1：折叠 name 匹配且无引用的标记子行为映射 ──
DO $v50$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name = 'em_course_examine_detail' AND column_name = 'goal_id') THEN
    EXECUTE $step$
      INSERT INTO em_course_examine_detail_goal (detail_id, goal_id, score)
      SELECT p.id, d.goal_id, d.score
      FROM em_course_examine_detail d
      JOIN em_course_examine ce ON ce.examine_id = d.examine_id
      JOIN em_course_examine_detail p ON p.id = d.parent_id
      WHERE ce.cal_type IN (0, 1)
        AND d.goal_id IS NOT NULL
        AND d.parent_id != 0
        AND (ce.cal_type = 0 OR p.parent_id != 0)  -- cal1 环节根无格子（gate1 死锚点）不折；cal0 根行映射=合法数据形态
        AND (d.name IS NULL OR d.name = p.name)
        AND NOT EXISTS (SELECT 1 FROM em_teaching_class_score s WHERE s.examine_detail_id = d.id AND s.is_deleted = false)
        AND NOT EXISTS (SELECT 1 FROM em_course_examine_detail_relation_score r WHERE r.examine_detail_id = d.id)
        AND NOT EXISTS (SELECT 1 FROM em_course_examine_detail_goal g
                        WHERE g.detail_id = p.id AND g.goal_id = d.goal_id)
    $step$;
  ELSE
    RAISE NOTICE 'V50 步骤1：goal_id 列已退役（V51 已执行），折叠跳过';
  END IF;
END
$v50$;

-- ── 2) cal2：小题行自身 goal 迁为映射（分值不动）──
DO $v50$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name = 'em_course_examine_detail' AND column_name = 'goal_id') THEN
    EXECUTE $step$
      INSERT INTO em_course_examine_detail_goal (detail_id, goal_id)
      SELECT d.id, d.goal_id
      FROM em_course_examine_detail d
      JOIN em_course_examine ce ON ce.examine_id = d.examine_id
      WHERE ce.cal_type = 2
        AND d.goal_id IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM em_course_examine_detail_goal g
                        WHERE g.detail_id = d.id AND g.goal_id = d.goal_id)
    $step$;
  ELSE
    RAISE NOTICE 'V50 步骤2：goal_id 列已退役（V51 已执行），cal2 迁移跳过';
  END IF;
END
$v50$;

-- ── 3) 备份并删除 cal0/1 的纯标记行（无任何成绩/绑定引用；杂交行保留）──
DO $v50$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name = 'em_course_examine_detail' AND column_name = 'goal_id') THEN
    EXECUTE $step$
      CREATE TABLE IF NOT EXISTS backup_ced_goal_marker_v50 AS
      SELECT d.*, ce.cal_type AS _cal_type
      FROM em_course_examine_detail d
      JOIN em_course_examine ce ON ce.examine_id = d.examine_id
      WHERE ce.cal_type IN (0, 1)
        AND d.goal_id IS NOT NULL
        AND d.parent_id != 0
        AND NOT EXISTS (SELECT 1 FROM em_teaching_class_score s WHERE s.examine_detail_id = d.id AND s.is_deleted = false)
        AND NOT EXISTS (SELECT 1 FROM em_course_examine_detail_relation_score r WHERE r.examine_detail_id = d.id)
    $step$;
    EXECUTE $step$
      DELETE FROM em_course_examine_detail d
      USING em_course_examine ce
      WHERE ce.examine_id = d.examine_id
        AND ce.cal_type IN (0, 1)
        AND d.goal_id IS NOT NULL
        AND d.parent_id != 0
        AND NOT EXISTS (SELECT 1 FROM em_teaching_class_score s WHERE s.examine_detail_id = d.id AND s.is_deleted = false)
        AND NOT EXISTS (SELECT 1 FROM em_course_examine_detail_relation_score r WHERE r.examine_detail_id = d.id)
    $step$;
  ELSE
    RAISE NOTICE 'V50 步骤3：goal_id 列已退役（V51 已执行），备份/删除标记行跳过';
  END IF;
END
$v50$;

-- ── 4) 保留的杂交标记行补行自身映射（原步骤 1.5，第29轮审查 P2-2）──
-- 折叠防线只删「无引用」标记行；带成绩/绑定引用者保留为行（如 dake_local 的 30/实训1）。
-- 旧读路径按「子行 goal_id 列」渲染这类行的格子；第29轮起子层格子只认映射——
-- 这里把列值等价迁为行自身映射（键位/锚定/分值与旧渲染逐位一致），随后的清列不丢归属。
-- 仅迁 name 与父行一致的标记形态行；3468/3471 等「真实数据行带死列值」（name≠父行）
-- 旧代码本就不渲染其列值，不在其列，由清列前置处置置 NULL。
-- ⚠ 执行序（2026-11-12 生产实测教训）：本步骤必须在步骤 3 删除标记行**之后**执行——
--   早期版本排在 3 之前且缺引用过滤，新库首跑时待删的纯标记行同时拿到步骤 1 的父行映射
--   与本步骤的自身映射，行被删后自身映射全部成孤儿（生产实测 gate3=848）。
--   现引用过滤（至少一个 score/relation 引用 = 折叠防线保留的行）与后置双保险，
--   即使单独回放本步骤也不再给待删行建映射。已污染库的清理口径：按 gate3 定义 DELETE。
DO $v50$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name = 'em_course_examine_detail' AND column_name = 'goal_id') THEN
    EXECUTE $step$
      INSERT INTO em_course_examine_detail_goal (detail_id, goal_id, score)
      SELECT d.id, d.goal_id, d.score
      FROM em_course_examine_detail d
      JOIN em_course_examine ce ON ce.examine_id = d.examine_id
      JOIN em_course_examine_detail p ON p.id = d.parent_id
      WHERE ce.cal_type IN (0, 1)
        AND d.goal_id IS NOT NULL
        AND d.parent_id != 0
        AND (d.name IS NULL OR d.name = p.name)
        AND (EXISTS (SELECT 1 FROM em_teaching_class_score s WHERE s.examine_detail_id = d.id AND s.is_deleted = false)
             OR EXISTS (SELECT 1 FROM em_course_examine_detail_relation_score r WHERE r.examine_detail_id = d.id))
        AND NOT EXISTS (SELECT 1 FROM em_course_examine_detail_goal g
                        WHERE g.detail_id = d.id AND g.goal_id = d.goal_id)
    $step$;
  ELSE
    RAISE NOTICE 'V50 步骤4：goal_id 列已退役（V51 已执行），补映射跳过';
  END IF;
END
$v50$;

INSERT INTO sys_schema_version (version, description, script, applied_by)
SELECT 'V50', '考核明细-课程目标映射表分离（矩阵 toggle 根因修复，标记行折叠）', 'V50__examine_detail_goal_separation.sql', 'lsyer'
WHERE NOT EXISTS (SELECT 1 FROM sys_schema_version WHERE version = 'V50');

-- ══ GATE SQL：清列（V51 DROP COLUMN em_course_examine_detail.goal_id）前的对账门禁 ══
-- 四项计数全部为 0 才允许清列；任一非 0 须先处置并记录（第29轮审查 P2-2/P2-4）。
-- ① cal0/1 惰性映射：cal1 宿主为环节根（parent_id=0，分组表头无格子，永不渲染）
SELECT 'gate1_cal1_outer_host' AS check_name, COUNT(*) AS violations
FROM em_course_examine_detail_goal m
JOIN em_course_examine_detail d ON d.id = m.detail_id AND d.is_deleted = false
JOIN em_course_examine ce ON ce.examine_id = d.examine_id AND ce.is_deleted = false
WHERE ce.cal_type = 1 AND d.parent_id = 0;

-- ② goal_id 列残留脏值（写侧已恒置 NULL；折叠防线保留的杂交行须手工置 NULL 后归零）。
--    列已退役（V51 已执行）的库重放时发 NOTICE 0，不报错。
DO $v50$
DECLARE
  n BIGINT;
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name = 'em_course_examine_detail' AND column_name = 'goal_id') THEN
    EXECUTE $step$
      SELECT COUNT(*) FROM em_course_examine_detail d
      JOIN em_course_examine ce ON ce.examine_id = d.examine_id AND ce.is_deleted = false
      WHERE d.is_deleted = false AND d.goal_id IS NOT NULL
    $step$ INTO n;
    RAISE NOTICE 'gate2_goalid_residue violations=%', n;
  ELSE
    RAISE NOTICE 'gate2_goalid_residue violations=0（goal_id 列已退役）';
  END IF;
END
$v50$;

-- ③ 孤儿映射：宿主明细行或考核环节已不存在/软删
SELECT 'gate3_orphan_mapping' AS check_name, COUNT(*) AS violations
FROM em_course_examine_detail_goal m
LEFT JOIN em_course_examine_detail d ON d.id = m.detail_id AND d.is_deleted = false
LEFT JOIN em_course_examine ce ON ce.examine_id = d.examine_id AND ce.is_deleted = false
WHERE d.id IS NULL OR ce.examine_id IS NULL;

-- ④ 映射指向不存在的课程目标
SELECT 'gate4_dangling_goal' AS check_name, COUNT(*) AS violations
FROM em_course_examine_detail_goal m
LEFT JOIN em_course_goal cg ON cg.goal_id = m.goal_id AND cg.is_deleted = false
WHERE cg.goal_id IS NULL;
