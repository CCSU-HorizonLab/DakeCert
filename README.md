# 达证通（达课）· 一键部署

大学教学质量管理平台：培养方案 → 课程大纲 → 课堂教学 → 考核评价 → 达成度分析 → 持续改进。
本仓库为一键 Docker 部署（标准版），面向教师个人/课程组开箱即用。当前版本 **v3.5.2**。

## 功能列表

**教学与考试（标准版全量）**

- **培养方案**：方案/培养目标/毕业要求指标点管理，版本定稿与字段级对比
- **课程大纲**：三栏结构化大纲工作台（课程目标/知识单元/实验项目/考核环节）、计算依据表与支撑权重导出
- **题库与组卷**：单选/多选/判断/填空/简答/复合题，题库分类与学生可见范围，题目导入导出
- **在线考试**：多题型答卷、自动保存、行政班分组发布、加时/代交卷/退回重做
- **代码题在线判题（Judge0）**：Java / Python / C / C++ / JavaScript / Go / TypeScript 七语言，多文件工程与填空槽，逐用例权重评分
- **自动判分**：客观题机械比对、填空/简答归一化比对，代码题执行测试用例
- **考试工作台**：批改 / 管理 / 试卷分析三 Tab 一体化，难度与区分度热力矩阵
- **课堂签到**：手势码 + GPS 范围 + 防作弊校验
- **教学班与成绩**：教学班管理、成绩导入导出、成绩单 PDF、已批改试卷批量导出
- **课程目标达成度分析表**：录入成绩即可在线查看（导出属授权版能力）
- **Word 模板在线编辑器**：大纲/命题计划/考核审核/达成度报告模板在线编辑、占位符填写、定稿导出
- **学生端**：在线考试、自主刷题与错题本、随堂限时测验、课程浏览、成绩单

**认证闭环（授权版 🔒）**

- **AI 智能批改**：主观题大模型评分 + 评分细则缓存 + 实时进度
- **课程目标达成度闭环**：三种达成度算法、评价批次、课程目标达成情况评价表等认证文书
- **毕业目标达成度**：指标点达成度、课程贡献度、多届趋势对比、Word 报告
- **持续改进**：改进建议一键扫描、七状态闭环、达成度报告自动播种

标准版中 🔒 功能**可见但锁定**：菜单带「授权版」标记，点击弹功能介绍与联系方式；获取授权即可解锁全部能力（已有数据无缝沿用）。详见文末「升级到授权版」。

## 环境要求

- Linux + Docker Engine 24+（含 `docker compose` v2 插件），内存 ≥ 4GB
- 开放端口：`10026`（教师端）、`10027`（学生端）、`10025`（后端 API）、`9000`（MinIO 图片）
- **代码判题需宿主机 cgroup v1**（见下文「Judge0 判题准备」）；不满足可 `--core` 部署，代码题转人工批改

## 快速开始

```bash
git clone <本仓库地址> dake-deploy && cd dake-deploy
./init.sh            # 完整部署（含 Judge0 判题）
# 或：./init.sh --core   # 不判题
```

脚本幂等：自动生成 `.env` 与随机密码、建数据目录、起基础服务并等健康检查、导入演示数据、启动全部服务。完成后打印访问地址与演示账号。

也可分步手动：

```bash
cp .env.example .env   # 编辑 PUBLIC_HOST 等
docker compose up -d postgresql redis minio
# 导入种子（占位符替换为你的 PUBLIC_HOST）：
sed "s|__DAKE_APP__|$(grep '^PUBLIC_HOST=' .env | cut -d= -f2)|g" database/dake_local.sql \
  | docker compose exec -T postgresql psql -U postgres -d dake -v ON_ERROR_STOP=1 -q
docker compose --profile judging up -d   # 判题（可选）
docker compose up -d
```

## Judge0 判题准备（重要，须手动）

Judge0 内置的 isolate 沙箱只支持 **cgroup v1**（需要 `/sys/fs/cgroup/memory/`），
Debian 12 / Ubuntu 22.04+ 等新发行版默认 **cgroup v2**，会导致判题失败。
`./init.sh` 检测到 v2 会主动中止并提示。

**验证 cgroup 版本**：

```bash
stat -fc %T /sys/fs/cgroup/
# cgroup2fs → 当前是 v2，需按下面步骤切换
# tmpfs    → 当前是 v1（hybrid），无需处理
```

**切换到 cgroup v1**（⚠️ 修改 GRUB 并重启宿主机，Docker 服务会中断）：

