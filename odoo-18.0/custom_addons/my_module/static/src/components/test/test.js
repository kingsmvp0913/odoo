import { Component, useState, useEffect, useRef, useAutoFocus, onWillStart  } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";


export class Test extends Component {
    static template = "my_module.Test";

    setup(){
        this.message= "Get back to work!";
        this.state = useState({counter:0, face:"☺️"});
        this.angryCounter = useService("angryCounter");
        this.orderId = this.props.record.resId || 0;
        this.comment = 'none';

        useEffect(() => {
            const timer = setInterval(() => {
                this.state.counter++;
                if(this.state.counter >= 60){
                    if(this.state.face != "😠"){
                        this.angryCounter.increase();
                    }
                    this.state.face = "😠";
                }
            }, 1000);

            return () => clearInterval(timer);
        });
        
        onWillStart(async () => {
            if(this.orderId){
                this.comment = await this.angryCounter.getComment(this.orderId);
            }
        });
    }

    alertMessage(event){
        const tab = document.querySelector(".js_calculator_tab");
        tab?.click();

        setTimeout(() => {
            const input = document.querySelector(".js_calculator_input");
            input?.focus();
        }, 0);
    }

    
}

export class TestCalculator extends Component {
    static template = "my_module.TestCalculator";

    setup(){
        this.state = useState({counter1:0, counter2:0});
    }

    updateCounter1(event){
        this.state.counter1 = Number(event.target.value);
    }
    
    updateCounter2(event){
        this.state.counter2 = Number(event.target.value);
    }

    get sum(){
        return (this.state.counter1 || 0) + (this.state.counter2 || 0);
    }
}

export class TestRef extends Component {
    static template = "my_module.TestRef";

    setup(){
        this.input = useRef("input1");
    }

    focusInput(event){
        this.input.el.focus();
    }
}

export class TestAountTotal extends  Component {
    static amountTotal = 0;
    

    clickToSum(event){
        
    }
}

registry.category("view_widgets").add("test", {component:Test});
registry.category("view_widgets").add("testCalculator", {component:TestCalculator});
registry.category("view_widgets").add("testRef", {component:TestRef});
registry.category("view_widgets").add("testAmountTotal", {component:TestAountTotal});