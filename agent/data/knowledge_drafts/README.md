# 核心 CS 知识草稿：第 1 批（50 条）

正文与结构化字段见 `batch_001.json`。用户已在聊天中确认这 50 条**内容审核通过**，审批证据及草稿 SHA-256 记录在 `batch_001.approval.json`。原草稿保留 `draft_pending_human_review` 状态作为不可变审阅快照；来源许可仍待核，**不得直接导入、生成 Embedding 或发布**。来源仅作事实核对入口，中文表述为原创摘要，不复制原文。

运行 `python -m scripts.validate_knowledge_draft --input data/knowledge_drafts/batch_001.json` 可检查数量、七领域覆盖、字段、来源引用、旧 ID 冲突和先修依赖环。它不证明事实正确或许可合规。现有 `import_curated_knowledge` 只接收带人工审核字段的独立 JSON 数组，不能直接接收本草稿对象。

内容审核已由用户整体确认。以下清单仍用于来源/许可复核：打开来源 URL 定位到 `source_locator`，核对具体版本、作者、许可。对来源不充分的条目补充更精确的 URL 或更换来源，并记录修改。尤其注意 NIST DADS 部分词条有第三方版权，RFC 原文修改权受限制，Linux/Python 等滚动文档应锁定审核时的版本。清单勾选本身不等于许可批准。

## 算法（8）

- [ ] `algo_insertion_sort` 插入排序
- [ ] `algo_heap_sort` 堆排序
- [ ] `algo_topological_sort` 拓扑排序
- [ ] `algo_bellman_ford` Bellman–Ford 最短路径
- [ ] `algo_floyd_warshall` Floyd–Warshall 全源最短路径
- [ ] `algo_kmp` KMP 字符串匹配
- [ ] `algo_backtracking` 回溯搜索
- [ ] `algo_amortized_analysis` 均摊复杂度分析（动态数组例子需补充来源）

## 数据结构（8）

- [ ] `ds_array` 数组与随机访问
- [ ] `ds_dynamic_array` 动态数组扩容（需核对具体实现与来源）
- [ ] `ds_linked_list` 单向链表
- [ ] `ds_binary_heap` 二叉堆
- [ ] `ds_trie` Trie 前缀树
- [ ] `ds_disjoint_set` 并查集
- [ ] `ds_adjacency_list` 图的邻接表
- [ ] `ds_b_tree` B 树

## 操作系统（7）

- [ ] `os_process_thread` 进程与线程（需补充分工定义来源）
- [ ] `os_context_switch` 上下文切换
- [ ] `os_page_table` 页表与地址转换
- [ ] `os_page_fault` 缺页异常
- [ ] `os_mutex` 互斥锁
- [ ] `os_semaphore` 计数信号量（需核对用户态定义来源）
- [ ] `os_scheduler_fairness` 调度公平性（需固定内核版本）

## 计算机网络（7）

- [ ] `net_tcp_retransmission` TCP 重传
- [ ] `net_http_methods` HTTP 方法语义
- [ ] `net_dns_recursive_resolution` DNS 递归解析（需结合现行规范）
- [ ] `net_dns_authoritative` DNS 权威服务器
- [ ] `net_ipv6_header` IPv6 基本首部
- [ ] `net_http_cache_validation` HTTP 缓存再验证
- [ ] `net_tls13_handshake` TLS 1.3 握手

## 数据库（7）

- [ ] `db_multicolumn_index` 多列索引
- [ ] `db_sequential_scan` 顺序扫描
- [ ] `db_hash_join` 哈希连接
- [ ] `db_mvcc_snapshot` MVCC 快照
- [ ] `db_wal` 预写式日志 WAL
- [ ] `db_foreign_key` 外键约束
- [ ] `db_explain_analyze` EXPLAIN ANALYZE

## 软件工程（6）

- [ ] `se_version_control` 版本控制与提交
- [ ] `se_code_review` 代码审查（需补充审查实践来源）
- [ ] `se_unit_test` 单元测试
- [ ] `se_integration_test` 集成测试（需补充明确的集成测试来源）
- [ ] `se_ci_pipeline` 持续集成流水线
- [ ] `se_semantic_versioning` 语义化版本号

## 编程语言（7）

- [ ] `pl_python_name_binding` Python 名称绑定与作用域
- [ ] `pl_python_mutability` Python 可变对象与不可变对象
- [ ] `pl_python_generator` Python 生成器
- [ ] `pl_python_decorator` Python 装饰器
- [ ] `pl_python_exception` Python 异常传播
- [ ] `pl_python_type_hints` Python 类型注解
- [ ] `pl_python_context_manager` Python 上下文管理器
