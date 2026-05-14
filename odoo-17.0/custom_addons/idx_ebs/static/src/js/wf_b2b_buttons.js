/** @odoo-module **/

import { KanbanController } from "@web/views/kanban/kanban_controller";
import { ListController } from "@web/views/list/list_controller";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { useService } from "@web/core/utils/hooks";
import { useState, onWillStart } from "@odoo/owl";

class ProductTemplateListController extends ListController {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.userService = useService("user");

        this.state = useState({
            canWfSync: false,
        });

        onWillStart(async () => {
            this.state.canWfSync =
                await this.userService.hasGroup("idx_ebs.group_back_it") ||
                await this.userService.hasGroup("idx_ebs.group_back_document_management");
        });
    }

    onWfSyncClick() {
        if (!this.state.canWfSync) {
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "WF同步至B2B",
            res_model: "idx.wf.sync.wizard",
            views: [[false, "form"]],
            target: "new",
            context: {},
        });
    }
}

class ProductTemplateKanbanController extends KanbanController {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.userService = useService("user");

        this.state = useState({
            canWfSync: false,
        });

        onWillStart(async () => {
            this.state.canWfSync =
                await this.userService.hasGroup("idx_ebs.group_back_it") ||
                await this.userService.hasGroup("idx_ebs.group_back_document_management");
        });
    }

    onWfSyncClick() {
        if (!this.state.canWfSync) {
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "WF同步至B2B",
            res_model: "idx.wf.sync.wizard",
            views: [[false, "form"]],
            target: "new",
            context: {},
        });
    }
}

class ProductPricelistListController extends ListController {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    onWfSyncPricelistClick() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "WF同步至B2B",
            res_model: "pricelist.wf.sync.wizard",
            views: [[false, "form"]],
            target: "new",
            context: {},
        });
    }
}

registry.category("views").add("idx_product_template_list_wf", {
    ...listView,
    Controller: ProductTemplateListController,
});

registry.category("views").add("idx_product_template_kanban_wf", {
    ...kanbanView,
    Controller: ProductTemplateKanbanController,
});

registry.category("views").add("idx_product_pricelist_list_wf", {
    ...listView,
    Controller: ProductPricelistListController,
});
