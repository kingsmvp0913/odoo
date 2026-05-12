import { Child } from "../child/child";
import { Component, useState, useSubEnv } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";


export class Example extends Component {
    static template = "my_module.Example";
    static components = {Child};

    setup(){
        useSubEnv({data:"info" });
        this.orm = useService("orm");
        this.counter = useService("counterService");
        this.message= "Hello!";
    }

    increaseCounter(event){
        this.counter.increase();
        this.orm.call("crm.lead", "create", {"name" : "new"});
    }

    alertMessage(event){
        alert(this.message);
    }
}

registry.category("view_widgets").add("example", {component:Example});