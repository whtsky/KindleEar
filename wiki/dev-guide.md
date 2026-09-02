# 开发指南（本地运行 / 测试 / i18n / 工具链）

## 1. 本地开发环境（Windows）

参考 `tools/run_flask.bat`（作者自用，盘符路径需自改），其环境变量组合即最小可运行配置：

```
FLASK_APP=main.py
DATABASE_URL=sqlite:///E:/.../database.db
TASK_QUEUE_SERVICE=apscheduler
TASK_QUEUE_BROKER_URL=memory
EBOOK_SAVE_DIR=<某目录>        # 可选，启用在线阅读器
SECRET_KEY=xxx  DELIVERY_KEY=xxx
flask run --debug
# 或: python main.py debug
```

- 首次访问 `/login` 自动创建管理员 **admin/admin**。
- 本地 sqlite 库为根目录 `database.db`。
- celery 本地调试：`tools/start_celery.bat`（eventlet，concurrency 2）。
- 需要收邮件测试时参考 `tests/simple_in_email.py` 与 `tests/debug_mail/` 样本。

## 2. 测试

- 入口 `tests/runtests.py`（unittest）：`python tests/runtests.py`，支持 coverage、failfast、`KE_SLOW_TESTS=1` 慢速用例、按模块名过滤。⚠ 文件尾部当前硬编码 `testonly='test_inbound_email'`（只会跑该模块，跑全量需先清掉）。
- BaseTestCase（tests/test_base.py）自动建 app/表/test_client，可选自动登录。
- 模块对应：test_login/setting/admin/subscribe/adv/logs/inbound_email/share(当前排除)/library_offical。
- datastore 相关在 tests/tools/：`run_datastore_emulator.bat`（gcloud 模拟器）+ test_datastore.py / test_nosql.py；test_calibre2.py 本地生成样书。
- fixture：tests/rss/（rss.xml、本地 .recipe）。

## 3. i18n 工作流（tools/）

```
pybabel_extract.bat   # babel.cfg 规则提取 → translations/messages.pot → update 各语言 po
pybabel_compile.bat   # po → mo
pybabel_auto_translate.py  # 作者私用：以中文 po 为参照调用外部 autopo(AI) 翻译其余语言
```

- 代码中用内置注入的 `_()`（builtins）+ Jinja2 模板自动提取；语言切换 `/setlocale`，locale 选择器在 view/settings.py::get_locale。
- po 备份在 tests/pobackup/。

## 4. 依赖管理（重要）

**requirements.txt 由 `tools/update_req.py` 生成，不要手改。** 改依赖请编辑 update_req.py 内的依赖矩阵后运行：

```
python tools/update_req.py docker          # Docker 最小集
python tools/update_req.py docker[all]     # 全部可选依赖
python tools/update_req.py gae             # GAE 集
python tools/update_req.py gae[B2,1,t2,20m]  # GAE + 自定义 worker.yaml 参数
```

同时它会改写 config.py/main.py 的构建日期。可选依赖（数据库/队列/平台）以注释形式保留在 requirements.txt。

## 5. 内置 recipe 维护

```
python tools/archive_builtin_recipes.py      # *.recipe → builtin_recipes.xml+zip（增量）
python tools/trim_recipes.py en zh es        # 按语言裁剪
```

## 6. 代码修改注意事项（踩坑清单）

1. **双 DB 后端**：改 db_models.py 实体时，确认该改动在 weedata（NoSQL）与 peewee（SQL）两侧都能工作；涉及表结构变更需递增 `AppInfo.dbSchemaVersion` 并在 `db_models_sql.py` 写迁移（NoSQL 无需迁移）。
2. **新配置项优先放 JSON 字段**（base_config/book_config/custom），避免动表结构。
3. **builtins 全局变量**（appDir/appVer/default_log/_）在 main.py 注入；IDE 类型靠 typings/__builtins__.pyi。新文件可直接用，但不要 import main。
4. **lib/ 是 vendored 代码**：calibre/readability/polyglot/css_selectors/tinycss 尽量不改；确需改（如 readability 的 shorten_title）在 tests/readme.developer.md 有记录惯例。
5. **safe_eval** 执行用户 recipe 代码（ke_utils.py），沙箱封禁内建名/dunder——给 recipe 增加可用名时改这里。
6. **发送间隔 10s**：send_to_kindle 有防 Kindle 垃圾机制的 sleep，测试时注意。
7. **GAE 差异**：代码中条件使用 google.appengine 的地方不要无条件 import；二进制不可用（mp3 合并自动回退 pymp3cat.py）。
8. **/worker、/url2book 是任务回调路由**（key 校验），不是普通页面，GAE 上被 dispatch 到 worker 服务。
9. **runtests.py 尾部 testonly 硬编码**（见上）。
10. **Windows 环境**：本仓库工作区约定使用 PowerShell（见 AGENTS.md）；tools 下有 .bat 脚本。

## 7. 版本发布 / CI

- 版本号在 `main.py::__Version__`（当前 3.4.7）。
- CI 两个 workflow 均手动触发：docker_build_push（tag=__Version__，多架构）与 mailfix_build_push。无自动测试 CI。
- 用户向文档在 docs/（Jekyll，中英双语），发布新功能时记得同步 changelog（docs/Chinese/changelog.md、docs/English/changelog_en.md）。

## 8. 深入阅读

- `tests/readme.developer.md`：电子书生成调用链、calibre 定制点、Let's Encrypt、dev_appserver 沙箱、平台免费额度对比。
- `docs/Chinese/deployment.md`：官方部署手册（GAE 云端 Shell 一键、Docker、常见 GAE 陷阱）。
- `docs/Chinese/extension.md`：浏览器扩展与 recipe 制作。
- `docs/Chinese/reader.md`：在线阅读器使用。
