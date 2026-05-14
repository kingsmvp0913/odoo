from odoo import models, fields


class CrmLead(models.Model):
    _inherit = "crm.lead"

    loyalty_card_id = fields.Many2one(
        "loyalty.card",
        string="優惠券",
        ondelete="restrict",
    )
    
    stock_lot_id = fields.Many2one(
        "stock.lot",
        string="相關批次",
        ondelete="restrict",
        help="關聯即將過期的庫存批次"
    )
    

    def action_open_card(self):
        self.ensure_one()
        return {
            "name": "優惠代碼",
            "type": "ir.actions.act_window",
            "res_model": "loyalty.card",
            "view_mode": "form",
            "res_id": self.loyalty_card_id.id,
            "target": "current",
        }
    
    def action_open_product(self):
        self.ensure_one()
        return {
            "name": "產品",
            "type": "ir.actions.act_window",
            "res_model": "product.product",
            "view_mode": "form",
            "res_id": self.stock_lot_id.product_id.id,
            "target": "current",
        }

    def action_view_sale_orders(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_orders")

        order_lines = self.env['sale.order.line'].search([('lot_id', '=', self.stock_lot_id.id)])

        order_ids = order_lines.mapped('order_id').ids

        if not order_ids:
            action['domain'] = [('id', 'in', [])]
            return action

        if len(order_ids) == 1:
            action['views'] = [(self.env.ref('sale.view_order_form').id, 'form')]
            action['res_id'] = order_ids[0]
        else:
            action['domain'] = [('id', 'in', order_ids)]
            tree_view = self.env.ref('sale.view_quotation_tree').id
            form_view = self.env.ref('sale.view_order_form').id
            action['views'] = [(tree_view, 'tree'), (form_view, 'form')]

        return action