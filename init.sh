#!/usr/bin/env bash
# =====================================================================
# 达证通（达课）一键部署
#   ./init.sh            完整部署（含 Judge0 在线判题）
#   ./init.sh --core     只起核心服务（不判题，代码题转人工批改）
#   ./init.sh --no-seed  跳过演示数据导入
# 幂等：重复执行只补齐缺失步骤，不会重复导入种子数据。
# =====================================================================
set -euo pipefail
cd "$(dirname "$0")"

WITH_JUDGE0=1
WITH_SEED=1
for arg in "$@"; do
  case "$arg" in
    --core)     WITH_JUDGE0=0 ;;
    --no-seed)  WITH_SEED=0 ;;
    *) echo "未知参数：$arg（可用：--core / --no-seed）"; exit 1 ;;
  esac
done

say() { printf '\033[1;36m==> %s\033[0m\n' "$*"; }

# ---------------------------------------------------------------- 1. .env
if [ ! -f .env ]; then
  cp .env.example .env
  say ".env 已从模板创建"
fi
set -a; . ./.env; set +a

gen_pw() { openssl rand hex 16 2>/dev/null || head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n'; }
fill_pw() { # $1=变量名
  local v; eval "v=\$$1"
  if [ -z "$v" ]; then
    v=$(gen_pw)
    sed -i "s|^${1}=.*|${1}=${v}|" .env
    eval "$1=\$v"
    say "已生成随机 $1"
  fi
}
fill_pw DB_PASSWORD
fill_pw REDIS_PASSWORD
fill_pw MINIO_ROOT_PASSWORD
if [ -z "${TOKEN_SIGN_KEY}" ]; then
  TOKEN_SIGN_KEY=$(gen_pw)$(gen_pw)
  sed -i "s|^TOKEN_SIGN_KEY=.*|TOKEN_SIGN_KEY=${TOKEN_SIGN_KEY}|" .env
  say "已生成随机 TOKEN_SIGN_KEY"
fi

# ---------------------------------------------------------------- 2. 目录
mkdir -p profile/{logs,file,tmp,scorePdf,sub_file,img_file/img} postgresql/data minio/data redis/data
say "数据目录就绪"

# ---------------------------------------------------------------- 3. judge0.conf 密码同步
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${DB_PASSWORD}|" judge0/judge0.conf
sed -i "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=${JUDGE0_REDIS_PASSWORD}|" judge0/judge0.conf

# ---------------------------------------------------------------- 4. 基础服务
say "启动 PostgreSQL / Redis / MinIO ..."
docker compose up -d postgresql redis minio

for i in $(seq 1 60); do
  ok=1
  docker compose exec -T postgresql pg_isready -U "$DB_USERNAME" -d "$DB_NAME" >/dev/null 2>&1 || ok=0
  docker compose exec -T redis redis-cli -a "$REDIS_PASSWORD" --no-auth-warning ping >/dev/null 2>&1 || ok=0
  curl -sf -o /dev/null "http://localhost:${MINIO_PORT:-9000}/minio/health/live" || ok=0
  [ "$ok" = 1 ] && break
  sleep 2
done
[ "$ok" = 1 ] || { echo "基础服务未就绪，请查日志：docker compose logs postgresql redis minio"; exit 1; }
say "基础服务健康检查通过"

# ---------------------------------------------------------------- 5. 种子数据
if [ "$WITH_SEED" = 1 ]; then
  SEEDED=$(docker compose exec -T postgresql psql -U "$DB_USERNAME" -d "$DB_NAME" -tAc \
    "select to_regclass('public.em_course') is not null" | tr -d '[:space:]')
  if [ "$SEEDED" = "t" ]; then
    say "数据库已有数据，跳过种子导入"
  else
    say "导入演示数据（约 1-2 分钟）..."
    sed "s|__DAKE_APP__|${PUBLIC_HOST}|g" database/dake_local.sql \
      | docker compose exec -T postgresql psql -U "$DB_USERNAME" -d "$DB_NAME" -v ON_ERROR_STOP=1 -q \
      || { echo "种子导入失败：docker compose logs postgresql 排查后重试（重试前需清空 postgresql/data）"; exit 1; }
    say "演示数据导入完成"
  fi
fi

# ---------------------------------------------------------------- 6. 数据库结构迁移
# database/migration/ 下的脚本幂等可重跑：新装库在种子后补齐，老库（升级）同样补齐到最新。
# 迁移前先停旧应用（V51 起含破坏性变更：旧镜像实体仍映射被 DROP 的 goal_id 列，
# 列没了旧应用查询即 500；停机窗口=迁移时长+新应用启动，升级请安排在非教学时段）。
# 全新安装时应用尚未起过，stop 是无害空操作。
docker compose stop app >/dev/null 2>&1 || true
for f in database/migration/*.sql; do
  [ -e "$f" ] || continue
  say "应用数据库迁移 $(basename "$f") ..."
  docker compose exec -T postgresql psql -U "$DB_USERNAME" -d "$DB_NAME" -v ON_ERROR_STOP=1 -q < "$f" \
    || { echo "迁移失败：$f（docker compose logs postgresql 排查后重试）"; exit 1; }
done

# ---------------------------------------------------------------- 7. Judge0
if [ "$WITH_JUDGE0" = 1 ]; then
  if [ "$(stat -fc %T /sys/fs/cgroup/)" = "cgroup2fs" ]; then
    cat <<'EOF'
⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠
⚠ 宿主机当前是 cgroup v2，Judge0 判题会失败（Internal Error status 13）！
⚠ 两种选择：
⚠   1) 按 README「Judge0 判题准备」切换 cgroup v1 后重启宿主机，再跑本脚本
⚠   2) 重跑 ./init.sh --core 且在 .env 设 JUDGE0_ENABLED=false（代码题人工批改）
⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠⚠
EOF
    exit 1
  fi
  say "启动 Judge0 判题引擎 ..."
  docker compose --profile judging up -d judge0-redis judge0 judge0-worker
fi

# ---------------------------------------------------------------- 8. 应用与前端
say "启动后端与前端 ..."
docker compose up -d

# ---------------------------------------------------------------- 9. 等待后端就绪
say "等待后端启动（首次约 1 分钟）..."
for i in $(seq 1 90); do
  curl -sf -o /dev/null "http://localhost:${APP_PORT:-10025}/at-user-service/v1/code/initprobe" && break
  sleep 2
done
curl -sf -o /dev/null "http://localhost:${APP_PORT:-10025}/at-user-service/v1/code/initprobe" \
  || { echo "后端未就绪：docker compose logs -t app | tail -100"; exit 1; }
say "后端就绪"

# ---------------------------------------------------------------- 10. 总结
PORT_T=${TEACHER_WEB_PORT:-10026}; PORT_S=${STUDENT_WEB_PORT:-10027}
cat <<EOF

==================== 部署完成 ====================
  教师端（管理后台）  http://${PUBLIC_HOST}:${PORT_T}
  学生端             http://${PUBLIC_HOST}:${PORT_S}
  对象存储 MinIO     http://${PUBLIC_HOST}:${MINIO_PORT:-9000}

  演示账号（首次登录后请立即改密）：
    管理员  admin / 1qaz2wsx@asiontech
    教师    23t    / 1qaz2wsx@23t
    学生    T10016 / 123456

  随机生成的密码已写入 .env（数据库/Redis/MinIO），请妥善保管。
  常用命令：
    docker compose logs -f app        # 看后端日志
    docker compose down               # 停止（数据保留在 ./postgresql/data 等目录）
    rm -rf postgresql/data minio/data redis/data   # 彻底重置数据（删除前先 down）
==================================================
EOF
