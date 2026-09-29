# 核心 CS 知识草稿：第 2 批（50 条）

正文及字段见 [batch_002.json](batch_002.json)。本批均为原创中文摘要；用户已在聊天中确认本批 50 条**内容审核通过**，证据及草稿 SHA-256 记录在 `batch_002.approval.json`。原草稿保留 `draft_pending_human_review` 状态作为不可变审阅快照；来源许可仍待核，不能导入、生成 Embedding 或发布。第 1 批的审批记录不适用于本批。

内容审核已由用户整体确认。以下清单继续用于来源定位、事实和许可复核；勾选不等于来源许可批准。对滚动版本文档需要锁定具体审核版本；NIST DADS 中个别词条可能有第三方版权；RFC 仅链接原文并保留原创摘要；cp-algorithms 是社区参考，四条相关知识点需独立事实复核。所有来源的许可状态仍是 `pending`。

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

从 `agent` 目录运行：

```bash
python -m scripts.validate_knowledge_draft --input data/knowledge_drafts/batch_002.json
```

该校验只覆盖结构、数量、ID 冲突和先修依赖等，不证明事实准确性、来源定位或许可合规。审批后应创建与第 1 批同型的独立审批记录并绑定草稿哈希；修改草稿须重新审核。
