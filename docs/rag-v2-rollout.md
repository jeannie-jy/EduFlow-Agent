# RAG v2 分阶段上线记录

`dev-v2.0` 从 `origin/main` 建立。此分支当前只实现第一阶段的基础设施，**尚未通过第一阶段内容与质量验收**；第二、三阶段不可标记为完成。`KNOWLEDGE_V2_ENABLED` 默认是 `false`，生产读取仍走旧库。

## 第一阶段：已实现的基础设施

- `0028_knowledge_library` 建立来源、不可变版本、片段、项目授权表及 PostgreSQL 向量/三元组索引；旧 `knowledge_base` 不删除。
- 向量固定为 `text-embedding-v4` 的 1024 维；模型或维度不符时不写入向量。无凭证时降级为关键词检索。
- 旧 22 条可由 `python -m scripts.seed_knowledge_v2` 迁移，稳定 `source_key` 不变，标注为 `legacy` 而非人工审核通过。
- `python -m scripts.import_curated_knowledge --input reviewed.json --dry-run` 验证七领域编辑记录。实际导入须由编辑确认 `reviewed_by`、权威来源、许可、先修关系、章节、难度和可视化元数据；`--embed` 才允许外部 Embedding 请求及费用。
- 检索支持数据库层作用域过滤、关键词与向量 RRF、本地确定性排序及具体 `version`/`section`/`locator`。API、工具和直接检索共用同一 v2 搜索函数；空查询和无命中返回空列表。

## 第一阶段：未满足的发布门槛

1. **内容**：目前数据库仍只有原有 22 条 legacy 种子；`agent/data/knowledge_drafts/batch_001.json` 的 50 条草稿已获用户聊天确认的内容审核，证据绑定在 `batch_001.approval.json`。第 1 批 18 个来源的初步许可核查记录在 `batch_001.source_audit.json`；用户确认非商用，Pro Git 按此限制评估。NIST 的 15 条逐词条审阅记录在 `batch_001.nist_entry_audit.json`，发现 1 条来源错误、4 条需要补充证据，明确不构成发布许可。第 2 批另有 50 条待审草稿（`batch_002.json`）；距约 280 条目标仍需再编写约 158 条。两个批次均未完成来源许可签核、导入或发布。内容审核不等于来源许可与数据库验收。
2. **迁移**：已验证 Alembic 离线 SQL 能生成，但尚须在测试 PostgreSQL/pgvector 数据库实际升级、回填、回滚演练。使用 `python -m scripts.compare_knowledge_versions --dataset evals/datasets/retrieval_production_v1.jsonl --output <report.json>` 比对新旧排名及稳定 ID。
3. **检索质量**：现有集仅 10 个生产检索用例，必须扩为七领域且含近义、易混与库外主题的人工标注集；在目标库实测 Recall@5 ≥ 90%、引用正确率 ≥ 95%，并核查无来源不附会引用。现有代码测试不能替代这些指标。
4. **切换**：只有以上完成且旧项目引用仍可解析，才在测试环境开启 `KNOWLEDGE_V2_ENABLED=true`，通过端到端教学输出和回滚演练后逐步切生产。

## 第二、三阶段入口（尚未实施）

第二阶段需要持久化教师资料、DOCX/分片解析、显式索引同意、异步任务与重试、所有者和项目授权接口、删除清理、严格资料模式及跨租户测试。`0028` 的项目授权表仅是将来使用的结构，**不表示资料库已经接通**。

第三阶段须先建立管理员 URL 白名单、定期差异同步和待审版本，再通过人工许可/版本审核发布。优先候选为 NIST DADS、RFC Editor、Python 官方文档和 PostgreSQL 16 官方文档；MDN 在许可确认前只保存原文链接及自行撰写的摘要。所有来源均需保留原 URL、机构/作者、版本、章节、许可、抓取时间和校验值。未经许可，不镜像全文。

## 环境与成本

索引或在线评测只有在明确提供规范模型凭证时才会产生 Embedding 调用；本地词法检索和排序不调用付费 Reranker。在线评测另需项目既有的显式 `EDUFLOW_ALLOW_ONLINE_EVAL=1` 确认机制。上线前应测量向量数量、每批 token、查询延迟和计费额。
