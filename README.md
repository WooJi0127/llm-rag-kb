# llm-rag-kb · 本地知识库问答

把 UTF-8 Markdown / TXT 笔记放进目录，通过 BM25 检索相关文本，再给出带块引用的摘录。默认只需 Python 标准库；可选本地 Ollama 生成答案。适合演示检索、证据定位、失败回退和接口边界处理。

## 已实现

- 长文使用 240 字窗口、40 字重叠；无标点也不会越界，文件名和块序号稳定。
- 中文按单字、英文与数字按词检索；缓存词频，同分按语料顺序排列。
- Web 与 CLI 均保留；API 返回实际模式、回退原因以及可展开的证据。
- 空命中明确“资料不足”；非法请求返回 4xx；模型出错、空输出或繁忙时回退抽取。
- 标准库测试、独立小语料检索评测与 Python 3.10 / 3.14 CI 配置。

## 三分钟启动

需要 Python >=3.10、Git；不需要 pip 安装。先下载项目：

```text
git clone https://github.com/WooJi0127/llm-rag-kb.git
cd llm-rag-kb
```

Windows PowerShell：

```powershell
$env:USE_LLM='0'
python run.py ask "MQTT"
python run.py
```

POSIX shell：

```sh
export USE_LLM=0
python run.py ask "MQTT"
python run.py
```

打开 [本地页面](http://localhost:8002/)，点击 MQTT 示例，检查答案后的块 ID 与展开证据。Ctrl+C 停止。若系统只有 `python3`，把命令中的 `python` 替换为 `python3`。

把自己的 `.md` / `.txt` 文件放入 `data/`，重启重建索引。仅读取该目录一层的 UTF-8 文本；不处理 PDF、Word 和子目录。

可选模型：自行安装并运行 Ollama、准备模型后，PowerShell 设置 `$env:USE_LLM='1'`；POSIX 设置 `export USE_LLM=1`，再启动。默认 `OLLAMA_MODEL=qwen2.5:1.5b`、`OLLAMA_URL=http://localhost:11434/api/generate`。本次未下载模型、未验证真实模型质量。配置远程模型 URL 会把检索证据发送到该 URL。

环境变量还包括 `RAG_PORT`（8002）、`RAG_DATA`（默认项目 `data/`）。PowerShell 示例：`$env:RAG_DATA='./data'`；POSIX：`export RAG_DATA=./data`。

## 验证与实测

启动前可执行：

```sh
python -m unittest discover -s tests -v
python scripts/evaluate.py --k 1
python scripts/evaluate.py --k 3
```

2026-10-31，Windows / Python 3.14.4：23 个测试通过；包括真实本地 HTTP 请求、慢模型替身期间读取 health、模型失败和空输出、无效 Unicode 问题返回 400，以及强制旧编码环境下的命令入口。命令输出统一为 UTF-8。Python 3.10 已配置到 CI，本地未执行；GitHub CI 结果以实际运行记录为准。

独立评测含 5 份文档、11 条人工标注查询（中文 3、英文 3、跨主题 2、无答案 3）。文档级 Recall@3=1.000、MRR@3=1.000；8 条有答案查询零命中 0 条，3 条无答案查询零命中 2 条。`STM32 warranty price` 没有答案却仍命中文档，说明词面命中不能证明答案正确。该小样例与回归测试夹具分离，不能代表真实业务或生成答案准确率。完整输出见 [评测结果](evaluation/results-k3.json)，定义见 [技术说明](docs/technical.md)。

## 接口与结构

- `GET /`：对话页面；`GET /health`：文本块数量与配置模式。
- `POST /ask`：JSON 对象，如 `{"q":"MQTT","topk":5}`。问题是 1–2000 字非空字符串；topk 为 1–20 的整数（不接受布尔值），请求体最多 64 KiB。
- 保留 `query/answer/sources/hits/mode/doc_count`；新增 `evidence`、`fallback_reason`。ask 的 mode 是实际模式；health 的 mode 是配置值，并带 `mode_is_configured=true`。
- `rag/corpus.py` 分块，`rag/retriever.py` 检索，`rag/generator.py` 生成，`app.py` HTTP，`scripts/evaluate.py` 离线评测。

[技术说明](docs/technical.md) · [60–90 秒演示与面试问题](docs/demo.md) · [MIT License](LICENSE)

## 使用范围与限制

这是本地教学与求职演示服务，保留原有 `0.0.0.0:8002` 监听方式，没有登录或生产部署防护。只在可信网络运行。没有向量检索、语义重排或自动事实核查；中文单字分词容易产生无关命中，固定窗口也可能截断句子。证据能帮助人工核对，不能保证模型引用正确或消除幻觉。模型并发限制为 2，超出立即回退；10 秒是网络操作超时，不是严格端到端时限。未测生产吞吐、真实模型和浏览器视觉效果。

## 第一次接触：它做什么，怎么跑，怎样算成功

这个项目相当于一个“会帮你翻笔记的问答框”。你给它一批文字资料，再输入问题，它先寻找出现相关词的文字块，然后摘出句子，并在答案后标上来源。默认不需要大模型，也不会凭空补充知识；如果选用 Ollama，它会把找到的资料交给模型组织语言，失败后仍能退回摘录。

执行顺序是：读取 data 文件夹 → 每 240 字切一块，相邻两块重复 40 字 → 为文字建立词频索引 → 收到问题后排列相关块 → 返回答案、实际模式和证据。没有找到任何相关块时，会说明资料不足；找到了块也要自行核对它是否真的回答了问题。

启动时，先确认装好 Python，在项目文件夹打开终端，按上面的系统示例设置 USE_LLM=0，再运行 `python run.py`。看到终端打印对话地址后，在浏览器打开 localhost:8002，输入 MQTT。也可以运行 `python run.py ask "MQTT"` 直接在终端查看。

判断成功看三件事：网页能打开；提问后能看到答案、demo 模式和来源块，展开后能读到原文；运行测试命令最后显示 OK。输入不存在的英文关键词（如 xyzzynonexistent）应得到“资料不足”。如果页面显示“请求失败”，先看终端服务是否仍在运行，再检查端口和问题内容。
