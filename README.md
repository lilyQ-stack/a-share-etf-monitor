# A股多维监控 · 模块01：核心宽基 ETF 资金风向标

独立于 `qdii-etf-premium-tracker`。目标沪市8只：`510300` `510310` `510330` `510050` `510180` `510500` `512100` `588080`。

## 阶段1：清算后份额采集验证（净申赎报告尚未上线）

- 工作流：[`SSE ETF clearing shares (validation stage)`](.github/workflows/collect-sse-shares.yml)，计划北京时间周一至周五20:15及周二至周六07:10尝试运行，GitHub可能延迟。
- 官方页面：<https://www.sse.com.cn/market/funddata/volumn/etfvolumn/>。代码向其使用的 `query.sse.com.cn/commonQuery.do` 查询接口提交 `STAT_DATE` 与 `sqlId=COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L`，取 `SEC_CODE`、`STAT_DATE`、`TOT_VOL`。
- 每次尝试近9个自然日中的工作日；只有当天8只目标基金齐全且返回日期吻合才存入 `data/sse_shares.csv`。假日/未清算日期会记录 `rejected`，但不影响其他日期成功。
- `TOT_VOL` 的单位为**万份**，转换成份。拒绝缺失基金、重复基金、日期冲突、无效份额和历史更正；不使用模拟数据。日志和 Actions Artifact 中的 `sse_diagnostic.json` 保存各日期是否验证成功、失败原因。
- GitHub运行成功≠数据成功：核查数据 CSV 的最后日期和8只代码。
- **基金公司单位净值尚未采集**，因此当前不发布1/5/20日资金净申赎或国家队动向结论；历史份额拆合、深市ETF和250日分位也还没有接入。
- ChatGPT 定时简报暂未连接本仓库数据，不应将搜索新闻的宽口径数字当成已验证的8只ETF净申赎额。

## 测试步骤

进入 Actions → SSE ETF clearing shares (validation stage) → Run workflow，检查运行日志中的 `verified` 日期、`new_rows` 以及 `data/sse_shares.csv` 是否新增。若遇403、反爬、动态变更、超时等问题，请保留诊断信息，不要以未核验数据替代。

原则：先观察资金行为，再长期验证信号价值；份额净申赎不能直接归因于国家队。
