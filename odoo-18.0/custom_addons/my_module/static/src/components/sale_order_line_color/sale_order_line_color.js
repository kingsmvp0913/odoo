/** @odoo-module **/

import { registry } from "@web/core/registry";
import {
    SaleOrderLineListRenderer,
    SaleOrderLineOne2Many,
    saleOrderLineOne2Many,
} from "@sale/js/sale_order_line_field/sale_order_line_field";

export class SaleOrderLineColorRenderer extends SaleOrderLineListRenderer {
    getRowClass(record) {
        const classNames = super.getRowClass(record);
        const type = record.data.product_type;
        if (type === "service") return `${classNames} o_sol_bg_service`;
        if (type === "consu") return `${classNames} o_sol_bg_consu`;
        if (type === "combo") return `${classNames} o_sol_bg_combo`;
        return classNames;
    }
}

export class SaleOrderLineColorOne2Many extends SaleOrderLineOne2Many {
    static components = {
        ...SaleOrderLineOne2Many.components,
        ListRenderer: SaleOrderLineColorRenderer,
    };
}

registry.category("fields").add("sol_o2m_color", {
    ...saleOrderLineOne2Many,
    component: SaleOrderLineColorOne2Many,
});
