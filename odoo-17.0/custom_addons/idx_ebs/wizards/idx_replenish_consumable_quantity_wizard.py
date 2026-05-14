import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class IDXReplenishConsumableQuantityWizard(models.TransientModel):
    _name = "idx.replenish.consumable.quantity.wizard"
    _description = "補充耗材數量"

    res_model = fields.Char('Related Document Model', required=True)
    res_id = fields.Integer('Related Document ID', required=True)
    product_id = fields.Many2one('product.product', string='產品', required=True)

    line_ids = fields.One2many('idx.replenish.consumable.line', 'wizard_id', string='補充明細')

    @api.model
    def default_get(self, fields_list):
        res = super(IDXReplenishConsumableQuantityWizard, self).default_get(fields_list)
        active_id = self._context.get('active_id')
        active_model = self._context.get('active_model')

        product = self.env[active_model].browse(active_id)
        if active_model == 'product.template':
            res['product_id'] = product.product_variant_id.id
        else:
            res['product_id'] = product.id

        res.update({
            'res_model': active_model,
            'res_id': active_id,
        })
        return res

    def action_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError("請至少新增一筆補充明細。")

        # 建立收貨單
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)

        if not picking_type:
            raise UserError("找不到合適的收貨作業類型，請檢查倉庫設定。")

        total_qty = sum(self.line_ids.mapped('qty'))
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id or self.env.ref('stock.stock_location_suppliers').id,
            'location_dest_id': picking_type.default_location_dest_id.id,
            'origin': f"批次補充: {self.product_id.name}",
        })

        # 建立庫存移動
        move = self.env['stock.move'].create({
            'name': self.product_id.name,
            'product_id': self.product_id.id,
            'product_uom_qty': total_qty,
            'product_uom': self.product_id.uom_id.id,
            'picking_id': picking.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
        })

        move._action_confirm()

        # 第一筆move_line更新數量，後續的move_line再建立
        for index, line in enumerate(self.line_ids):
            if line.qty <= 0:
                continue

            line_vals = {
                'lot_id': line.lot_id.id,
                'quantity': line.qty,
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
            }

            if index == 0 and move.move_line_ids:
                move.move_line_ids[0].write(line_vals)
            else:
                line_vals.update({
                    'move_id': move.id,
                    'picking_id': picking.id,
                    'product_id': self.product_id.id,
                    'product_uom_id': self.product_id.uom_id.id,
                })
                self.env['stock.move.line'].create(line_vals)

        picking.button_validate()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "耗材庫存補充完成",
                "message": f"產品【{self.product_id.name}】已成功更新 {len(self.line_ids)} 筆批號。",
                "type": "success",
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },

        }


class IDXReplenishConsumableLine(models.TransientModel):
    _name = "idx.replenish.consumable.line"
    _description = "補充明細行"

    wizard_id = fields.Many2one('idx.replenish.consumable.quantity.wizard')
    product_id = fields.Many2one(related='wizard_id.product_id')
    lot_id = fields.Many2one(
        'stock.lot', '批次',
        domain="[('product_id', '=', product_id)]", required=True
    )
    qty = fields.Float('數量', default=1.0, required=True)