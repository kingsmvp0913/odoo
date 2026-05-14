/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { useService } from "@web/core/utils/hooks";

class IDXOcrPageListController extends ListController {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    MergeOrders1() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "合併成訂單",
            res_model: "idx.merge.order.wizard",
            views: [[false, "form"]],
            target: "new",
            context: {default_merge_type : '1'},
        });
    }

    MergeOrders2() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "合併成訂單",
            res_model: "idx.merge.order.wizard",
            views: [[false, "form"]],
            target: "new",
            context: {default_merge_type : '2'},
        });
    }
}

registry.category("views").add("idx_view_sale_order_ocr1_tree", {
    ...listView,
    Controller: IDXOcrPageListController,
});

registry.category("views").add("idx_view_sale_order_ocr2_tree", {
    ...listView,
    Controller: IDXOcrPageListController,
});

