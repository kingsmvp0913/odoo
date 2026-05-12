import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { reactive } from "@odoo/owl";

registry.category("services").add("counterService", {
    start() {
        return {
            state: {
                counter: 0,
            },

            increase() {
                this.state.counter++;
                console.log(this.state.counter)
            },
        };
    },
});



