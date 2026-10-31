# 技术说明

## 分块与检索契约

`load_corpus(path)` 返回 `[(filename#cN, text), ...]`，文件名排序，块序号从 0 开始。去掉 Markdown 标题前缀及全文首尾空白后，按 Python Unicode 字符（非字节、非词元）切片：size=240，overlap=40，步长 200。最后一个块到达文本尾部即停止，不生成重复的尾块。参数要求整数、size>0、0<=overlap<size；布尔值拒绝。优点是可解释、确定且严格有界；缺点是可能切断句子或英文单词。同一份未修改文件的 ID 稳定；修改前文可能改变后续块，ID 不是内容哈希。

BM25 保留 k1=1.5、b=0.75 及原有平滑 IDF：
`idf=log(1+(N-df+0.5)/(df+0.5))`；
每个查询词的贡献为 `idf*f*(k1+1)/(f+k1*(1-b+b*dl/avgdl))`。
add 时缓存 Counter 与长度；build 计算 IDF，后续新增内容会在 search 时重建统计。search 不再遍历所有 token 来重建频数；仍逐块评分，没有倒排索引。重复查询词沿用原逻辑重复计分。按未舍入分数降序，同分按插入顺序；返回分数舍入四位。空索引、空文档、无词查询返回空结果；topk 始终先校验为 1–20 整数。

## 生成与证据

默认 demo 选取前三命中块中最多四句有词交集的摘录，去除完全重复句子；答案逐句引用块 ID，sources 只列实际采用的块所属文件，evidence 带完整块 ID、text、score。无命中直接返回资料不足，不调用模型。窗口边界可能导致摘录不完整，须核对原文。

可选 Ollama 最多取四块，提示中使用 [块ID] 标记，并要求引用。llm 模式的 evidence 表示送入模型的参考资料，不能断言模型逐条使用了它们，也不验证答案引用是否正确。保留 generate 的三项返回值兼容旧调用，元数据通过 generate_result 返回。

actual mode：demo 或 llm；fallback_reason：null、no_hits、model_error、empty_response、invalid_response、model_busy。模型网络操作超时 10 秒、响应读取最多 1 MiB+1 字节，并发槽 2 个，槽满立即抽取回退；不同 HTTP 请求独立处理，慢模型不持有索引共享锁。线程式 HTTP 服务整体并发没有生产级上限。受控替身验证异常、空响应、错误类型、成功输出和忙碌回退；未运行真实模型。

## HTTP

保留端口 8002、POST /ask 和原字段。请求体必须 UTF-8 JSON 对象；q 为非空字符串、总长<=2000（再 trim）；topk 必须整数 1–20，不能为 bool。Content-Length 必须唯一、非负十进制，最大 65536 字节；不接受 Transfer-Encoding。坏 JSON/类型/参数/长度返回 400，超大返回 413，读体超时返回 408；每次响应后关闭连接，避免未读取的坏请求体污染下一请求。未知路径 404，服务内部异常 500 且不泄漏内部异常详情。body 读取有 5 秒网络操作超时。health.mode 表示配置，ask.mode 表示实际生成结果。doc_count 沿用原含义：块数。

## 评测定义与复现

evaluation/corpus 与 tests/fixtures 是独立目录。5 份人工编写的短文覆盖消息协议、固件、检索、园艺和异常检测；queries.json 中 11 条查询及相关文件名标签人工可审阅。没有随机采样，也没有生成答案评分。运行 `python scripts/evaluate.py --k 3` 可重复输出同样排名；同时建议检查 k=1。

先检索全部候选块，再按第一次出现保留文档、截取前 k 文档。此评测仅用于 <=20 块的小固定语料；超过时明确报错，避免 public search 的 topk 限制默默截断评测。单查询 Recall@k=前 k 文档中相关文档数/所有相关文档数；MRR@k=第一个相关文档排名的倒数（未命中为 0）。对 8 条有答案查询做宏平均；3 条无答案查询不混入召回率分母，单独报告零命中数。未命中率不能等同于拒答准确率。

Python 3.14.4 本地结果：Recall@3=1、MRR@3=1；有答案零命中 0/8；无答案零命中 2/3。结果高的原因包括语料小、查询使用相似词汇；没有调参、真实用户日志、同义改写测试或规模测试。无答案查询 STM32 warranty price 仍命中 firmware.md，是词面检索的可见局限，不能据此把摘录认作有效答案。

## 一手接口资料

- Python 的 ThreadingHTTPServer 使用线程处理请求，http.server 本身面向基础服务而非生产部署：[官方说明](https://docs.python.org/3/library/http.server.html)。
- 可选生成器按 Ollama POST /api/generate 发送 model、prompt、stream=false，并读取 response：[官方 API](https://docs.ollama.com/api/generate)。

链接已于 2026-10-31 核实。实现以仓库测试和上述参数为准；不依赖外部服务即可完成演示与评测。
