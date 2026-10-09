// Stock monitor dashboard (docs/phase3/PLAN.md §4.3, §4.5): RPCs, fields from
// fields_get only, keyboard and focus, pressed states, RPC error.
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { press, queryAll, queryFirst } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import {
    contains,
    defineModels,
    fields,
    getService,
    models,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { WebClient } from "@web/webclient/webclient";

describe.current.tags("desktop");

const MODEL = "lartdubati.stock.monitor";

class StockMonitor extends models.Model {
    _name = MODEL;
    family = fields.Selection({ selection: [["asset", "Asset"], ["consumable", "Consumable"]] });
    ownership_status = fields.Selection({
        string: "Ownership Status",
        selection: [["owned", "Owned"], ["borrowed", "Borrowed"], ["rented", "Rented"], ["lent_out", "Lent Out"]],
    });
    product_name = fields.Char({ string: "Product" });
    equipment_name = fields.Char();
    serial = fields.Char();
    category_name = fields.Char();
    stock_name = fields.Char();
    location_name = fields.Char();
    city = fields.Char();
    country_name = fields.Char();
    quantity = fields.Float();
    uom_name = fields.Char();
    currency_id = fields.Integer();
    inventory_value = fields.Float({ string: "Inventory Value (excl. tax)" });
    inventory_value_known = fields.Integer();
    inventory_value_rate_missing = fields.Integer({ string: "Inventory Value – Rate Missing" });
    inventory_value_source_amount = fields.Float();
    inventory_value_source_currency_id = fields.Integer();
    accounting_value = fields.Float({ string: "Net Book Value" });
    accounting_value_known = fields.Integer();
    accounting_value_rate_missing = fields.Integer();
    accounting_value_source_amount = fields.Float();
    accounting_value_source_currency_id = fields.Integer();
    accounting_provisional = fields.Integer();

    _records = [
        { id: 2, family: "asset", ownership_status: "owned", product_name: "Drill", serial: "S1", stock_name: "Bg/Stock", quantity: 1, currency_id: 1, inventory_value: 100, inventory_value_known: 1, inventory_value_source_currency_id: 1, accounting_value: 80, accounting_value_known: 1 },
        { id: 3, family: "consumable", ownership_status: "owned", product_name: "Screws", stock_name: "Bg/Stock", quantity: 10, currency_id: 1, inventory_value: 20, inventory_value_known: 1, inventory_value_source_currency_id: 1, accounting_value: 0, accounting_value_known: 1 },
    ];
}
defineModels([StockMonitor]);
defineMailModels(); // the web client of a database with mail needs its models

function dashboardData(totals) {
    return {
        domain: [],
        count: 2,
        assets: 1,
        totals,
        stocks: [{ name: "Bg/Stock", city: "Bougival", country: "France", place_type: "physical", currency_id: 1, count: 2, assets: 1, inventory_value: 120, missing: 0, alerts: 0 }],
        alerts: {},
        segments: [
            { family: "asset", ownership: "owned", count: 1 },
            { family: "consumable", ownership: "owned", count: 1 },
        ],
        choices: [{ country: "France", city: "Bougival", stock: "Bg/Stock", currency_id: 1 }],
        controls: {},
        staff: false,
        equipment_access: false,
        date: "2026-10-09",
        company_currency_id: 1,
    };
}
const INVESTOR_TOTALS = { inventory_value: { lines: [{ currency_id: 1, amount: 120 }], missing: [], provisional: [] } };

/**
 * fields_get as the server gives it: the fields the user may read. (The mock server's
 * own fields_get cannot take `attributes`.) Without `accountant`, the accounting fields
 * are absent, as for an investor (field groups).
 */
function serverFields({ accountant = false } = {}) {
    const selection = {
        family: [["asset", "Asset"], ["consumable", "Consumable"]],
        ownership_status: [["owned", "Owned"], ["borrowed", "Borrowed"], ["rented", "Rented"], ["lent_out", "Lent Out"]],
    };
    const strings = { inventory_value: "Inventory Value (excl. tax)", accounting_value: "Net Book Value" };
    const types = {
        family: "selection", ownership_status: "selection", product_name: "char",
        equipment_name: "char", serial: "char", category_name: "char", stock_name: "char",
        location_name: "char", city: "char", country_name: "char", quantity: "float",
        uom_name: "char", currency_id: "integer", inventory_value: "float",
        inventory_value_known: "integer", inventory_value_rate_missing: "integer",
        inventory_value_source_amount: "float", inventory_value_source_currency_id: "integer",
        accounting_value: "float", accounting_value_known: "integer",
        accounting_value_rate_missing: "integer", accounting_value_source_amount: "float",
        accounting_value_source_currency_id: "integer", accounting_provisional: "integer",
    };
    onRpc(MODEL, "fields_get", () => {
        const result = { id: { string: "ID", type: "integer" } };
        for (const [name, type] of Object.entries(types)) {
            if (name.startsWith("accounting_") && !accountant) {
                continue;
            }
            result[name] = { string: strings[name] || name, type, selection: selection[name], help: "" };
        }
        return result;
    });
}
function investorFields() {
    serverFields();
}

async function openDashboard() {
    await mountWithCleanup(WebClient);
    await getService("action").doAction("lartdubati_stock_monitor");
    await animationFrame();
}

test("first display: fields_get, aggregates and one page of the list", async () => {
    const calls = [];
    investorFields();
    onRpc(MODEL, "get_dashboard_data", () => dashboardData(INVESTOR_TOTALS));
    onRpc(MODEL, "*", ({ method, kwargs }) => {
        calls.push(method);
        if (method === "web_search_read") {
            expect(kwargs.limit).toBe(25);
            expect(kwargs.count_limit).toBe(1);
            expect(Object.keys(kwargs.specification)).not.toInclude("accounting_value");
        }
    });
    await openDashboard();
    expect(calls).toEqual(["fields_get", "get_dashboard_data", "web_search_read"]);
    expect(".o_smm_row").toHaveCount(2);
    expect(".o_smm_card_inventory_value").toHaveCount(1);
    // a field the user may not read gives no card and no column
    expect(".o_smm_card_accounting_value").toHaveCount(0);
    expect(".o_smm_col_accounting").toHaveCount(0);
});

test("a field readable by the user gives its card and its column", async () => {
    serverFields({ accountant: true });
    onRpc(MODEL, "get_dashboard_data", () =>
        dashboardData({ ...INVESTOR_TOTALS, accounting_value: { lines: [{ currency_id: 1, amount: 80 }], missing: [], provisional: [] } })
    );
    await openDashboard();
    expect(".o_smm_card_accounting_value").toHaveCount(1);
    expect("th.o_smm_col_accounting").toHaveCount(1);
});

test("keyboard: Enter opens the detail, Escape closes it and gives the focus back", async () => {
    investorFields();
    onRpc(MODEL, "get_dashboard_data", () => dashboardData(INVESTOR_TOTALS));
    await openDashboard();
    const row = queryFirst(".o_smm_row");
    row.focus();
    await press("Enter");
    await animationFrame();
    expect(".o_smm_detail").toHaveCount(1);
    expect(".o_smm_close").toBeFocused();
    await press("Escape");
    await animationFrame();
    expect(".o_smm_detail").toHaveCount(0);
    expect(queryFirst(".o_smm_row")).toBeFocused();
});

test("ownership chip: pressed state and filter sent to the server", async () => {
    const filters = [];
    investorFields();
    onRpc(MODEL, "get_dashboard_data", ({ args }) => {
        filters.push(args[0]);
        return dashboardData(INVESTOR_TOTALS);
    });
    await openDashboard();
    const chip = queryAll(".o_smm_chip.o_smm_owned")[0];
    expect(chip).toHaveAttribute("aria-pressed", "false");
    await contains(".o_smm_chip.o_smm_owned").click();
    await animationFrame();
    expect(".o_smm_chip.o_smm_owned").toHaveAttribute("aria-pressed", "true");
    expect(filters.at(-1)).toEqual({ ownerships: ["owned"] });
});

test("RPC error: a banner and no figure, then Retry", async () => {
    let fail = true;
    investorFields();
    onRpc(MODEL, "get_dashboard_data", () => {
        if (fail) {
            fail = false;
            throw new Error("server down");
        }
        return dashboardData(INVESTOR_TOTALS);
    });
    await openDashboard();
    expect(".o_smm_error").toHaveCount(1);
    expect(".o_smm_card_inventory_value").toHaveCount(0);
    await contains(".o_smm_retry").click();
    await animationFrame();
    expect(".o_smm_error").toHaveCount(0);
    expect(".o_smm_card_inventory_value").toHaveCount(1);
});
