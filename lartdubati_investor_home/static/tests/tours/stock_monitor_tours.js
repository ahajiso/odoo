/** @odoo-module **/
// Stock monitor on a real server (docs/phase3/PLAN.md §7): the dashboard and the
// detailed analysis, for an investor and an accountant.
import { registry } from "@web/core/registry";

const noError = { content: "no error dialog", trigger: "body:not(:has(.o_error_dialog))" };

function commonSteps() {
    return [
        { content: "figures loaded", trigger: ".o_smm_card_inventory_value .o_smm_card_big" },
        { content: "a row of the list", trigger: ".o_smm_row" },
        { content: "consumables only", trigger: ".o_smm_family_consumable", run: "click" },
        { content: "segment pressed", trigger: ".o_smm_family_consumable.active[aria-pressed='true']" },
        { content: "open a row", trigger: ".o_smm_row", run: "click" },
        { content: "detail open", trigger: ".o_smm_detail .o_smm_close" },
        { content: "close it", trigger: ".o_smm_close", run: "click" },
        { content: "detail closed", trigger: ".o_smm:not(:has(.o_smm_detail))" },
        noError,
    ];
}

registry.category("web_tour.tours").add("stock_monitor_investor_tour", {
    steps: () => [
        ...commonSteps(),
        {
            content: "no staff or accountant figure",
            trigger: ".o_smm:not(:has(.o_smm_card_stock_value)):not(:has(.o_smm_card_accounting_value)):not(:has(.o_smm_col_accounting))",
        },
        { content: "detailed analysis", trigger: ".o_smm_analysis", run: "click" },
        { content: "analysis list", trigger: ".o_list_view .o_group_header" },
        noError,
    ],
});

registry.category("web_tour.tours").add("stock_monitor_accountant_tour", {
    steps: () => [
        { content: "net book value card", trigger: ".o_smm_card_accounting_value .o_smm_card_big" },
        { content: "net book value column", trigger: "th.o_smm_col_accounting" },
        ...commonSteps(),
    ],
});
