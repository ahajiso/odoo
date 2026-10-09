/** @odoo-module **/
// Phase 2f: interface checks of the approver alone and of the operator alone on a
// complete purchase receipt (docs/phase2f/PLAN.md §4). Any access error raised while
// opening the form or a line fails the tour.
import { registry } from "@web/core/registry";

const LINE = ".o_field_one2many[name='line_ids'] .o_data_row:first-child .o_data_cell:first-child";

function openLineAndCheckTreatment() {
    return [
        { content: "the operation form is loaded", trigger: ".o_form_view .o_field_widget[name='line_ids']" },
        { content: "open the line sheet", trigger: LINE, run: "click" },
        {
            content: "the planned accounting treatment is shown",
            trigger: ".modal .o_field_widget[name='accounting_treatment']:contains('Planned treatment')",
        },
        { content: "responsible shown", trigger: ".modal .o_field_widget[name='responsible_user_id']" },
        { content: "close the line sheet", trigger: ".modal .modal-footer button", run: "click" },
        { content: "line sheet closed", trigger: "body:not(:has(.modal))" },
    ];
}

registry.category("web_tour.tours").add("equipment_operation_approver_tour", {
    steps: () => [
        ...openLineAndCheckTreatment(),
        { content: "no execute button for the approver", trigger: ".o_form_view:not(:has(button[name='action_execute']))" },
        { content: "approve", trigger: ".o_statusbar_buttons button[name='action_approve']", run: "click" },
        { content: "approved", trigger: ".o_statusbar_status .o_arrow_button_current:contains('Approved')" },
    ],
});

registry.category("web_tour.tours").add("equipment_operation_operator_tour", {
    steps: () => [
        ...openLineAndCheckTreatment(),
        { content: "no approve button for the operator", trigger: ".o_form_view:not(:has(button[name='action_approve']))" },
        { content: "still waiting for the approver", trigger: ".o_statusbar_status .o_arrow_button_current:contains('To Approve')" },
    ],
});
