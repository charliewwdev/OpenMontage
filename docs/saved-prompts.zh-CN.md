# 我的提示词：存储、权限与迁移

「个人资产 → 提示词」里的「我的提示词」按账号保存：每条提示词只属于一个账号，别的账号看不到、改不了、删不掉。

## 谁能看、谁能存

| 访问者 | 列表 | 新建 / 编辑 / 删除 |
| --- | --- | --- |
| 已登录账号（包括 GitHub 登录的 `gh-<id>`） | 只看到自己的 | 可以 |
| 未登录（`STUDIO_AUTH_REQUIRED=true`） | 空列表，提示登录 | 401 |
| Demo 体验账号（多人共用同一个 id） | 空列表，提示用自己的账号登录 | 403；`STUDIO_DEMO_SAVE_PROMPTS=1` 时可以 |
| 关闭登录（`STUDIO_AUTH_REQUIRED=false`，单人自用） | 本机用户 `_local` 的列表 | 可以 |

为什么 Demo 账号默认只读：公开实例上所有体验访客共用 `demo` 这一个 id，如果允许保存，大家会看到、改到彼此的提示词。按浏览器 Cookie 分身也不可靠：清掉 Cookie 就丢数据，换个 Cookie 又能无限写入。这和每日额度只认 GitHub 账号、不认 Demo 身份是同一个思路。只有自己用的私有部署，才建议设 `STUDIO_DEMO_SAVE_PROMPTS=1`（`studio/.env.example` 默认就是 1；`docker-compose.studio.yml` 的默认是 0）。

其他规则：

- 提示词 id 是随机生成的；拿别人的 id 去改或删，返回 404，不会泄露它是否存在。
- 限制：正文默认最多 8000 字符，标题最多 120 字符，每个账号最多 500 条，请求体最大 64 KB。
- 频率：每个账号默认 60 秒内最多 30 次保存 / 删除，超过返回 429 并带 `Retry-After`。这个计数在每个进程的内存里，多进程部署时每个进程分别计数。
- 列表接口 `GET /api/platform/prompts` 支持 `category`、`q`（字面匹配，`%` 和 `_` 不当通配符）、`sort=latest|oldest|name`、`offset`、`limit`（1–200，默认 60），返回 `total` 和 `nextOffset`。
- 错误返回 `{"error": "...", "code": "prompts_..."}`。`error` 按请求头 `X-Studio-Locale` 给出中文或英文。
- 日志里不写提示词标题和正文；账号只记一个短哈希。

## 存在哪里

- **Postgres**（设置了 `DATABASE_URL` 或 `STUDIO_DATABASE_URL`）：存在 `studio_prompts` 表里，按 `owner_id` 建了索引；同一账号里同一条提示词库来源（`origin.libraryId`）和同一条旧数据（`legacy_id`）都有唯一约束。表结构在第一次用到时自动创建。迁移用 `studio_schema_migrations` 记账，并加了 advisory lock，可以重复执行，多实例同时启动也没问题。保存时按账号加事务锁，所以并发写入也不会超过条数上限。
- **磁盘**：存在 `PROJECTS_ROOT/.users/<账号>/prompts.json`。写入时先写临时文件再 `os.replace`，同时加进程内锁和 `flock` 文件锁。

## 旧数据（按账号保存之前的共享列表）

旧版本把所有人的提示词存在同一个列表里（Postgres 的 `studio_kv` 键 `prompts:_library`，或磁盘上的 `PROJECTS_ROOT/_library/prompts.json`）。

- 旧数据**不会被修改或删除**。在 Postgres 里，它会被复制成 `owner_id IS NULL` 的行，谁都看不到。
- 关闭登录的单人部署会自动把旧数据接到 `_local`，升级后看到的内容不变。
- 想把旧数据给某个账号：设 `STUDIO_LEGACY_PROMPTS_OWNER=<账号 id>`，这个账号第一次打开「我的提示词」时会自动复制一次。也可以用下面的命令手动分配。
- 从磁盘迁到 Postgres（`/api/ops/migrate-disk-to-pg`）时，`.users/*/prompts.json` 也会一起导入表里，已存在的行不会被覆盖。

### 管理命令

在 studio 容器里运行，或者在本机用同样的环境变量运行（`DATABASE_URL` / `STUDIO_DATABASE_URL`、`PROJECTS_ROOT`）：

```bash
# 建表 / 升级表结构，并导入旧数据（可重复执行）
python studio/scripts/prompts_admin.py migrate

# 列出旧数据；默认不打印正文，加 --show-text 才打印
python studio/scripts/prompts_admin.py legacy-list
python studio/scripts/prompts_admin.py legacy-list --json --show-text

# 把旧数据复制给某个账号（同一条只会复制一次）
python studio/scripts/prompts_admin.py legacy-assign --to gh-12345 --all
python studio/scripts/prompts_admin.py legacy-assign --to gh-12345 --ids old-1,old-2
#   --force 表示忽略每账号条数上限

# 每个账号的提示词数量
python studio/scripts/prompts_admin.py owners
```

GitHub 登录的账号 id 是 `gh-<GitHub 数字 id>`，可以在 `https://api.github.com/users/<用户名>` 的 `id` 字段查到。

## 环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `STUDIO_DEMO_SAVE_PROMPTS` | `0`（`.env.example` 里是 `1`） | Demo 体验账号能否保存。公开实例保持 0 |
| `STUDIO_LEGACY_PROMPTS_OWNER` | 空 | 把旧数据自动复制给这个账号（只复制一次） |
| `STUDIO_PROMPTS_MAX_PER_USER` | `500` | 每个账号最多几条 |
| `STUDIO_PROMPT_TEXT_MAX` | `8000` | 正文最多几个字符（上限 20000） |
| `STUDIO_PROMPT_TITLE_MAX` | `120` | 标题最多几个字符（上限 300） |
| `STUDIO_PROMPTS_RATE_LIMIT` | `30/60` | 每个账号「次数/秒数」内最多几次保存或删除 |
| `STUDIO_PG_POOL_MAX` | `8` | Postgres 连接池大小；连接用满时请求排队等待，不会直接报错 |
| `STUDIO_PG_POOL_TIMEOUT` | `30` | 等待空闲连接的秒数 |

## 回滚

旧版本只读 `prompts:_library`（或磁盘上的旧文件），这份数据一直没动过，所以直接回滚到旧镜像就能用。回滚期间 `studio_prompts` 表可以留着不删；以后再升级，按账号保存的数据都还在。
