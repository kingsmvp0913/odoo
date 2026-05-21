# Graph Report - C:/online_addons/19/odoo19_e_service  (2026-05-20)

## Corpus Check
- Corpus is ~2,007 words - fits in a single context window. You may not need a graph.

## Summary
- 61 nodes · 51 edges · 19 communities (9 shown, 10 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 6 edges (avg confidence: 0.83)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Service Question Logic|Service Question Logic]]
- [[_COMMUNITY_Taxonomy & Contract Check|Taxonomy & Contract Check]]
- [[_COMMUNITY_E-Service Core Models|E-Service Core Models]]
- [[_COMMUNITY_Teams Notification Config|Teams Notification Config]]
- [[_COMMUNITY_Exchange Rate Fetch (AST)|Exchange Rate Fetch (AST)]]
- [[_COMMUNITY_Teams Notify Service (AST)|Teams Notify Service (AST)]]
- [[_COMMUNITY_Exchange Rate API Methods|Exchange Rate API Methods]]
- [[_COMMUNITY_Holiday Import Wizard|Holiday Import Wizard]]
- [[_COMMUNITY_Holiday Wizard Logic (AST)|Holiday Wizard Logic (AST)]]
- [[_COMMUNITY_Holiday Model|Holiday Model]]
- [[_COMMUNITY_System Configuration|System Configuration]]
- [[_COMMUNITY_Announcement Model|Announcement Model]]
- [[_COMMUNITY_Question Category|Question Category]]
- [[_COMMUNITY_Module Entry Point|Module Entry Point]]
- [[_COMMUNITY_Teams Notify (Semantic)|Teams Notify (Semantic)]]

## God Nodes (most connected - your core abstractions)
1. `ServiceExchangeRate` - 4 edges
2. `ServiceQuestion` - 4 edges
3. `ServiceQuestion` - 3 edges
4. `ServiceTaxonomy` - 3 edges
5. `ServiceTeamsNotify` - 3 edges
6. `ServiceHolidayWizard` - 3 edges
7. `ServiceExchangeRate` - 3 edges
8. `ServiceTaxonomy` - 3 edges
9. `get_spot_exchange_rate_bank` - 3 edges
10. `compute_contract_notify` - 3 edges

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

## Communities (19 total, 10 thin omitted)

### Community 1 - "Taxonomy & Contract Check"
Cohesion: 0.33
Nodes (3): ServiceTaxonomy, ServiceTaxonomyLine, ServiceTaxonomyPoints

### Community 2 - "E-Service Core Models"
Cohesion: 0.40
Nodes (6): ServiceAnnouncement, ServiceQuestion, ServiceQuestionCategory, ServiceTaxonomy, ServiceTaxonomyLine, ServiceTaxonomyPoints

### Community 3 - "Teams Notification Config"
Cohesion: 0.40
Nodes (6): ResConfigSettings (e_service), _TeamsNotifyMessage, compute_contract_notify, Contract Expiry Notification Pattern, contract_notify_check, Teams Webhook Configuration Pattern

### Community 6 - "Exchange Rate API Methods"
Cohesion: 0.83
Nodes (4): ServiceExchangeRate, get_exchange_rate_customs, get_historical_exchange_rate_bank, get_spot_exchange_rate_bank

### Community 7 - "Holiday Import Wizard"
Cohesion: 0.50
Nodes (4): ServiceHoliday, ServiceHolidayWizard, ServiceHolidayWizard.generate, ServiceHolidayWizard.get_days_from_api

## Knowledge Gaps
- **14 isolated node(s):** `ResConfigSettings`, `ServiceAnnouncement`, `ServiceHoliday`, `ServiceQuestionCategory`, `ServiceTaxonomyLine` (+9 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What connects `ResConfigSettings`, `ServiceAnnouncement`, `ServiceHoliday` to the rest of the system?**
  _15 weakly-connected nodes found - possible documentation gaps or missing edges._