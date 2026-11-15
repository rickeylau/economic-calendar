# Economic Calendar — filtered

为 SPX / ES 交易使用的独立经济日历，默认从 Compass Economic Calendar 公开完整 ICS 读取数据，仅保留指定类别。不是 TradingView 官方数据。

## 安装

1. 新建 GitHub 仓库 `economic-calendar`（Public，用于无认证 ICS 订阅；不要把私密 URL 或密钥写入本项目）。
2. 上传 `filter_calendar.py`、`config.json`、`test_filter_calendar.py`、`README.md`、`.gitignore`（可选）。
3. 若网页漏掉隐藏目录，手动创建 `.github/workflows/update-calendar.yml`，将 ZIP 中同名文件的完整内容粘贴并提交。GitHub 会自动创建目录。
4. Actions → Update Economic Calendar → Run workflow → main。保存工作流时也会自动触发一次，无需重复启动。
5. 确认 `Generate filtered calendar` 和 `Publish calendar` 成功，且根目录出现 `economic.ics`。
6. Google Calendar → 其他日历 → + → 通过网址添加；使用 `https://raw.githubusercontent.com/你的用户名/economic-calendar/main/economic.ics`。新日历显示正常后取消订阅旧的 Economic Calendar。

## 配置

`config.json` 中的 `source_url` 默认使用 Compass 全量日历（https://compasseconomiccalendar.github.io/compass_calendar.ics）。如原先使用不同的公开 ICS，可替换这个 URL。若源为私人/付费订阅，不应将 URL 或内容发布到公开仓库，需另外设计私有同步。

`keep` 中每个布尔值控制对应类别。先排除 Fed、FOMC、休市和提前收盘，再以分类和标题白名单匹配。未列出的事件不保留；包括期货换月/期货到期（除与期权共同到期的 Quad Witching）、房屋数据、工业产出、工厂订单、JOLTS 等。Treasury Quarterly Refunding Announcement 不属于拍卖，默认排除。

保留 CPI/PPI/PCE、全国就业/NFP/失业率、GDP/零售销售、ISM/PMI、Treasury Auction、Jobless Claims、Consumer Confidence、Options Expiration（包含 OPEX/Quad Witching；如源提供 VIX 结算或期权到期也会保留）。缺失类别不会自动补造。当前 Compass 快照没有 Consumer Confidence，也未提供独立 VIX 结算；ISM 有估算标签，不能视作正式确认时间。

脚本保留原始事件 UID、开始/结束时间、时区定义及描述，不推测事件日期。日志显示每类保留数量和总计。无事件或解析失败时不覆盖旧文件。来源说明：https://compasseconomiccalendar.github.io/ 。使用前请核对数据发布机构/交易所官方时间及上游数据使用条款；本项目只用于计划提醒，不用于自动交易决策。

## 运行

Python 3.12；仅使用标准库，无需 API Key 或第三方依赖。每小时 UTC 第 37 分钟检查一次，修改配置后亦会触发。上游自身刷新周期及 Google 的订阅刷新周期独立于此工作流；并不保证每小时更新实际数据。公开仓库定时工作流长期不活跃可能被 GitHub 停用，届时需手动启用。

本地测试：`python -m unittest -v`；真实抓取：`python filter_calendar.py`。本地单元测试已通过；首次真实网络下载需在 GitHub Actions 验证。未附预生成 ICS，避免订阅空文件。
