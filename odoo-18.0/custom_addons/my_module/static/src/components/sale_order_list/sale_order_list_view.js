/** @odoo-module **/
import { SaleListView } from "@sale/views/sale_onboarding_list/sale_onboarding_list_view";
import { SaleListRenderer } from "@sale/views/sale_onboarding_list/sale_onboarding_list_renderer";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";

const formatters = registry.category("formatters");

patch(SaleListRenderer.prototype, {
    // Always compute footer aggregate from ALL records, not just the selected subset.
    // Odoo's default switches to selected-only when selection exists, hiding the full total.
    // Selected total is shown separately in an extra row below (see template).
    get aggregates() {
        let values;
        if (this.props.list.isGrouped) {
            values = this.props.list.groups.map((g) => g.aggregates);
        } else {
            values = this.props.list.records.map((r) => r.data);
        }
        const aggregates = {};
        for (const column of this.allColumns) {
            if (column.type !== "field") continue;
            const fieldName = column.name;
            if (fieldName in this.optionalActiveFields && !this.optionalActiveFields[fieldName]) continue;
            const field = this.fields[fieldName];
            const fieldValues = values.map((v) => v[fieldName]).filter((v) => v || v === 0);
            if (!fieldValues.length) continue;
            const type = field.type;
            if (type !== "integer" && type !== "float" && type !== "monetary") continue;
            const { attrs, widget } = column;
            const func =
                (attrs.sum && "sum") ||
                (attrs.avg && "avg") ||
                (attrs.max && "max") ||
                (attrs.min && "min");
            let currencyId;
            if (type === "monetary" || widget === "monetary") {
                const currencyField =
                    column.options.currency_field ||
                    this.fields[fieldName].currency_field ||
                    "currency_id";
                if (!(currencyField in this.props.list.activeFields)) {
                    aggregates[fieldName] = { help: _t("No currency provided"), value: "—" };
                    continue;
                }
                currencyId = values[0][currencyField] && values[0][currencyField][0];
                if (currencyId && func) {
                    const sameCurrency = values.every((v) => currencyId === v[currencyField][0]);
                    if (!sameCurrency) {
                        aggregates[fieldName] = {
                            help: _t("Different currencies cannot be aggregated"),
                            value: "—",
                        };
                        continue;
                    }
                }
            }
            if (func) {
                let aggregateValue = 0;
                if (func === "max") aggregateValue = Math.max(-Infinity, ...fieldValues);
                else if (func === "min") aggregateValue = Math.min(Infinity, ...fieldValues);
                else if (func === "avg") aggregateValue = fieldValues.reduce((a, v) => a + v) / fieldValues.length;
                else if (func === "sum") aggregateValue = fieldValues.reduce((a, v) => a + v);
                const formatter = formatters.get(widget, false) || formatters.get(type, false);
                const formatOptions = {
                    digits: attrs.digits ? JSON.parse(attrs.digits) : undefined,
                    escape: true,
                };
                if (currencyId) formatOptions.currencyId = currencyId;
                aggregates[fieldName] = {
                    help: attrs[func],
                    value: formatter ? formatter(aggregateValue, formatOptions) : aggregateValue,
                };
            }
        }
        return aggregates;
    },

    get selectedAmountInfo() {
        const sel = this.props.list.selection;
        if (!sel.length) return null;
        const currencyId = sel[0]?.data?.currency_id?.[0];
        if (currencyId && sel.some((r) => r.data.currency_id?.[0] !== currencyId)) {
            return { count: sel.length, formatted: "—" };
        }
        const total = sel.reduce((sum, r) => sum + (r.data.amount_total || 0), 0);
        return { count: sel.length, formatted: formatMonetary(total, { currencyId, escape: true }) };
    },
});

registry.category("views").add("sale_order_list", {
    ...SaleListView,
    Renderer: SaleListRenderer,
});
