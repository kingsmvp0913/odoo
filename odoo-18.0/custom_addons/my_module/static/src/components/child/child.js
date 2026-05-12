import { Component, onWillStart } from "@odoo/owl";

export class Child extends Component {
    static template = "my_module.Child";
    static props = {
        title : { type: String},
        list : { type: Array},
        slots : { type: Object},
        onDBLClick: {type: Function},
        counter:{ type: Object},
    }

    setup(){
        this.message= "Hello Sub!";

        onWillStart(() => console.log("Child onWillStart"));
    }

    get counterValue() {
        return this.props.counter.state.counter;
    }
}
