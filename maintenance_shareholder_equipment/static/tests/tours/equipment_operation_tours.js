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

// After execution: the approver alone really opens each document the operation refers
// to (audit of bad8e9f). An access error on the document or on its lines (bill lines,
// move lines) shows an error dialog and fails the tour.
const noError = { content: "no error dialog", trigger: "body:not(:has(.o_error_dialog))" };

registry.category("web_tour.tours").add("equipment_document_with_lines_tour", {
    steps: () => [
        { content: "form loaded", trigger: ".o_form_view .o_form_sheet" },
        { content: "its lines are loaded", trigger: ".o_form_view .o_data_row" },
        noError,
    ],
});

registry.category("web_tour.tours").add("equipment_document_tour", {
    steps: () => [
        { content: "form loaded", trigger: ".o_form_view .o_form_sheet" },
        noError,
    ],
});

registry.category("web_tour.tours").add("equipment_receipt_details_tour", {
    steps: () => [
        { content: "receipt loaded", trigger: ".o_form_view .o_field_widget[name='move_ids_without_package'] .o_data_row" },
        {
            content: "open the move's detailed operations",
            trigger: ".o_field_widget[name='move_ids_without_package'] .o_data_row .fa-list",
            run: "click",
        },
        { content: "the serial number of the move line is shown", trigger: ".modal .o_data_row:contains('TOUR-')" },
        noError,
    ],
});
