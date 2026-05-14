/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";

registry.category("views").add("loyalty_card_list_view", {
    ...listView,
    buttonTemplate: "idx_ebs.empty_loyalty_buttons",
}, { force: true });