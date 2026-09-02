# 投递流水线（核心业务流）

三条主要任务链：**① 定时/手动 RSS 投递**、**② URL/文本转书（url2book）**、**③ 入站邮件**。它们最终都汇到 `send_to_kindle()`。

## ① 定时 / 手动投递（RSS 订阅）

```
定时层（二选一）
  GAE:     cron.yaml 每小时 GET /deliver（X-Appengine-Cron 头）
  自托管:  apscheduler :40 / celery beat :50 / rq cron / 主机 cron `python main.py deliver check`
      ↓
view/deliver.py :: /deliver
  ├─ MultiUserDelivery：遍历所有用户与 BookedRecipe
  │    · 到点判定：书级 send_times 优先，否则用户级 send_days/send_time
  │    · GAE cron 场景 hr=(now.hour+1)%24 提前一小时匹配（整点 cron 提前排任务）
  └─ queueOneBook()：separated=True 的书逐本建任务；其余按用户合并为一个任务
       （recipeId 列表逗号连接；URL 中 ':' 转义为 '__'）
       → task_queue_adpt.create_delivery_task({userName, recipeId, reason, key})
      ↓
work/worker.py :: /worker（GAE 上由 dispatch.yaml 路由到 worker 服务）
  校验 key == DELIVERY_KEY → WorkerImpl(userName, recipeId, reason)
      ↓
WorkerImpl 执行（核心流程）
  1. 取 KeUser；未指定 recipeId → user.get_booked_recipe() 全部订阅
  2. UrlOpener.set_proxy(user.cfg('proxy'))   ← 全局代理
  3. GetAllRecipeSrc()：按 recipe_id 前缀取源码
       builtin: → recipes/builtin_recipes.xml（元数据）+ builtin_recipes.zip（源码）
       upload:  → Recipe.src（数据库）
       custom:  → GenerateRecipeSource() 现场生成源码（不入库）
       手动指定未订阅的 custom → cloneToBookedRecipe() 生成临时 BookedRecipe（不落库）
  4. calibre compile_recipe(src) 编译为 recipe 类，注入运行时配置：
       delivery_reason、extra_css（合并用户自定义 CSS）、
       translator/tts/summarizer 三套配置（从 BookedRecipe 拷贝）、
       needs_subscription 时填网站账号密码、
       封面策略（多书合并→强制用户全局 covers；单书未设封面→应用全局开关）
  5. 合并分组：separated=True → 以 rc.title 为键各成一本；否则全部并入 user.book_cfg('title') 合订本
  6. 每组 build_ebook.convert_book(roList, 'recipe', user) → 电子书二进制（格式 user.book_cfg('type')）
  7. TTS：MergeAudioSegment() 合并各 recipe 的 tts.audio_files（优先 mp3cat 二进制，否则 pymp3cat.py）
       有音频则【先于电子书】推送到 tts.send_to 或默认 kindle_email
  8. 投递（delivery_mode 可多选）：
       email → send_to_kindle()（距上次发送 <10s 先 sleep(10)，防 Kindle 垃圾邮件机制）
       local → 保存到本地 webshelf（/reader 在线阅读书架）
  9. 书和音频都为空 → save_delivery_log(status='nonews')
```

附件命名 `标题_(时间).后缀`，邮件主题 `KindleEar 日期时间`。

> 注意：v2 时代的"Hyper 内置书""退订确认邮件"逻辑在 v3 中已不存在；退订是 `/recipe/unsubscribe` AJAX 直接删 BookedRecipe + LastDelivered。

## ② url2book（浏览器扩展 / 书签 / 邮件共用）

```
触发方：
  浏览器扩展/书签 → GET|POST /url2book?userName=..&urls=a|b&title=..&key=<share_links key>&action=..&text=..
  入站邮件有链接   → inbound_email.py 建 create_url2book_task
      ↓
work/url2book.py :: Url2BookImpl（校验用户 + share key）
  action=download → u2lDownloadFile()：直接下载电子书文件原样推送
  action=debug    → u2lDebugFetch()：抓页面/文本作为附件发邮箱（调试）
  默认            → u2lFetchUrl2()：
      有 text → u2lCreateEbookFromText()：文本拼 HTML → recursive_fetch_url 补抓正文图片 → html_to_book()
      无 text → u2lPreprocessUrl()（gitbooks.io 单链 → GetGitbookChapterUrls() 展开全章节）
                → urls_to_book()（预下载每篇、提取真实标题、生成临时 recipe、convert_book）
                → send_to_kindle(fileWithTime=False)；失败记 'fetch failed'
```

## ③ 入站邮件（邮件转发/附件推送）

```
入站通道（三者择一，按部署形态）：
  GAE:            POST /_ah/mail/<addr>（app.yaml inbound_services: mail）
  Docker(mailfix): postfix content-filter → POST /mail
  mailglove:      POST /mailglove（JSON 格式）
      ↓
view/inbound_email.py :: ReceiveMailImpl
  1. 白名单校验（WhiteList）反垃圾
  2. 可选存 InBox（附件存 UserBlob）
  3. 指令解析（收件地址 dest 或主题）：
       dest=trigger → 触发投递（create_delivery_task）
       dest=convert → mobi/prc/azw 附件转 epub 再推送
       主题 !links / !article / !lang=xx → 控制链接提取模式
  4. 正文含 URL → create_url2book_task（URL 是电子书扩展名则 action=download）
     无 URL → 正文（含内联图片）html_to_book() 转书推送，或直接 HTML 邮件转发
```

`/_ah/bounce`（退信通知）仅记日志。

## 电子书构建层（lib/build_ebook.py）

三个入口，全部落到 calibre `Plumber`：
- `convert_book(input_, input_fmt, user, ...)` — input 为编译后 recipe 类（'recipe'）/ 文件名 / BytesIO
- `urls_to_book(urls, title, user, ...)` — URL 列表 → 临时 recipe → convert_book（max_articles=100）
- `html_to_book(html, title, user, imgs, ...)` — 单 HTML + 图片 → 'html' 输入

`ke_opts(user, options)`：合并用户 `custom.calibre_options` 与默认（output_profile=device、input_profile='kindle'、epub_inline_toc=True、dont_compress、dont_split_on_page_breaks、keep_images=True 等），并把 `user` 实例注入 options（calibre news.py 读取 `rm_links` 等定制行为）。

calibre 调用链（tests/readme.developer.md 记载）：`ConvertToEbook() → plumber.run() → recipe_input.convert() → BasicNewsRecipe.download() → plumber.create_oebbook() → output_plugin.convert()`。

## 排障速查

| 症状 | 检查点 |
|---|---|
| 定时投递不触发 | TASK_QUEUE_SERVICE 与部署形态是否匹配；apscheduler 是否随进程存活（gunicorn 多 worker 时注意）；`/deliver` 是否可达（DELIVERY_KEY） |
| 手动"现在推送"没反应 | `/advanced/delivernow` → SingleUserDelivery 建任务；队列后端日志；DELIVERY_KEY |
| 收到 nonews | BookedRecipe 时间表、源站 RSS 是否更新、代理 |
| 邮件没到 | send_mail_service 通道配置、白名单、Kindle 的 approved senders、10s 防垃圾 sleep |
| url2book 403/无效 key | key 必须等于用户 share_links 里的 secret_key |
