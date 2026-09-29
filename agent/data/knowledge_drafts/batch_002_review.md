# 核心 CS 知识草稿：第 2 批（50 条）

正文及字段见 [batch_002.json](batch_002.json)。本批均为原创中文摘要；用户已在聊天中确认本批 50 条**内容审核通过**，证据及草稿 SHA-256 记录在 `batch_002.approval.json`。原草稿保留 `draft_pending_human_review` 状态作为不可变审阅快照；来源许可已做**初步核查**，见 `batch_002.source_audit.json`（25 个来源元数据，24 个实际引用）和 `batch_002.nist_entry_audit.json`（11 个 NIST 词条）。两份记录均明确 `publication_clearance: false`，不能据此导入、生成 Embedding 或发布。第 1 批的审批记录不适用于本批。

内容审核已由用户整体确认。以下清单继续用于来源定位、事实和许可复核；勾选不等于来源许可批准。对滚动版本文档需要锁定具体审核版本；NIST DADS 的 `algo_lcs` 词条明确标有 CRC Press 版权，`algo_a_star` 没有对应词条，`ds_circular_buffer` 只有相关但非同一概念的词条，须替换或补充来源。`man_pipe`、`man_open` 的 6.19 源文件 SPDX 已核实；`coverage_py` 网页文档具体再利用条款仍未独立确定。`kernel_sched` 来源元数据未被使用。RFC 仅链接原文并保留原创摘要；cp-algorithms 是社区参考，四条相关知识点需独立事实复核。原审批记录的来源许可状态仍是 `pending`。

上述三个错误或不精确来源已有独立的候选修订 `batch_002.source_revision_001.json`，绑定获批草稿哈希，仅变更引用元数据，不改 50 条知识点正文。候选分别是 UC Berkeley CS188 A* 小节、MIT OCW 6.006 LCS 讲义、Linux 6.2 环形缓冲区文档。MIT OCW 材料为 CC BY-NC-SA 4.0；本项目只保留原创摘要和链接，不复制、翻译、入向量库或展示讲义。伯克利页面未取得再分发许可，亦仅链接。修订不是导入清单，不能据此发布。

用户随后在聊天中确认三处候选引用**编辑复核通过**；独立记录 `batch_002.source_revision_001.approval.json` 绑定修订文件的 SHA-256。该批准不扩展到整批来源许可，也不授权数据库导入或 Embedding。另有 `batch_002.version_pin_001.json` 记录 26 组来源或补充来源的版本、URL 与章节候选；多处已固定 Git 提交和文件对象，另有网页来源尚缺内容快照及校验值。

逐文件许可追查结果：man-pages 6.19 官方标签中的 `fork.2`、`pipe.2`、`open.2` 均标注 `Linux-man-pages-copyleft`，证据见 `batch_002.man_pages_license_evidence.json`。Coverage.py 7.16.1 发行元数据标注 Apache-2.0，但引用网页文档的具体再利用条款尚未独立确定。当前均只使用原创摘要和链接，不复制来源文字。

NIST 对 `algo_radix_sort` 的 MSD 变体及 `algo_kruskal` 的并查集/复杂度说明不足，已通过 `batch_002.source_supplement_001.json` 记录 Princeton Algorithms 4e 的补充论据，限于链接及原创摘要。独立预检 `python -m scripts.check_knowledge_batch_readiness --batch 2` 当前会拒绝测试库导入和向量索引：整批来源许可仍待签核、来源审核仍属初步、版本固定仍是候选，且没有 Embedding 同意。实际 PostgreSQL/pgvector 临时库的迁移、幂等、回滚和词法检索验证见 `../../evals/reports/rag_v2_stage1_tempdb_2026-09-29.md`。

来源修订 002 的事实核查记录在 `batch_002.source_revision_002_factcheck.json`，绑定草稿与修订文件哈希。RFC 768 的 Introduction、Format、Fields、User Interface 足以定位 UDP 条目的通用主张；COW 的 `fork(2)` 只证明 Linux 使用 COW，Linux 6.19 文档说明缺页路径，作者公开提供的 *The Linux Programming Interface* 第 24 章第 521–522 页补足只读共享页、写入陷入与私有复制机制。教材章节有版权声明，未取得再分发许可，仍只保留链接、定位与原创概述。`恢复写入` 与网络重排表述还需编辑确认；这份机器事实核查不是用户或法律审批，修订 002 依旧待审核。

## 算法（8）

- [ ] `algo_counting_sort` 计数排序
- [ ] `algo_radix_sort` 基数排序
- [ ] `algo_bucket_sort` 桶排序
- [ ] `algo_lower_bound` 二分查找下界
- [ ] `algo_a_star` A* 启发式搜索
- [ ] `algo_kruskal` Kruskal 最小生成树
- [ ] `algo_edmonds_karp` Edmonds–Karp 最大流
- [ ] `algo_lcs` 最长公共子序列

