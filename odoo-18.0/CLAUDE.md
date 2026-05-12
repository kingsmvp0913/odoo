# CLAUDE.md (Odoo Domain - Minimalist)

## 1. Context & Versioning
- **Path-Based Detection**: Auto-detect version via parent directory (e.g., `odoo-13.0`).
  - **V13-14**: Use `api.multi`, `odoo.define`, `web.Widget`.
  - **V15-18**: Use OWL Components, ESM, Modern API.
- **Inheritance**: Always search `_inherit` to map overrides before modification.
- **Path Priority**: Target `custom_addons/` only. Do not modify `odoo/` core.

## 2. ORM & XML Rules
- **Security**: Prefer `with_user()`/`with_company()`. Avoid `sudo()`.
- **Performance**: NO SQL, `env.ref()`, or `search()` inside loops. Use `@api.model_create_multi` for batch creates.
- **XML**: Use precise `xpath`. 
- **Location-First XML**: No full records. Provide: `@Path` > `Record ID` > `XPath` > `Change Description`.

## 3. Commands
- **Start**: `python odoo-bin -c odoo.conf`
- **Update**: `-d <db> -u <module>`
- **Test**: `-d <db> --test-enable --test-tags <tag>`
- **Shell**: `python odoo-bin shell -c odoo.conf -d <db>`

## 4. Terminology (Taiwan)
- **Keep English**: Model, Recordset, Many2one, Compute, Field, View, Hook, Environment.
- **Taiwan Terms**: 「欄位」, 「視圖」, 「繼承」, 「函式」, 「資料庫」, 「專案」.
