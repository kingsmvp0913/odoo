# -*- coding: utf-8 -*-
from werkzeug.exceptions import Forbidden

from odoo import SUPERUSER_ID, fields, http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class IdxEbsWebsiteSale(WebsiteSale):
    def _check_user_login(self):
        """檢查使用者是否已登入且具有正確權限"""
        if request.env.user._is_public():
            # 判斷是否已登入（有 session uid）
            if request.session.uid:
                # 已登入但權限不足（仍是公開使用者）
                return request.render(
                    "idx_ebs.shop_access_denied",
                    {
                        "page_name": "商店",
                        "message": "您的帳號權限不足，無法訪問此頁面",
                    },
                    status=403,
                )
            # 未登入，重定向到登入頁
            return request.redirect("/web/login?redirect=" + request.httprequest.path)
        return None

    @http.route(
        [
            "/shop",
            "/shop/page/<int:page>",
            '/shop/category/<model("product.public.category"):category>',
            '/shop/category/<model("product.public.category"):category>/page/<int:page>',
        ],
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def shop(self, **post):
        # 檢查使用者是否已登入
        redirect = self._check_user_login()
        if redirect:
            return redirect
        # 如果已登入，調用原始的 shop 方法
        return super(IdxEbsWebsiteSale, self).shop(**post)

    @http.route(
        ['/shop/<model("product.template"):product>'],
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def product(self, product, category="", search="", **kwargs):
        """覆寫產品詳情頁，要求登入"""
        if request.env.user._is_public():
            # 返回 403 錯誤頁面（含 robots meta tag）
            return request.render(
                "idx_ebs.shop_access_denied",
                {
                    "page_name": "產品詳情",
                    "redirect_url": "/web/login?redirect=" + request.httprequest.path,
                    "is_shop_access_denied": True,
                },
                status=403,
            )
        return super(IdxEbsWebsiteSale, self).product(
            product, category=category, search=search, **kwargs
        )
    
    @http.route(
        ['/shop/product/<model("product.template"):product>'],
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def product_redirect(self, product, **kwargs):
        """覆寫產品詳情頁（/shop/product/ 路由），要求登入"""
        if request.env.user._is_public():
            # 返回 403 錯誤頁面（含 robots meta tag）
            return request.render(
                "idx_ebs.shop_access_denied",
                {
                    "page_name": "產品詳情",
                    "redirect_url": "/web/login?redirect=" + request.httprequest.path,
                    "is_shop_access_denied": True,
                },
                status=403,
            )
        # 如果已登入，重定向到標準產品頁面
        return request.redirect(f"/shop/{product.id}", code=301)

    @http.route(["/shop/cart"], type="http", auth="public", website=True, sitemap=False)
    def cart(self, **post):
        """覆寫購物車頁面，要求登入"""
        redirect = self._check_user_login()
        if redirect:
            return redirect
        return super(IdxEbsWebsiteSale, self).cart(**post)

    @http.route(
        ["/shop/checkout"], type="http", auth="public", website=True, sitemap=False
    )
    def checkout(self, **post):
        redirect = self._check_user_login()
        if redirect:
            return redirect

        order_sudo = request.website.sale_get_order()

        if order_sudo:
            report_groups = (
                request.env["sale.order.report"]
                .sudo()
                .read_group(
                    domain=[("order_id", "=", order_sudo.id)],
                    fields=["order_line_id"],
                    groupby=["order_line_id"],
                )
            )
            report_count_map = {
                g["order_line_id"][0]: g["order_line_id_count"]
                for g in report_groups
                if g["order_line_id"]
            }
            check_category = []
            for line in order_sudo.order_line:
                check_category.append(line.product_id.product_category_id.name if line.product_id.product_category_id else "N/A")
                if not line.product_id.category:
                    continue
                report_count = report_count_map.get(line.id, 0)
                if report_count != int(line.product_uom_qty):
                    # 使用 Odoo 原生的 shop_warning 欄位顯示錯誤訊息
                    order_sudo.shop_warning = "購物車中的「檢測服務」數量必須與「送檢報告」數量相同，請確認後再進行結帳！"
                    return request.redirect("/shop/cart")
            is_unified = all(x == check_category[0] for x in check_category) if check_category else False
            if not is_unified and "耗材" in check_category:
                order_sudo.shop_warning = "若​要​下單​耗材，​請先​確認​購物​車​中​的​產品​類別​皆為​「耗材」，​再​進行​結帳，​謝謝！"
                return request.redirect("/shop/cart")

        # 移除 express 參數，避免原生邏輯直接跳過地址選擇頁跑去 /shop/confirm_order
        post.pop("express", None)
        return super(IdxEbsWebsiteSale, self).checkout(**post)

    @http.route(
        ["/shop/confirm_order"], type="http", auth="public", website=True, sitemap=False
    )
    def confirm_order(self, **post):
        """覆寫確認訂單：直接送出訂單，跳過付款頁"""
        redirect = self._check_user_login()
        if redirect:
            return redirect

        order = request.website.sale_get_order()

        redirection = self.checkout_redirection(order) or self.checkout_check_address(order)
        if redirection:
            return redirection

        order.order_line._compute_tax_id()
        request.website.sale_get_order(update_pricelist=True)

        # 直接確認訂單，跳過付款頁
        if order.state != "sale":
            order.with_context(send_email=True).with_user(SUPERUSER_ID).action_confirm()

        # 先取得 portal URL（sale_reset 會清掉 session，需先保留）
        portal_url = order.get_portal_url()
        request.website.sale_reset()
        return request.redirect(portal_url)

    @http.route("/shop/payment", type="http", auth="public", website=True, sitemap=False)
    def shop_payment(self, **post):
        """封鎖付款頁，直接導回結帳頁（本站不走前台付款流程）"""
        redirect = self._check_user_login()
        if redirect:
            return redirect
        return request.redirect("/shop/checkout")

    @http.route(
        ["/shop/cart/update"],
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
        sitemap=False,
    )
    def cart_update(self, product_id, add_qty=1, set_qty=0, **kw):
        """覆寫加入購物車，要求登入"""
        redirect = self._check_user_login()
        if redirect:
            return redirect
        return super(IdxEbsWebsiteSale, self).cart_update(
            product_id, add_qty=add_qty, set_qty=set_qty, **kw
        )

    @http.route(
        ["/shop/cart/update_json"],
        type="json",
        auth="public",
        methods=["POST"],
        website=True,
        csrf=False,
    )
    def cart_update_json(
        self,
        product_id,
        line_id=None,
        add_qty=None,
        set_qty=None,
        display=True,
        product_custom_attribute_values=None,
        no_variant_attribute_values=None,
        **kw,
    ):
        """覆寫 AJAX 加入購物車，要求登入"""
        if request.env.user._is_public():
            return {
                "error": "login_required",
                "message": "您無權限修改購物車內容",
            }

        values = super(IdxEbsWebsiteSale, self).cart_update_json(
            product_id=product_id,
            line_id=line_id,
            add_qty=add_qty,
            set_qty=set_qty,
            display=display,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_values=no_variant_attribute_values,
            **kw,
        )

        # 判斷是否為刪除動作（set_qty=0 表示移除該明細）
        is_remove_action = line_id and set_qty is not None and float(set_qty) == 0

        if is_remove_action:
            # 刪除 sale_order_report 中 order_line_id=line_id 的所有資料
            sale_order_reports = (
                request.env["sale.order.report"]
                .sudo()
                .search([("order_line_id", "=", int(line_id))])
            )
            sale_order_reports.unlink() if sale_order_reports else None

        return values

    def _get_cart_notification_information(self, order, line_ids):
        """覆寫加入購物車通知的價格，改用價格表的 inc_tax_price（含稅單價）"""
        result = super()._get_cart_notification_information(order, line_ids)
        if not result or not result.get("lines"):
            return result

        # 無價格查看權限時，隱藏價格（設為 0）
        has_price_permission = (
            request.env.user.has_group('base.group_user') or
            request.env.user.has_group('idx_ebs.group_front_clinic_manager')
        )
        if not has_price_permission:
            for line_dict in result["lines"]:
                line_dict["line_price_total"] = 0
            return result

        lines = order.order_line.filtered(lambda l: l.id in line_ids)
        line_map = {l.id: l for l in lines}
        today = fields.Date.today()

        for line_dict in result["lines"]:
            line = line_map.get(line_dict["id"])
            if not line:
                continue
            pricelist_item = request.env["product.pricelist.item"].sudo().search(
                [
                    ("pricelist_id", "=", order.pricelist_id.id),
                    ("product_tmpl_id", "=", line.product_id.product_tmpl_id.id),
                    ("compute_price", "=", "fixed"),
                    "|", ("date_start", "=", False), ("date_start", "<=", today),
                    "|", ("date_end", "=", False), ("date_end", ">=", today),
                ],
                order="date_start desc",
                limit=1,
            )
            if pricelist_item and pricelist_item.inc_tax_price:
                line_dict["line_price_total"] = pricelist_item.inc_tax_price * line.product_uom_qty

        return result