## 数据结构（8）

- [ ] `ds_deque` 双端队列
- [ ] `ds_circular_buffer` 环形缓冲区
- [ ] `ds_skip_list` 跳表
- [ ] `ds_segment_tree` 线段树
- [ ] `ds_fenwick_tree` 树状数组
- [ ] `ds_bloom_filter` 布隆过滤器
- [ ] `ds_sparse_table` 稀疏表
- [ ] `ds_adjacency_matrix` 图的邻接矩阵

## 操作系统（7）

- [ ] `os_copy_on_write` 写时复制
- [ ] `os_tlb` TLB 地址转换缓存
- [ ] `os_lru_page_replacement` LRU 页面替换
- [ ] `os_pipe_ipc` 管道进程间通信
- [ ] `os_priority_inversion` 优先级反转
- [ ] `os_rw_lock` 读写锁
- [ ] `os_file_descriptor` 文件描述符

## 计算机网络（7）

- [ ] `net_udp_datagram` UDP 数据报
- [ ] `net_cidr_prefix` IPv4 CIDR 网络前缀
- [ ] `net_tcp_congestion_control` TCP 拥塞控制
- [ ] `net_http_status_codes` HTTP 状态码语义
- [ ] `net_http2_multiplexing` HTTP/2 多路复用
- [ ] `net_quic_streams` QUIC 流
- [ ] `net_dns_ttl` DNS TTL 与缓存

## 数据库（7）

- [ ] `db_serializable_isolation` 可串行化隔离
- [ ] `db_index_only_scan` 仅索引扫描
- [ ] `db_vacuum` PostgreSQL VACUUM
- [ ] `db_checkpoint` 数据库检查点
- [ ] `db_unique_constraint` 唯一约束
- [ ] `db_deadlock_detection` 数据库死锁检测
- [ ] `db_analyze_statistics` 查询规划统计信息

## 软件工程（6）

- [ ] `se_branching` Git 分支协作
- [ ] `se_merge_conflict` 合并冲突
- [ ] `se_test_double` 测试替身 Mock
- [ ] `se_code_coverage` 代码覆盖率
- [ ] `se_threat_modeling` 威胁建模
- [ ] `se_api_compatibility` 语义化版本与 API 兼容性

## 编程语言（7）

- [ ] `pl_python_iterator_protocol` Python 迭代器协议
- [ ] `pl_python_async_await` Python async/await
- [ ] `pl_python_dataclass` Python dataclass
- [ ] `pl_python_descriptor` Python 描述符协议
- [ ] `pl_python_pattern_matching` Python 结构化模式匹配
- [ ] `pl_python_import_system` Python 模块导入
- [ ] `pl_python_default_arguments` Python 默认参数求值时机

## 验证

2026-09-29 的版本/章节复核检查了 PostgreSQL 16 七个条目的具体章节，Python 3.14.7 具体页面与 PSF 许可证，以及 Linux 6.19、man-pages 6.19、Coverage.py 7.16.1 等候选版本。RFC 已按编号和章节定位。cp-algorithms 四篇文章已锁定仓库提交与各自文件对象 ID，见 `batch_002.cp_algorithms_version_evidence.json`；OWASP 威胁建模页的源 Markdown 及 Pro Git 两节书稿也已锁定提交与文件对象 ID，分别见 `batch_002.owasp_version_evidence.json` 和 `batch_002.pro_git_version_evidence.json`。渲染网页仍可能变化。复核还发现 `os_copy_on_write` 当前引用的 Linux `Page Tables` 页面明确把 COW 细节列为范围外；`batch_002.source_revision_002.json` 提议以 `fork(2)` 为主引用，并以 Linux 6.19 `rtapp` 页面补充写时复制触发缺页的证据。UDP 草稿没有 IPv6 专有断言，RFC 768 的引言、报文格式和字段足以支撑现有条目；修订提议去除引用定位中的 IPv6 待核语句，RFC 8200 §8.1 留作未来扩展资料。man-pages 6.19 官方标签中的 `fork.2`、`pipe.2`、`open.2` 源文件标头和对应许可证文本已核对，提交及文件对象 ID 见 `batch_002.man_pages_license_evidence.json`。修订 002 尚未经用户编辑复核，COW 的具体实现步骤仍待进一步佐证。

从 `agent` 目录运行：

```bash
python -m scripts.validate_knowledge_draft --input data/knowledge_drafts/batch_002.json
```

该校验只覆盖结构、数量、ID 冲突和先修依赖等，不证明事实准确性、来源定位或许可合规。另可运行 `python -m scripts.audit_knowledge_source_resolution --batch 2` 获取 50 条逐条候选 URL、版本和章节；当前有 2 条待复核来源修订与 9 条未固定内容快照的网页来源。加 `--strict` 会在这些缺口存在时以非零状态退出。这个只读清单不是可导入目录，整批许可、导入与 Embedding 审批仍需单独完成。
