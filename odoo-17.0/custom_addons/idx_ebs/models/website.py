from odoo import models
from odoo.osv import expression


class Website(models.Model):
    _inherit = "website"

    def _search_get_details(self, search_type, order, options):
        """覆寫搜尋類型：當 search_type='all' 時，排除產品和產品分類"""
        result = super()._search_get_details(search_type, order, options)

        # 當 search_type 為 'all' 時，過濾掉產品相關的搜尋結果
        if search_type == "all":
            result = [
                detail
                for detail in result
                if detail.get("model")
                not in ["product.template", "product.public.category"]
            ]

        return result

    def sale_product_domain(self):
        """
        擴展原生的商品篩選邏輯：
        對於非內部使用者，只顯示在當前價格表中有設定價格的產品。
        """
        domain = super().sale_product_domain()

        # 如果是內部使用者，且是員工型態，則不做額外篩選
        if self.env.user._is_internal() and self.env.user.class_type == "E":
            return domain

        # 取得當前使用者的價格表
        pricelist = self.env["product.pricelist"].search(
            [("partner_id", "=", self.env.user.partner_id.id)], limit=1
        )
        # 使用者未設置價格表或價格表中沒有設定產品，則返回空結果
        if not pricelist:
            return expression.AND([domain, [("id", "=", False)]])

        # 取得價格表中有效的產品範本 ID（有設定價格且在有效期間內）
        pricelist_items = (
            self.env["product.pricelist.item"]
            .sudo()
            .search(
                [
                    ("pricelist_id", "=", pricelist.id),
                    ("product_tmpl_id", "!=", False),
                    "|",
                    ("date_start", "=", False),
                    ("date_start", "<=", self.env.cr.now()),
                    "|",
                    ("date_end", "=", False),
                    ("date_end", ">=", self.env.cr.now()),
                ]
            )
        )

        # 若同一產品有多筆設定，取生效日（date_start）最新的一筆
        from datetime import date as _date
        unique_tmpl: dict = {}
        for item in pricelist_items:
            tmpl_id = item.product_tmpl_id.id
            item_date = item.date_start or _date.min
            if tmpl_id not in unique_tmpl or item_date > unique_tmpl[tmpl_id]:
                unique_tmpl[tmpl_id] = item_date
        product_tmpl_ids = list(unique_tmpl.keys())
        pconsumables_ids = pricelist.consumables.ids
        all_product_ids = list(set(product_tmpl_ids + pconsumables_ids))
        # 如果價格表中沒有任何產品設定，則返回空結果
        if not product_tmpl_ids:
            return expression.AND([domain, [("id", "=", False)]])

        # 只顯示價格表中有設定的產品
        return expression.AND([domain, [("id", "in", all_product_ids)]])

    def _get_checkout_step_list(self):
        """覆寫結帳步驟清單：移除付款步驟，本站不走前台付款流程"""
        steps = super()._get_checkout_step_list()
        # 過濾掉含有 'website_sale.payment' 的步驟
        return [step for step in steps if "website_sale.payment" not in step[0]]
