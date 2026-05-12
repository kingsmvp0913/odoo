# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

- **Python**: `C:/odoo/venv_odoo17/Scripts/python.exe`
- **Odoo binary**: `C:/odoo/odoo-17.0/odoo-bin`
- **Config**: `C:/odoo/odoo-17.0/odoo.conf`
- **DB**: PostgreSQL at `localhost:5416`, user `odoo18`
- **Custom modules**: `custom_addons/` (only directory for project-specific code)

## Common Commands

```powershell
# Start Odoo (normal)
C:/odoo/venv_odoo17/Scripts/python.exe odoo-bin -c odoo.conf

# Start with dev mode (view hot-reload, asset unbundled)
C:/odoo/venv_odoo17/Scripts/python.exe odoo-bin -c odoo.conf --dev=xml,qweb,assets

# Upgrade specific module(s)
C:/odoo/venv_odoo17/Scripts/python.exe odoo-bin -c odoo.conf -u <module_name> -d <db_name> --stop-after-init

# Install new module
C:/odoo/venv_odoo17/Scripts/python.exe odoo-bin -c odoo.conf -i <module_name> -d <db_name> --stop-after-init

# Run tests for a module
C:/odoo/venv_odoo17/Scripts/python.exe odoo-bin -c odoo.conf --test-enable -u <module_name> -d <db_name> --stop-after-init

# Run single test class
C:/odoo/venv_odoo17/Scripts/python.exe odoo-bin -c odoo.conf --test-enable --test-tags=/<module_name>/<TestClassName> -d <db_name> --stop-after-init

# Auto-upgrade (dev tool — detects changed files and upgrades affected modules)
C:/odoo/venv_odoo17/Scripts/python.exe auto_upgrade.py
```

> `auto_upgrade.py` is a **development-only** tool. It scans `custom_addons/` for recently modified `.py`, schema `.xml`, and security `.csv` files, then automatically passes the affected module names to `-u`. Configure `DB_NAME` via the `ODOO_DB` environment variable.

## Architecture Overview

```
odoo-17.0/
├── odoo/               # Framework core
│   ├── models.py       # ORM base (BaseModel, AbstractModel, TransientModel)
│   ├── fields.py       # Field types
│   ├── api.py          # Decorators (@model, @depends, @constrains, etc.)
│   ├── http.py         # HTTP/controller layer
│   ├── addons/         # Built-in addons loaded with the framework
│   ├── modules/        # Module loading, registry, migration
│   └── tools/          # Utilities (config, misc, translate, etc.)
├── addons/             # Standard Odoo community addons
├── custom_addons/      # Project-specific custom modules (← work here)
└── odoo.conf           # Instance configuration
```

### Module Structure (`custom_addons/<module>/`)

```
<module>/
├── __manifest__.py     # name, version, depends, data, assets
├── __init__.py
├── models/             # Python model definitions (_inherit or new)
├── views/              # XML view definitions and menu items
├── controllers/        # HTTP routes (inherit from http.Controller)
├── security/
│   ├── ir.model.access.csv   # ACL (required for any new model)
│   └── <module>_security.xml # Record rules
├── data/               # Default/demo data XML
├── static/
│   └── src/            # JS, CSS, XML templates (OWL components)
└── wizard/             # TransientModel-based wizards
```

### ORM Key Patterns

- **Extend existing model**: `_inherit = 'res.partner'` (no `_name`)
- **New model**: `_name = 'my.model'`, `_description = '...'`
- **Computed field**: `@api.depends('field')` + `compute='_compute_x'`
- **Onchange**: `@api.onchange('field')`
- **Constraints**: `@api.constrains('field')`
- **Override**: always call `super()` unless intentionally blocking

### View Extension

```xml
<record id="view_id" model="ir.ui.view">
    <field name="inherit_id" ref="module.original_view_id"/>
    <field name="arch" type="xml">
        <xpath expr="//field[@name='target_field']" position="after">
            <field name="new_field"/>
        </xpath>
    </field>
</record>
```

### Controller Extension

```python
from odoo.addons.web.controllers.main import Home
class MyHome(Home):
    @http.route('/web', auth='user')
    def index(self, **kw):
        result = super().index(**kw)
        # modify result
        return result
```

## Linting

Odoo uses `flake8` with RST extension (see `setup.cfg`). Run from repo root:

```powershell
C:/odoo/venv_odoo17/Scripts/python.exe -m flake8 custom_addons/<module>
```

## Key Constraints

- Never modify files outside `custom_addons/`. Upstream Odoo files will be overwritten on update.
- Every new `_name` model requires an entry in `ir.model.access.csv`.
- `__manifest__.py` `depends` must list all modules whose models/views you inherit.
- `assets` in manifest are required for any custom JS/CSS to load.
