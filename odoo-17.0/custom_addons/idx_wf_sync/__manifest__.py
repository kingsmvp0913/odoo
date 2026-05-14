{
    "name": "idx同步Workflow",
    "summary": """同步Workflow功能""",
    "description": """同步Workflow功能""",
    "author": "IDX",
    "category": "Services/Project",
    "version": "1.0",
    "depends": ["base"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/wf_mapping_views.xml",
        "views/res_config_setting.xml",
        "views/res_company_views.xml",
    ],

    "installable": True,
    "application": True,
    "auto_install": False,
    "license": "LGPL-3",
}
