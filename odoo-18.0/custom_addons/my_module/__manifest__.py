{
    "name" : "My Module",
    "version" : "18.0.1.0.0",
    "author" : "Odoo",
    "category" : "Category",
    "license" : "LGPL-3",
    "description" : "Description text",
    "depends" : [
        "sale",
        "sale_management",
        "crm",
        "web",
        
    ],
    "data" : [
        'views/sale_order_views.xml',
    ],
    "assets" : {
        "web.assets_backend":[
            "my_module/static/src/components/**/*",
            "my_module/static/src/lib/*", 
        ]
    }
}