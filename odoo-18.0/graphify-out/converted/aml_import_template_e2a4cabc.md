<!-- converted from aml_import_template.xlsx -->

## Sheet: Journal Items
| journal_id | move_id | date | partner_id | name | account_id | debit | credit | matching_number |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MISC | MISC/2021/00002 | 2021-12-06 00:00:00 | Deco Addict | [FURN_8220] Four Person Desk | 700200 |  | 11750 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| MISC | MISC/2021/00002 | 2021-12-06 00:00:00 | Deco Addict | Three Seater Sofa with Lounger in Steel Grey Colour | 700200 |  | 30000.89 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| MISC | MISC/2021/00002 | 2021-12-06 00:00:00 | Deco Addict | +++000/0000/05454+++ | 400000 | 41750.89 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| SAL | SAL/2021/00001 | 2021-12-01 00:00:00 |  | Salary November 2021 | 455000 |  | 11750 | R1 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| SAL | SAL/2021/00001 | 2021-12-01 00:00:00 |  | Salary November 2021 | 620200 | 11750 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| BNK | BNK/2021/00001 | 2021-12-15 00:00:00 |  | Payment Salary November 2021 | 455000 | 11750 |  | R1 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| BNK | BNK/2021/00001 | 2021-12-15 00:00:00 |  | Payment Salary November 2021 | 550003 |  | 11750 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Instructions
| (Optional) Import Journal Items |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| * is mandatory |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Column name | Comments / Notes |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| IMPORTANT | Journal Entries consist of at least 2 lines with balanced debits and credit. |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| journal_id* | The code of the associated journal in Odoo. Standard Odoo journals are provided as a guide.
BILL - Vendor Bills*
BNK1 - Bank
CSH1 - Cash
EXCH - Exchange difference
EXP - Expense
INV - Customer Invoices*
MISC - Miscellaneous
POSS - Point of Sale
SAL - Salaries
STJ - Inventory Valuation
* Importing entries in those journals will not create Invoices in Odoo. We suggest to import Invoices regularly. |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| move_id* | The name of the entry. This should bear the appropriate sequence number for your Journal. This will be used by Odoo to group all the lines together in an entry. |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| date* |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| partner_id | You can directly reference a Contact name. If no Partner is found in the database with that name, Odoo will create a new one. |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| name | The label of your line (product reference, payment reference, etc); |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| account_id* | Reference an existing account using its code. If no account is found in the database, a new one will be created and configured automatically. 
You can specify a name next to the code and it will update or create the name if needed (e.g.: 100100 Current Assets) |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| debit |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| credit |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |