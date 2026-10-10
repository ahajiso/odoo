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
        // Q6, audit of the deployed phase 4: the export from the list (Actions → Export),
        // XLSX then CSV, with the export group the investor group implies; each download
        // the browser triggers is counted on <body> (the download utility makes an object
        // URL); the files' content is checked by the HTTP tests (test_export_routes)
        {
            content: "count the downloads",
            trigger: "body",
            run: () => {
                const createObjectURL = URL.createObjectURL;
                document.body.dataset.smmDownloads = "0";
                URL.createObjectURL = (blob) => {
                    document.body.dataset.smmDownloads = String(Number(document.body.dataset.smmDownloads) + 1);
                    return createObjectURL.call(URL, blob);
                };
            },
        },
        // the analysis opens grouped by currency then stock, as one removable facet
        {
            content: "grouping facet « Currency > Stock », in this order",
            trigger: ".o_searchview_facet:has(.oi-group) .o_facet_remove",
            run: () => {
                const values = [...document.querySelectorAll(".o_searchview_facet:has(.oi-group) .o_facet_value")]
                    .map((el) => el.textContent.trim());
                if (values.join(" > ") !== "Currency > Stock") {
                    throw new Error(`grouping facet: ${values.join(" > ")}`);
                }
            },
        },
        // open the currency group, then its first stock group
        { content: "open the currency group", trigger: ".o_list_view .o_group_header:not(.o_group_open)", run: "click" },
        { content: "stock groups shown", trigger: ".o_list_view .o_group_header.o_group_open ~ .o_group_header" },
        { content: "open a stock group", trigger: ".o_list_view .o_group_header:not(.o_group_open)", run: "click" },
        { content: "rows shown", trigger: ".o_list_view .o_data_row" },
        {
            content: "first level: a currency; second level: a stock",
            trigger: ".o_list_view .o_data_row",
            run: () => {
                const headers = [...document.querySelectorAll(".o_list_view .o_group_header")]
                    .map((el) => el.textContent.trim());
                if (!/^EUR/.test(headers[0]) || !/^LADB \//.test(headers[1])) {
                    throw new Error(`group headers: ${headers.join(" | ")}`);
                }
            },
        },
        { content: "select a row", trigger: ".o_data_row .o_list_record_selector input", run: "click" },
        { content: "actions menu", trigger: ".o_cp_action_menus .dropdown-toggle", run: "click" },
        { content: "export", trigger: ".o-dropdown--menu .dropdown-item:contains('Export')", run: "click" },
        { content: "export dialog with fields", trigger: ".o_export_data_dialog .o_export_field" },
        { content: "XLSX", trigger: ".o_export_data_dialog input[name='o_export_format_name'][value='xlsx']", run: "click" },
        { content: "export XLSX", trigger: ".o_export_data_dialog .o_select_button", run: "click" },
        { content: "XLSX download triggered", trigger: "body[data-smm-downloads='1']" },
        noError,
        // Odoo refuses a CSV export of grouped data (for every user): ungroup first
        { content: "close the dialog before CSV", trigger: ".o_export_data_dialog .o_form_button_cancel", run: "click" },
        { content: "unselect (the search bar comes back)", trigger: ".o_list_unselect_all", run: "click" },
        { content: "remove the grouping", trigger: ".o_searchview_facet:has(.oi-group) .o_facet_remove", run: "click" },
        { content: "flat list", trigger: ".o_list_view:not(:has(.o_group_header)) .o_data_row" },
        { content: "select a row again", trigger: ".o_data_row .o_list_record_selector input", run: "click" },
        { content: "actions menu again", trigger: ".o_cp_action_menus .dropdown-toggle", run: "click" },
        { content: "export again", trigger: ".o-dropdown--menu .dropdown-item:contains('Export')", run: "click" },
        { content: "export dialog again", trigger: ".o_export_data_dialog .o_export_field" },
        { content: "CSV", trigger: ".o_export_data_dialog input[name='o_export_format_name'][value='csv']", run: "click" },
        { content: "export CSV", trigger: ".o_export_data_dialog .o_select_button", run: "click" },
        { content: "CSV download triggered", trigger: "body[data-smm-downloads='2']" },
        noError,
        { content: "close the dialog", trigger: ".o_export_data_dialog .o_form_button_cancel", run: "click" },
        { content: "dialog closed", trigger: "body:not(:has(.o_export_data_dialog))" },
    ],
});

registry.category("web_tour.tours").add("stock_monitor_accountant_tour", {
    steps: () => [
        { content: "net book value card", trigger: ".o_smm_card_accounting_value .o_smm_card_big" },
        { content: "net book value column", trigger: "th.o_smm_col_accounting" },
        ...commonSteps(),
    ],
});

// Performance (P13, C5): the time from the action to the cards and the list rendered is
// logged by the tour itself (performance.now at the first and last step).
registry.category("web_tour.tours").add("stock_monitor_perf_tour", {
    steps: () => [
        { content: "start", trigger: "body", run: () => (window.__smmStart = performance.now()) },
        { content: "cards and list rendered", trigger: ".o_smm_card_inventory_value .o_smm_card_big" },
        {
            content: "list rendered",
            trigger: ".o_smm_row",
            run: () => console.log(`monitor_perf browser render: ${Math.round(performance.now() - window.__smmStart)} ms`),
        },
    ],
});

// Investor home page (phase 4, docs/phase4/PLAN.md §3): the home action, the Financial
// button to the dashboard, a « coming soon » button, no error under the investor rights.
registry.category("web_tour.tours").add("investor_home_tour", {
    steps: () => [
        { content: "home buttons", trigger: ".o_kanban_record:contains('Financial')" },
        { content: "four buttons", trigger: ".o_kanban_view:has(.o_kanban_record:contains('Production'))" },
        {
            content: "open Financial",
            trigger: ".o_kanban_record:contains('Financial') a[name='run_action']",
            run: "click",
        },
        { content: "dashboard figures", trigger: ".o_smm_card_inventory_value .o_smm_card_big" },
        noError,
        { content: "back home", trigger: ".o_smm_back:contains('Investor Home')", run: "click" },
        {
            content: "open Production",
            trigger: ".o_kanban_record:contains('Production') a[name='run_action']",
            run: "click",
        },
        { content: "coming soon", trigger: ".o_notification:contains('Coming soon')" },
        noError,
        // audit of bdb8428 (badge « 2 » seen locally): the messaging badge adds the inbox,
        // the failures, the « install the app » prompt and the « allow notifications »
        // prompt (mail MessagingMenu.counter); the test made another user's messages,
        // failures, activity and unread chat: none may count here
        {
            content: "messaging badge: only the browser's own prompts",
            trigger: ".o_menu_systray .fa-comments",
            run: () => {
                const services = odoo.__WOWL_DEBUG__.root.env.services;
                const store = services["mail.store"];
                const parts = {
                    inbox: store.inbox.counter,
                    starred: store.starred.counter,
                    failures: store.failures.length,
                    unreadChannels: store.initChannelsUnreadCounter || 0,
                    install: services.pwa.canPromptToInstall ? 1 : 0,
                    allowNotifications:
                        services["mail.notification.permission"].permission === "prompt" &&
                        !store.isNotificationPermissionDismissed ? 1 : 0,
                };
                const badge = document.querySelector(".o-mail-MessagingMenu-counter");
                const shown = badge ? Number(badge.textContent.trim()) : 0;
                console.log(`investor messaging badge: ${shown} ${JSON.stringify(parts)}`);
                if (parts.inbox || parts.starred || parts.failures || parts.unreadChannels) {
                    throw new Error(`messages counted for the investor: ${JSON.stringify(parts)}`);
                }
                if (shown !== parts.install + parts.allowNotifications) {
                    throw new Error(`badge ${shown} is not the browser prompts: ${JSON.stringify(parts)}`);
                }
            },
        },
        { content: "open the messaging menu", trigger: ".o_menu_systray .fa-comments", run: "click" },
        {
            content: "no conversation, no failure in the menu",
            trigger: ".o-mail-MessagingMenu",
            run: () => {
                const text = document.querySelector(".o-mail-MessagingMenu").textContent;
                for (const hidden of ["Hidden", "mon_store", "Failure"]) {
                    if (text.includes(hidden)) {
                        throw new Error(`messaging menu shows « ${hidden} »: ${text}`);
                    }
                }
                console.log(`investor messaging menu: ${text.replace(/\s+/g, " ").trim()}`);
            },
        },
        { content: "close the messaging menu", trigger: ".o_menu_systray .fa-comments", run: "click" },
        // own preferences (language, time zone): action_get, web_read, web_save
        { content: "user menu", trigger: ".o_user_menu button", run: "click" },
        { content: "preferences", trigger: ".dropdown-item[data-menu='settings']", run: "click" },
        { content: "preferences form", trigger: ".modal .o_form_view .o_field_widget[name='tz']" },
        { content: "save", trigger: ".modal .modal-footer button.btn-primary", run: "click" },
        { content: "saved", trigger: "body:not(:has(.modal .o_form_view))" },
        noError,
    ],
});
