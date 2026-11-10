# 数据备份与恢复

所有持久化数据都在仓库目录下的 bind mount 中，备份 = 拷目录 / 导出数据库。

## 一键备份（建议加入 cron）

```bash
cd dake-deploy
mkdir -p backups
# 1. 数据库逻辑备份（在线、一致性）
docker compose exec -T postgresql pg_dump -U "$(grep '^DB_USERNAME=' .env | cut -d= -f2)" \
  "$(grep '^DB_NAME=' .env | cut -d= -f2)" | gzip > "backups/dake-$(date +%F-%H%M).sql.gz"
# 2. 附件与对象存储（题目图片、上传文件）
tar czf "backups/profile-$(date +%F-%H%M).tgz" profile/file profile/sub_file profile/img_file
tar czf "backups/minio-$(date +%F-%H%M).tgz" minio/data
```

> 恢复演练：备份只有做过恢复演练才算有效。建议每学期抽一次把备份恢复到测试目录。

## 恢复到全新环境

```bash
# 1. 新机器 clone 本仓库，跑 ./init.sh --no-seed（跳过演示数据）
# 2. 恢复数据库
gunzip -c backups/dake-XXXX.sql.gz | docker compose exec -T postgresql psql -U postgres -d <DB_NAME> -v ON_ERROR_STOP=1
# 3. 恢复文件（先 down 再解压，避免写入竞争）
docker compose down
tar xzf backups/profile-XXXX.tgz
tar xzf backups/minio-XXXX.tgz
# 4. 检查 .env 的 PUBLIC_HOST 与新环境地址一致（不一致时全局替换见下）
docker compose up -d
```

## 迁移后图片地址修正

历史数据的图片 URL 内嵌了部署地址。换了 `PUBLIC_HOST` 后，用一条 SQL 批量替换
（把 `OLD_HOST` / `NEW_HOST` 换成实际值，先在测试库验证再执行）：

```sql
-- MinIO 图片（含端口）
UPDATE sys_attachment SET url = replace(url, 'OLD_HOST:9000', 'NEW_HOST:9000') WHERE url LIKE '%OLD_HOST:9000%';
UPDATE question_choices SET content = replace(content, 'OLD_HOST:9000', 'NEW_HOST:9000') WHERE content LIKE '%OLD_HOST%';
-- 其余含地址的表按需同法处理（em_course_outline_desc / exam_answer 等）
```

## Redis 需要备份吗

Redis 仅存缓存与验证码，不需要备份。持久化目录 `redis/data` 可随重置删除。