```bash
# 1. 添加内核参数
sudo sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT="\(.*\)"/GRUB_CMDLINE_LINUX_DEFAULT="\1 systemd.unified_cgroup_hierarchy=false"/' /etc/default/grub
# 2. 确认已加上 systemd.unified_cgroup_hierarchy=false
grep GRUB_CMDLINE_LINUX_DEFAULT /etc/default/grub
# 3. 更新 GRUB 并重启
sudo update-grub && sudo reboot
# 4. 重启后重新拉起并验证
cd dake-deploy && docker compose up -d
ls /sys/fs/cgroup/memory >/dev/null 2>&1 && echo "v1 enabled" || echo "v1 NOT enabled"
# 5. 学生端代码题「运行/提交」应返回 stdout 或 Accepted
```

**回滚到 cgroup v2**（不再判题时）：

```bash
sudo sed -i 's/ systemd.unified_cgroup_hierarchy=false//' /etc/default/grub
sudo update-grub && sudo reboot
```

**判题容量建议**（`judge0-worker` 容器内 isolate 并行度，默认 4）：

| 并发考生 | 建议 worker 容量 |
|---|---|
| ≤ 50 | 4（默认） |
| 50 – 200 | 8 |
| 200+ | 16，或分离部署 Judge0 集群 |

调整方式：`judge0/judge0.conf` 的 `COUNT`（每 worker 进程数）与 `docker-compose.yml` 中 judge0-worker 副本数。

**判题降级**：Judge0 不可用或 `JUDGE0_ENABLED=false` 时，代码题自动落入人工批改队列，不影响考试进行。

## 演示账号

| 角色 | 账号 | 密码 |
|------|------|------|
| 管理员 | admin | 1qaz2wsx@asiontech |
| 教师 | 23t | 1qaz2wsx@23t |
| 学生 | T10016 | 123456 |

> ⚠️ 公网部署请**首次登录后立即修改密码**；演示数据含历史课程/考试/成绩，可自行清理后录入真实数据。

## 配置说明（.env）

| 变量 | 说明 |
|------|------|
| `PUBLIC_HOST` | **部署后必检**：浏览器可达的本机 IP/域名，图片 URL 与跨域都由它派生 |
| `TEACHER_WEB_PORT` / `STUDENT_WEB_PORT` / `APP_PORT` / `MINIO_PORT` | 各服务宿主端口 |
| `DB_PASSWORD` / `REDIS_PASSWORD` / `MINIO_ROOT_PASSWORD` | `init.sh` 首次自动生成随机值；已有数据后修改无效 |
| `JUDGE0_ENABLED` | `false` 时代码题全部人工批改 |
| `DOCKER_NAMESPACE` / `IMAGE_TAG` | 镜像仓库命名空间与版本，随正式发布地址调整 |

## 常见问题

**演示数据里的图片打不开（404）**
演示库中的历史图片/附件对象不随仓库分发（属原部署的私有对象存储），对应的占位 URL 已指向你的部署地址。新建的题目、附件、签到照片均正常上传/显示，不受影响。

**PDF 导出中文乱码或失败**
系统依赖 `profile/fonts/simsun.ttf`（随仓库提供）。如需替换，请放置任意中文 TTF 并保持文件名不变；也可换用开源宋体（如思源宋体）重命名为 `simsun.ttf`。

**忘记生成的数据库/MinIO 密码**
查看 `.env` 文件——所有随机密码首次生成后都记录在其中。

**彻底重置全部数据**

```bash
docker compose down
rm -rf postgresql/data minio/data redis/data
./init.sh
```

**升级版本**

```bash
git pull
docker compose pull && ./init.sh
```

`./init.sh` 幂等：除拉起新镜像外，还会自动补跑 `database/migration/` 下尚未生效的数据库结构迁移（迁移前自动停旧应用、迁移后再起新镜像——V51 起含删列等破坏性变更，旧代码对已删列的查询会 500，故统一按「停应用→迁移→起新镜像」编排；停机窗口约 1-2 分钟，请安排在非教学时段）。含结构变更的版本会在 `docs/release-notes/` 下给出升级说明（如 [v3.5.2](docs/release-notes/v3.5.2.md) 含 V49/V50 迁移）。

## 升级到授权版

授权版解锁 **AI 智能批改**（n8n 工作流全链，支持 DeepSeek/Qwen/OpenAI 兼容模型）与**课程目标达成度闭环**（三种达成度算法、评价批次、毕业达成度、持续改进报告）。获取授权请联系：

- 邮箱：service@asiontech.com

## 许可

本仓库及其包含的镜像、字体、模板为**专属授权软件**（详见 [LICENSE](LICENSE)）：允许部署与内部使用，禁止再分发、反编译或用于二次分发。演示数据的著作权归原作者所有。

## 致谢

感谢长沙学院计算机科学与工程学院马丽、刘欣、李少勇等老师在平台研发过程中给予的需求指导、真实教学场景试用与持续提出的改进意见。平台从设计到落地的每一步，都离不开各位老师的信任、支持与帮助，在此谨致谢忱。
