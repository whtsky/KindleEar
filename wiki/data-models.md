# 数据模型（数据库层）

## 双后端切换机制 ⚠

`application/back_end/db_models.py` 顶部按 `DATABASE_URL` 前缀分流：

| DATABASE_URL 前缀 | 实现 | ORM |
|---|---|---|
| `datastore` / `mongodb` / `redis` / `pickle` | `db_models_nosql.py` | 作者自写 **weedata** ODM（peewee 兼容 API），NoSQL 端 |
| `sqlite` / `mysql` / `postgresql` / `cockroachdb`（默认 `sqlite:////data/kindleear.db`） | `db_models_sql.py` | **peewee** |

- 两个实现都提供：`MyBaseModel.get_all / get_by_id_or_none / to_dict` 与模块级 `connect_database() / close_database()`（NoSQL 版为空操作）。
- 实体类在 db_models.py 中**与后端无关**地定义一次（`from xxx import *` 引入各自字段类型与 BaseModel）。
- **建表/迁移只在 SQL 后端执行**：`create_database_tables()` 按 `AppInfo.dbSchemaVersion` 判断（如 v3.2 增加 summarizer 相关列）。NoSQL 无 schema 概念，字段是动态属性。
- 自定义 `JSONField`（SQL 端）以文本存 JSON —— 用户配置大量使用 JSON 字段，加新配置项通常**不需要**改表结构。

## 实体类清单（均在 db_models.py）

### KeUser — 用户
核心实体。字段：
- `name`（唯一）、`passwd_hash`、`expiration_days`/`expires`（账号有效期，过期自动停推）
- `send_days` / `send_time`：用户级推送时间表
- JSON 字段：
  - `base_config`：email、kindle_email、secret_key（share key）、timezone、proxy、delivery_mode（email/local）、webshelf_days 等
  - `book_config`：书籍格式（type=mobi/epub...）、设备 profile、标题格式、语言、oldest_article、书名 title 等
  - `share_links`：归档分享配置（Evernote/Wiz/Pocket/Instapaper/wallabag 凭据）+ 书签/扩展用 key
  - `covers`：封面策略
  - `send_mail_service`：**发信通道配置**（service=smtp/webdav/gae/sendgrid/mailjet/local + 各自参数；SMTP 密码加密存储，可引用管理员配置）
  - `custom`：杂项（calibre_options、词典设置等）
- 常用方法：`cfg(key)` / `book_cfg(key)` / `set_cfg()`（JSON 配置读写）、密码哈希校验、`ke_encrypt/decrypt` 便捷方法、`local_time()`（时区换算）、`all_custom_rss`。

### Recipe — 自定义 RSS / 上传的 recipe
`title`、`url`、`isfulltext`、`type_`（'custom' | 'upload'）、`src`（仅 upload 存源码；custom 投递时动态生成）、`user`、`language`。
`recipe_id` 属性 → `"custom:12"` / `"upload:34"` 形式。内置 recipe 不入库（见 extensibility.md）。

### BookedRecipe — 已订阅项（含 builtin 订阅）
`recipe_id`（`builtin:xxx` / `custom:x` / `upload:x`）、`separated`（是否单独一本书推送）、网站账号密码（`ke_encrypt` 加密）、`send_days` / `send_times`（**书级时间表，优先于用户级**）、`title`、`language`，以及三套增强配置 JSON：`translator` / `tts` / `summarizer`。

### DeliverLog — 投递历史
`user`、`to`（收件地址）、`size`、`time_str`、`book`、`status`（ok/nonews/fetch failed 等）。由 `base_handler.save_delivery_log()` 和 send_mail_adpt 写入；`/logs` 页展示；`/removelogs` 清理 30 天前记录。

### WhiteList — 发件白名单
`mail`、`user`。入站邮件反垃圾用（Kindle 接收方域名思路的本地版）。

### SharedRss / SharedRssCategory — 共享订阅库（仅官方站点使用）
SharedRss：共享的 RSS/recipe 条目（标题、URL、分类、订阅计数、失效举报计数）。SharedRssCategory：分类缓存。普通部署下这两张表是死代码（`view/library_offical.py` 才用）。

### LastDelivered — 上次投递记录
每本书上次投递的时间/信息，用于增量抓取与"现在推送"去重。

### InBox — 入站邮件存档（GAE/postfix 收信）
正文 + `attachments`（附件二进制指向 UserBlob）。`/webmail` 网页收件箱读取。

### UserBlob — 用户二进制数据
`name`、`user`、`time`、`data`（Blob）。自定义封面、自定义 CSS、收信附件等都存这里。

### AppInfo — 全局 KV 表
`dbSchemaVersion`（迁移标记）、`signupType`（注册方式）、`inviteCodes`（邀请码）等全局状态。

## 配置读取约定（避免误判"字段在哪"）

用户级配置**不都体现在列上**，而是塞在三个 JSON 字段里。查找某配置项的写读位置时按此映射：
- 读：`user.cfg('xxx')`（base_config）、`user.book_cfg('xxx')`（book_config）、`user.custom_cfg` 相关（custom）
- 写：设置页 `view/settings.py` POST → `user.set_cfg(...)`
- 跨实体：投递相关增强配置在 `BookedRecipe`（书级覆盖用户级）
