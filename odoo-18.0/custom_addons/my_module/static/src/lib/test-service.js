import { registry } from "@web/core/registry";

registry.category("services").add("angryCounter", {
    start(env) {
        const today = () => new Date().toISOString().slice(0, 10);
        const state = {
            date: today(),
            count: 0,
        };

        return {
            state,
            increase() {
                //跨天數歸0
                if(this.state.date != today()){
                    this.state.date = today();
                    this.state.count = 0;
                }
                this.state.count++;
            },
            async getComment(orderId) {
                let orm = env.services.orm;
                let res = await orm.read("sale.order", [orderId], ["name", "state", "opportunity_id"]);
                let comment = 'none';

                if(res[0]?.state == 'sale'){
                    comment = 'good';
                }else if(res[0]?.state != 'sale'){
                    //取得id後再抓crm資料
                    let opportunity_id = res[0]?.opportunity_id[0] || 0;
                    if(opportunity_id){
                        let res2 = await orm.read("crm.lead", [opportunity_id], ["probability"]);
                        if(res2[0]?.id && res2[0]?.probability >= 50){
                            comment = 'better';
                        }
                    }
                }
                console.log(comment);
                return comment;
            }
        };
    },
});