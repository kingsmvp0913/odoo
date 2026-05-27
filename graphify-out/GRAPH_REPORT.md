# Graph Report - odoo  (2026-05-27)

## Corpus Check
- 52451 files · ~37,697,826 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 89 nodes · 98 edges · 25 communities (15 shown, 10 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 6 edges (avg confidence: 0.83)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `15b57e3e`
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
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]

## God Nodes (most connected - your core abstractions)
1. `Get-SystemDir()` - 7 edges
2. `BackToConfirm()` - 5 edges
3. `Get-OnlineAddonsRoot()` - 4 edges
4. `Atomic-WriteFile()` - 4 edges
5. `ServiceExchangeRate` - 4 edges
6. `ServiceQuestion` - 4 edges
7. `Format-YamlScalar()` - 3 edges
8. `Write-YamlObject()` - 3 edges
9. `ConvertTo-Yaml()` - 3 edges
10. `Get-LogDir()` - 3 edges

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

## Communities (25 total, 10 thin omitted)

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

### Community 20 - "Community 20"
Cohesion: 0.33
Nodes (6): Get-ModulePath(), Get-OnlineAddonsRoot(), Get-ProjectDir(), Get-ProjectVersion(), Get-WikiCache(), Load-ProjectVersionMap()

### Community 21 - "Community 21"
Cohesion: 0.50
Nodes (4): BackToConfirm(), Get-LogDir(), Release-Lock(), Resolve-CrashState()

### Community 22 - "Community 22"
Cohesion: 0.50
Nodes (4): Clear-StalePending(), Get-SystemDir(), Test-HasBlocker(), Test-PendingStale()

### Community 23 - "Community 23"
Cohesion: 0.67
Nodes (3): Atomic-WriteFile(), Open-ClaudeTerminal(), Write-PendingPrompt()

### Community 24 - "Community 24"
Cohesion: 1.00
Nodes (3): ConvertTo-Yaml(), Format-YamlScalar(), Write-YamlObject()

## Knowledge Gaps
- **14 isolated node(s):** `ResConfigSettings`, `ServiceAnnouncement`, `ServiceHoliday`, `ServiceQuestionCategory`, `ServiceTaxonomyLine` (+9 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Get-SystemDir()` connect `Community 22` to `Community 19`, `Community 21`, `Community 23`?**
  _High betweenness centrality (0.002) - this node is a cross-community bridge._
- **What connects `ResConfigSettings`, `ServiceAnnouncement`, `ServiceHoliday` to the rest of the system?**
  _15 weakly-connected nodes found - possible documentation gaps or missing edges._