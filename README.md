# A股多维监控 · 模块01：核心宽基 ETF 资金风向标

独立于 `qdii-etf-premium-tracker` 的研究采集仓库。首批监测沪市8只ETF：
`510300`、`510310`、`510330`、`510050`、`510180`、`510500`、`512100`、`588080`。

## 当前进度：上交所清算后份额的采集验证

工作流：[`SSE ETF clearing shares (validation stage)`](.github/workflows/collect-sse-shares.yml)

- 北京时间交易周的工作日20:15、以及周二至周六07:10，尝试读取上交所各基金基本信息页面。
- 只接受页面“基金规模／总份额（万份）”下明确标注日期、基金代码的行；转换单位后保存 `data/sse_shares.csv`。
- 同日份额记录若与历史保存值冲突，程序中断等待人工核对，绝不无提示覆盖。
- 每次将抓取状态写入 `output/sse_diagnostic.json`，由 Actions 保存为诊断工件。
- 页面如由 JavaScript 动态填充，程序可能无法读出数据，将明确失败并留下诊断，**绿色的 GitHub Actions 本身不代表已取得有效行情数据**。
- **目前尚未采集或验证基金单位净值**，所以不计算1/5/20日净申赎金额，不推断国家队买卖。深市份额、250日分位、历史拆合份额校正均尚未接入。

## 手动运行

进入 **Actions → SSE ETF clearing shares (validation stage) → Run workflow**。
执行后先检查日志，再查看 Artifacts 的 `sse-shares-diagnostic`；确认真实日期和8只ETF的解析结果。后续只有在实测验证和净值接入完成后，才应让 ChatGPT 定时简报读取这个仓库并发布正式的资金方向判定。

研究原则：先观察资金行为，再通过长期历史和持续跟踪评估它的预测能力。宽基 ETF 份额变化不是汇金操作的直接证据。
