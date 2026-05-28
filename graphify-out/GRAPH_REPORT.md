# Graph Report - odoo  (2026-05-28)

## Corpus Check
- 52454 files · ~37,718,919 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 152 nodes · 181 edges · 30 communities (19 shown, 11 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 6 edges (avg confidence: 0.83)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8e82091d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]

## God Nodes (most connected - your core abstractions)
1. `Kingsmvps Pipeline (V8.2)` - 10 edges
2. `enabledPlugins` - 8 edges
3. `Get-SystemDir()` - 8 edges
4. `project_version_map` - 7 edges
5. `project_dir_map` - 7 edges
6. `BackToConfirm()` - 7 edges
7. `Atomic-WriteFile()` - 6 edges
8. `Get-OnlineAddonsRoot()` - 5 edges
9. `Format-YamlScalar()` - 4 edges
10. `Write-YamlObject()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `ServiceAnnouncement` --semantically_similar_to--> `ServiceQuestion`  [INFERRED] [semantically similar]
  19/odoo19_e_service/models/service_announcement.py → 19/odoo19_e_service/models/service_question.py
- `ServiceHolidayWizard` --shares_data_with--> `ServiceHoliday`  [INFERRED]
  19/odoo19_e_service/wizard/service_holiday_wizard.py → 19/odoo19_e_service/models/service_holiday.py
- `ServiceHolidayWizard.generate` --references--> `ServiceHoliday`  [EXTRACTED]
  19/odoo19_e_service/wizard/service_holiday_wizard.py → 19/odoo19_e_service/models/service_holiday.py
- `ServiceQuestion` --references--> `ServiceQuestionCategory`  [EXTRACTED]
  19/odoo19_e_service/models/service_question.py → 19/odoo19_e_service/models/service_question_category.py
- `ServiceQuestion` --shares_data_with--> `ServiceTaxonomy`  [EXTRACTED]
  19/odoo19_e_service/models/service_question.py → 19/odoo19_e_service/models/service_taxonomy.py

## Hyperedges (group relationships)
- **Exchange Rate Fetch Pipeline (Bank Spot + Historical + Customs)** — odoo19_e_service_get_spot_exchange_rate_bank, odoo19_e_service_get_historical_exchange_rate_bank, odoo19_e_service_get_exchange_rate_customs [INFERRED 0.85]
- **Contract Expiry Notification Flow** — odoo19_e_service_contract_notify_check, odoo19_e_service_compute_contract_notify, odoo19_e_service_TeamsNotifyMessage [EXTRACTED 1.00]
- **Holiday Import Wizard Flow** — odoo19_e_service_ServiceHolidayWizard, odoo19_e_service_generate, odoo19_e_service_get_days_from_api [EXTRACTED 1.00]

## Communities (30 total, 11 thin omitted)

### Community 1 - "Community 1"
Cohesion: 0.33
Nodes (3): ServiceTaxonomy, ServiceTaxonomyLine, ServiceTaxonomyPoints

### Community 2 - "Community 2"
Cohesion: 0.40
Nodes (6): ServiceAnnouncement, ServiceQuestion, ServiceQuestionCategory, ServiceTaxonomy, ServiceTaxonomyLine, ServiceTaxonomyPoints

### Community 3 - "Community 3"
Cohesion: 0.40
Nodes (6): ResConfigSettings (e_service), _TeamsNotifyMessage, compute_contract_notify, Contract Expiry Notification Pattern, contract_notify_check, Teams Webhook Configuration Pattern

### Community 6 - "Community 6"
Cohesion: 0.83
Nodes (4): ServiceExchangeRate, get_exchange_rate_customs, get_historical_exchange_rate_bank, get_spot_exchange_rate_bank

### Community 7 - "Community 7"
Cohesion: 0.50
Nodes (4): ServiceHoliday, ServiceHolidayWizard, ServiceHolidayWizard.generate, ServiceHolidayWizard.get_days_from_api

### Community 19 - "Community 19"
Cohesion: 0.16
Nodes (28): Acquire-Lock(), Atomic-WriteFile(), BackToConfirm(), Clear-StalePending(), ConvertFrom-Yaml(), ConvertTo-Yaml(), Format-YamlScalar(), Get-ExistingModules() (+20 more)

### Community 20 - "Community 20"
Cohesion: 0.13
Nodes (14): Blocker 類型, code:block1 (Odoo 任務), code:block2 (.claude/), Kingsmvps Pipeline (V8.2), QA 檢查項目, Stage 標記一覽（Unified Marker Table）, 任務流向, 前置需求 (+6 more)

### Community 21 - "Community 21"
Cohesion: 0.13
Nodes (14): project_dir_map, 2508014 凌越生醫-商務管理平台, A11-Odoo產品功能研發, eservice, eService2.0, 鴻久, 鴻久用戶, project_version_map (+6 more)

### Community 24 - "Community 24"
Cohesion: 0.15
Nodes (12): autoUpdatesChannel, enabledMcpjsonServers, hooks, Stop, UserPromptSubmit, language, permissions, allow (+4 more)

### Community 27 - "Community 27"
Cohesion: 0.25
Nodes (8): enabledPlugins, caveman@caveman, code-review@claude-plugins-official, context7@claude-plugins-official, hookify@claude-plugins-official, pr-review-toolkit@claude-plugins-official, security-guidance@claude-plugins-official, superpowers@claude-plugins-official

## Knowledge Gaps
- **53 isolated node(s):** `2508014 凌越生醫-商務管理平台`, `A11-Odoo產品功能研發`, `eService2.0`, `鴻久`, `鴻久用戶` (+48 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `enabledPlugins` connect `Community 27` to `Community 24`?**
  _High betweenness centrality (0.010) - this node is a cross-community bridge._
- **What connects `2508014 凌越生醫-商務管理平台`, `A11-Odoo產品功能研發`, `eService2.0` to the rest of the system?**
  _54 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 20` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._
- **Should `Community 21` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._