import io
import csv
import json
from datetime import date
from odoo import http
from odoo.http import request


class ExportInvoCsvController(http.Controller):

    @http.route('/export_invo_csv/download', type='http', auth='user', methods=['GET'])
    def download_csv(self, ids=None, domain=None, **kwargs):
        ids = ids or ''
        domain_str = domain or '[]'

        if ids:
            move_ids = [int(i) for i in ids.split(',') if i.isdigit()]
            moves = request.env['account.move'].browse(move_ids)
        else:
            try:
                domain = json.loads(domain_str)
            except (ValueError, TypeError):
                domain = []
            moves = request.env['account.move'].search(domain)

        csv_content = self._build_csv(moves)
        filename = 'invoice_export_{}.csv'.format(date.today().strftime('%Y%m%d'))

        return request.make_response(
            csv_content,
            headers=[
                ('Content-Type', 'text/csv; charset=utf-8'),
                ('Content-Disposition', 'attachment; filename="{}"'.format(filename)),
            ]
        )

    def _build_csv(self, moves):
        output = io.StringIO()
        writer = csv.writer(output)

        company = request.env.company
        address_parts = [p for p in [company.street, company.street2, company.city] if p]
        address = ' '.join(address_parts)

        writer.writerow([
            'H',
            company.vat or '',
            company.name or '',
            address,
            company.phone or '',
        ])

        for move in moves:
            tax_type, tax_rate = self._get_tax_info(move)
            invoice_date = ''
            if move.invoice_date:
                invoice_date = move.invoice_date.strftime('%Y/%m/%d') + ' 00:00:00'

            writer.writerow([
                'M',
                move.name or '',
                invoice_date,
                '07',
                move.partner_id.vat or '',
                move.partner_id.name or '',
                '',
                tax_type,
                tax_rate,
                int(round(move.amount_untaxed)),
                int(round(move.amount_tax)),
                int(round(move.amount_total)),
                '1',
                '1',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                move.currency_id.name or '',
            ])

            for line in move.invoice_line_ids:
                if line.display_type:
                    continue
                writer.writerow([
                    'D',
                    line.name or '',
                    '{:g}'.format(line.quantity),
                    '{:g}'.format(line.price_unit),
                    '{:g}'.format(line.price_total),
                    '',
                    line.product_uom_id.name or '',
                    '',
                ])

        return output.getvalue().encode('utf-8')

    def _get_tax_info(self, move):
        for line in move.invoice_line_ids:
            if line.display_type:
                continue
            for tax in line.tax_ids:
                amount = tax.amount
                name = (tax.name or '') + (tax.tax_group_id.name or '')
                if amount > 0:
                    return '1', str(int(amount))
                elif '零' in name:
                    return '2', '0'
                elif '免' in name:
                    return '3', '0'
                else:
                    return '1', str(int(amount))
        return '1', '5'
