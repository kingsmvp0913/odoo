from odoo import http
from odoo.http import request

# 此 controller 已停用
# 改為在模型層的 _create_answer 方法中處理 partner_id 自動設定
# 避免覆寫原生 controller 導致功能缺失
