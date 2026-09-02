# Recipe 机制与扩展点

## 1. Recipe 三类 ID（贯穿全项目的核心概念）

| 前缀 | 存储位置 | 生成/来源 | 相关代码 |
|---|---|---|---|
| `builtin:<name>` | `application/recipes/builtin_recipes.xml`（元数据索引）+ `builtin_recipes.zip`（源码） | calibre 官方 recipe 打包，**不入数据库** | `lib/recipe_helper.py::GetBuiltinRecipeInfo/GetBuiltinRecipeSource` |
| `custom:<dbId>` | `Recipe` 表（type_='custom'，只存 url/title 等参数，**不存源码**） | 用户在 `/my` 页填 RSS 表单 | 投递时 `GenerateRecipeSource()` 现场生成源码 |
| `upload:<dbId>` | `Recipe` 表（type_='upload'，`src` 存完整 .recipe 源码） | 用户上传 .recipe 文件（先 `compile_recipe` 校验） | `view/subscribe.py` |

URL 中 `:` 转义为 `__`（如 `/tts/custom__12`）。

### GenerateRecipeSource()（lib/recipe_helper.py）
为自定义 RSS 拼一个临时 calibre recipe 子类源码（类名 `UserRecipe+时间戳`），参数来自用户 book_cfg：`oldest_article`、`use_embedded_content`（全文 RSS=True）、`auto_cleanup`（摘要模式=True，走正文提取）、`timefmt/title_fmt`、`language`、`max_articles`（默认 30）、`cover_url`。base 可选 `BasicNewsRecipe` 或 `UrlNewsRecipe`（url2book 用）。

### 内置 recipe 打包/裁剪（tools/）
- `archive_builtin_recipes.py`：把 `*.recipe` 编译合并为 xml+zip，增量式（按 mtime）。
- `trim_recipes.py`：按语言裁剪（`python trim_recipes.py en zh es`）。
- Docker 构建时自动拉 calibre 官方 recipes 更新。

### OPML
导入 `/advanced/import`、导出 `/advanced/export`（view/adv.py，lib/opml.py 解析）。

## 2. 翻译引擎（lib/ebook_translator/）

按 recipe（BookedRecipe.translator JSON）配置，`html_translator.py` 做 HTML 分段翻译并还原排版（双语对照）。

内置引擎（engines/，基类 `base.py`）：
| 类 | 服务 | 备注 |
|---|---|---|
| GoogleFreeTranslate | Google 网页免费接口 | |
| GoogleBasicTranslate | Google API（ADC/Advanced 计费版） | GAE 可用 |
| GeminiPro | Google Gemini | 经 simple_ai_provider |
| ChatgptTranslate | OpenAI 兼容 | |
| AzureChatgptTranslate | Azure OpenAI | |
| DeeplTranslate / Pro / Free | DeepL | |
| YoudaoTranslate | 有道 | |
| BaiduTranslate | 百度 | |
| MicrosoftEdgeTranslate | Edge 免费接口 | 无需 key |
| CustomTranslate | 自定义 API（JSON 模板） | 用户自填 |

**接入新引擎**：在 `engines/` 加类继承 base（实现翻译方法与语言表），在 `engines/__init__.py` 注册；前端配置页模板 `templates/book_translator.html` + `view/translator.py` 路由一般需同步。`/translator/<recipeId>/test` AJAX 可测试。

## 3. TTS 引擎（lib/ebook_tts/）

按 BookedRecipe.tts 配置，`html_audiolator.py` 把章节文本转 mp3 并合并（mp3cat 二进制优先，无则 `pymp3cat.py` 纯 Python）。worker 中音频**先于电子书**推送。

| 引擎 | 服务 | 备注 |
|---|---|---|
| GoogleWebTTSFree | Google 网页免费 | |
| GoogleTextToSpeech | google-cloud-texttospeech | 仅 GAE（依赖 gae 平台库） |
| EdgeTTSFree | edge-tts 库 | 免费 |
| AzureTTS | Azure | |
| ChatGptTTS | OpenAI | |

## 4. AI 摘要（lib/ebook_summarizer/ + lib/simple_ai_provider.py）

- `simple_ai_provider.py` 是统一 AI Chat 适配：google(Gemini)、openai、anthropic(Claude)、xai(Grok)、mistral、groq、perplexity、alibaba(通义/dashscope)。含模型列表、RPM、上下文长度、多 apiHost。openai/xai 走 OpenAI 协议，gemini/anthropic 内部转换 payload。
- `HtmlSummarizer` 按 token 预算分段摘要；引擎缺省回退 gemini。
- 配置入口 `/summarizer/<recipeId>`（v3.2+ 加入，注意 dbSchemaVersion 迁移）。

## 5. 词典（lib/dictionary/）

在线阅读器查词用（`/reader/dict` + hunspell 词根/拼写建议，依赖 chunspell + marisa-trie + indexed-gzip —— Docker 额外装这三个库的原因）。

9 引擎（`dictionary/__init__.py` 注册）：
- 在线：dict_org（DICT 协议）、dict_cn、dict_cc、merriam_webster、oxford_learners
- 本地文件（放 `DICTIONARY_DIR`）：stardict(.ifo)、mdict(.mdx/.mdd，含 lzo/salsa20/ripemd128 纯 Python 实现)、lingvo(ABBYY DSL)、babylon(.bgl)

## 6. 其他扩展点

| 扩展点 | 位置 | 说明 |
|---|---|---|
| 浏览器扩展正文提取规则 | `/ext/extractor`（view/extension.py） | JSON 规则提取；`/ext/removejs` 去 JS 抓页 |
| 书签脚本 | tools/bookmarklet_src/send_to_kindle.js | 有选区 POST HTML，否则打开 url2book 页 |
| 归档分享 | view/share.py + lib/pocket.py / wallabag.py / webdav_client.py | Evernote/Wiz 走"readability 提取后邮件发送"，Pocket OAuth 在 `/oauth2/<type>` |
| 发信通道 | back_end/send_mail_adpt.py | 新通道需实现 send 分支并加入 `avaliable_sm_services()` |
| 数据库后端 | back_end/db_models_*.py | peewee 系或 weedata 系 |
| 队列后端 | back_end/task_queue_*.py | 实现 3 个 create_xxx_task + init_task_queue_service |
| 正文提取器 | lib/readability（主力）→ lib/justext_extract（改造版 jusText）→ lib/simpleextract（兜底） | 依次回退 |
| calibre 定制参数 | 用户 custom.calibre_options（JSON） | 经 build_ebook.ke_opts 合并 |
