/** @odoo-module **/
// Stock monitor dashboard (docs/phase3/PLAN.md §4.1, 4.3, 4.5).
// Everything is read through the ORM under the user's rights, never sudo:
//   1. fields_get: the fields the user may read (others are absent and never asked for);
//   2. get_dashboard_data(filters): every aggregate, and the domain of the filters;
//   3. web_search_read: one page of the list (limit, offset, order) with that domain.
// Nothing is computed in the browser but the display.

import { Component, onWillStart, useEffect, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { deserializeDate, formatDate } from "@web/core/l10n/dates";
import { Pager } from "@web/core/pager/pager";
import { registry } from "@web/core/registry";
import { SelectMenu } from "@web/core/select_menu/select_menu";
import { useService } from "@web/core/utils/hooks";
import { formatFloat, formatMonetary } from "@web/views/fields/formatters";

export const MODEL = "lartdubati.stock.monitor";
export const PAGE = 25;
const OUTSIDE = "__outside__";

const OWNERSHIP_ICONS = { owned: "fa-home", borrowed: "fa-sign-in", rented: "fa-refresh", lent_out: "fa-sign-out" };
// blocking alerts (wrong or missing figure); the others are « to check »
const BLOCKING = new Set([
    "alert_rate_missing",
    "inventory_value_rate_missing",
    "replacement_value_rate_missing",
    "alert_integrity",
    "alert_no_position",
    "alert_negative_quantity",
    "alert_cost_missing",
    "alert_outside_stock",
    "alert_rental_ended",
    "alert_asset_removed",
    "alert_asset_missing",
]);
const ALERT_ORDER = [
    "alert_rate_missing",
    "inventory_value_rate_missing",
    "replacement_value_rate_missing",
    "alert_integrity",
    "alert_no_position",
    "alert_negative_quantity",
    "alert_cost_missing",
    "alert_outside_stock",
    "alert_rental_ended",
    "alert_asset_removed",
    "alert_asset_missing",
    "alert_replacement_missing",
    "alert_replacement_old",
    "alert_lent_uninsured",
    "alert_rent_period_unsupported",
    "alert_no_asset",
    "alert_no_responsible",
];
// summary cards: measure -> icon
const CARDS = [
    ["inventory_value", "fa-archive"],
    ["stock_value", "fa-cube"],
    ["accounting_value", "fa-balance-scale"],
    ["rent_monthly", "fa-refresh"],
    ["rent_paid", "fa-check-square-o"],
];
// list columns that can be sorted, when readable
const SORTABLE = ["product_name", "stock_name", "ownership_status", "quantity", "inventory_value", "accounting_value", "rent_monthly"];
const MEASURES = ["inventory_value", "replacement_value", "stock_value", "original_value", "depreciated_value", "accounting_value", "rent_monthly"];

export class StockMonitorDashboard extends Component {
    static template = "lartdubati_investor_home.StockMonitorDashboard";
    static components = { Pager, SelectMenu };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.root = useRef("root");
        this.closeButton = useRef("closeButton");
        this.OWNERSHIP_ICONS = OWNERSHIP_ICONS;
        this.OUTSIDE = OUTSIDE;
        this.limit = PAGE;
        this.state = useState({
            loading: true,
            error: false,
            data: null,
            rows: [],
            filters: { countries: [], cities: [], stocks: [], families: [], ownerships: [], alert: false, search: "" },
            sort: { field: "stock_name", asc: true },
            offset: 0,
            selected: null,
            detail: null,
            alertsOpen: true,
        });
        this.fields = {};
        this.loadId = 0;
        this.lastRow = null;
        this.searchTimer = null;
        onWillStart(async () => {
            this.fields = await this.orm.call(MODEL, "fields_get", [], {
                attributes: ["string", "type", "selection", "help"],
            });
            await this.load();
        });
        // focus goes into the panel when it opens, and back to the row when it closes
        useEffect(
            (selected) => {
                if (selected && this.closeButton.el) {
                    this.closeButton.el.focus();
                } else if (!selected && this.lastRow !== null && this.root.el) {
                    const el = this.root.el.querySelector(`[data-row-id="${this.lastRow}"]`);
                    if (el) {
                        el.focus();
                    }
                }
            },
            () => [this.state.selected]
        );
    }

    // ---- data ------------------------------------------------------------------------

    has(name) {
        return name in this.fields;
    }
    get listFields() {
        const names = [
            "family", "product_name", "equipment_name", "serial", "category_name", "stock_name",
            "location_name", "ownership_status", "quantity", "uom_name", "lot_quant_count",
            "accounting_provisional", "rent_amount", "rent_currency_id", "rent_rule_type",
            "rent_interval", "rent_start", "rent_end", "currency_id",
        ];
        for (const measure of ["inventory_value", "accounting_value", "rent_monthly"]) {
            names.push(measure, `${measure}_known`, `${measure}_rate_missing`, `${measure}_source_amount`, `${measure}_source_currency_id`);
        }
        names.push(...ALERT_ORDER);
        return names.filter((name) => this.has(name));
    }
    get order() {
        const { field, asc } = this.state.sort;
        const direction = asc ? "asc" : "desc";
        const fields = field === "stock_name" ? ["stock_name", "family", "product_name"] : [field];
        return [...fields.map((name) => `${name} ${direction}`), "id asc"].join(", ");
    }
    specification(names) {
        const spec = {};
        for (const name of names) {
            // many2one: the id only; labels come from the text columns of the view
            spec[name] = {};
        }
        return spec;
    }
    async load({ keepOffset = false } = {}) {
        const loadId = ++this.loadId;
        if (!keepOffset) {
            this.state.offset = 0;
        }
        Object.assign(this.state, { loading: true, error: false, selected: null, detail: null });
        try {
            const data = await this.orm.call(MODEL, "get_dashboard_data", [this.cleanFilters()]);
            const page = await this.orm.webSearchRead(MODEL, data.domain, {
                specification: this.specification(this.listFields),
                limit: PAGE,
                offset: this.state.offset,
                order: this.order,
                // the total comes from get_dashboard_data: count_limit 1 skips the second
                // count web_search_read would make (its `length` is not used)
                count_limit: 1,
            });
            if (loadId !== this.loadId) {
                return;
            }
            Object.assign(this.state, { data, rows: page.records, loading: false });
        } catch (error) {
            if (loadId !== this.loadId) {
                return;
            }
            // never keep the previous figures as if they were current
            Object.assign(this.state, { data: null, rows: [], loading: false, error: true });
            if (!(error && error.name === "RPC_ERROR")) {
                throw error;
            }
        }
    }
    async loadPage() {
        const loadId = ++this.loadId;
        try {
            const page = await this.orm.webSearchRead(MODEL, this.state.data.domain, {
                specification: this.specification(this.listFields),
                limit: PAGE,
                offset: this.state.offset,
                order: this.order,
                count_limit: 1,
            });
            if (loadId === this.loadId) {
                Object.assign(this.state, { rows: page.records, selected: null, detail: null });
            }
        } catch {
            if (loadId === this.loadId) {
                Object.assign(this.state, { data: null, rows: [], error: true });
            }
        }
    }
    cleanFilters() {
        const filters = {};
        for (const [key, value] of Object.entries(this.state.filters)) {
            if (Array.isArray(value) ? value.length : value) {
                filters[key] = Array.isArray(value) ? [...value] : value;
            }
        }
        return filters;
    }
    retry() {
        this.load();
    }

    // ---- selection: country, city, stock ------------------------------------------

    get choices() {
        return this.state.data ? this.state.data.choices : [];
    }
    get countryChoices() {
        const countries = [...new Set(this.choices.map((c) => c.country).filter(Boolean))].sort();
        return [{ value: "", label: _t("All countries") }, ...countries.map((c) => ({ value: c, label: c }))];
    }
    get cityChoices() {
        const [country] = this.state.filters.countries;
        const cities = this.choices.filter((c) => c.city && (!country || c.country === country)).map((c) => c.city);
        return [{ value: "", label: _t("All cities") }, ...[...new Set(cities)].sort().map((c) => ({ value: c, label: c }))];
    }
    get stockGroups() {
        const [country] = this.state.filters.countries;
        const [city] = this.state.filters.cities;
        const groups = {};
        for (const c of this.choices) {
            if ((country && c.country !== country) || (city && c.city !== city)) {
                continue;
            }
            const key = c.stock === OUTSIDE ? _t("Control") : `${c.country} · ${c.city}`;
            const label = c.stock === OUTSIDE ? _t("Outside any monitor stock") : c.stock;
            (groups[key] = groups[key] || []).push({ value: c.stock, label });
        }
        return Object.entries(groups).map(([label, choices]) => ({ label, choices }));
    }
    get stockChoices() {
        return [{ value: "", label: _t("All stocks") }];
    }
    single(key) {
        return this.state.filters[key][0] || "";
    }
    setFilter(changes) {
        Object.assign(this.state.filters, changes);
        this.load();
    }
    onCountry(value) {
        this.setFilter({ countries: value ? [value] : [], cities: [], stocks: [] });
    }
    onCity(value) {
        const choice = this.choices.find((c) => c.city === value);
        const changes = { cities: value ? [value] : [], stocks: [] };
        if (choice && !this.state.filters.countries.length) {
            changes.countries = [choice.country];
        }
        this.setFilter(changes);
    }
    onStock(value) {
        const choice = this.choices.find((c) => c.stock === value);
        const changes = { stocks: value ? [value] : [] };
        if (choice && choice.stock !== OUTSIDE) {
            Object.assign(changes, { countries: [choice.country], cities: [choice.city] });
        }
        this.setFilter(changes);
    }
    selectStockCard(card) {
        if (this.single("stocks") === card.name) {
            this.setFilter({ stocks: [], countries: [], cities: [] });
        } else {
            this.onStock(card.name);
        }
    }
    resetAll() {
        Object.assign(this.state.filters, { countries: [], cities: [], stocks: [], families: [], ownerships: [], alert: false, search: "" });
        this.load();
    }
    get hasFilters() {
        const f = this.state.filters;
        return Boolean(f.countries.length || f.cities.length || f.stocks.length || f.families.length || f.ownerships.length || f.alert || f.search);
    }

    // ---- family and ownership ---------------------------------------------------------

    get family() {
        return this.state.filters.families[0] || "all";
    }
    get segments() {
        return this.state.data ? this.state.data.segments : [];
    }
    familyCount(family) {
        return this.segments.filter((s) => family === "all" || s.family === family).reduce((n, s) => n + s.count, 0);
    }
    setFamily(family) {
        this.setFilter({ families: family === "all" ? [] : [family] });
    }
    get ownershipKeys() {
        return (this.fields.ownership_status?.selection || []).map(([key, label]) => ({ key, label, icon: OWNERSHIP_ICONS[key] }));
    }
    ownershipLabel(key) {
        const found = (this.fields.ownership_status?.selection || []).find(([k]) => k === key);
        return found ? found[1] : key;
    }
    ownershipCount(key) {
        return this.segments
            .filter((s) => s.ownership === key && (this.family === "all" || s.family === this.family))
            .reduce((n, s) => n + s.count, 0);
    }
    toggleOwnership(key) {
        const list = [...this.state.filters.ownerships];
        const index = list.indexOf(key);
        if (index >= 0) {
            list.splice(index, 1);
        } else {
            list.push(key);
        }
        this.setFilter({ ownerships: list });
    }

    // ---- cards ------------------------------------------------------------------------

    get cards() {
        const data = this.state.data;
        const cards = [];
        for (const [name, icon] of CARDS) {
            const total = data.totals[name];
            if (!total) {
                continue;
            }
            cards.push({ key: name, icon, title: this.fields[name].string, note: this.cardNote(name), ...total });
        }
        return cards;
    }
    cardNote(name) {
        return {
            inventory_value: _t("Everything physically in the stock, whoever owns it"),
            stock_value: _t("Carried by the stock valuation; fixed assets count 0"),
            accounting_value: _t("Company property only"),
            rent_monthly: _t("Active rentals, monthly equivalent"),
            rent_paid: _t("Posted bills, refunds deducted"),
        }[name];
    }
    get countCard() {
        const data = this.state.data;
        return { assets: data.assets, consumables: data.count - data.assets };
    }
    get currencyMix() {
        const lines = this.state.data?.totals.inventory_value?.lines || [];
        return lines.length > 1;
    }
    get stockCards() {
        const stocks = this.state.data ? this.state.data.stocks : [];
        return stocks.filter((card) => card.name !== OUTSIDE || this.state.data.staff);
    }

    // ---- alerts -----------------------------------------------------------------------

    get alertSummary() {
        const counts = this.state.data ? this.state.data.alerts : {};
        return ALERT_ORDER.filter((name) => counts[name] && this.has(name)).map((name) => ({
            name,
            count: counts[name],
            label: this.fields[name].string,
            help: this.fields[name].help || "",
            blocking: BLOCKING.has(name),
        }));
    }
    get alertTotal() {
        return this.alertSummary.reduce((n, a) => n + a.count, 0);
    }
    get controls() {
        const controls = this.state.data ? this.state.data.controls : {};
        const texts = {
            to_complete: _t("equipment to complete (outside the monitor, not counted)"),
            serial_without_equipment: _t("serial numbers in stock without equipment (outside the monitor)"),
        };
        return Object.entries(controls)
            .filter(([, count]) => count)
            .map(([key, count]) => ({ key, count, text: texts[key] }));
    }
    filterAlert(name) {
        this.setFilter({ alert: this.state.filters.alert === name ? false : name });
    }
    rowAlerts(row) {
        return ALERT_ORDER.filter((name) => row[name]);
    }
    alertClass(name) {
        return BLOCKING.has(name) ? "o_smm_alert_danger" : "o_smm_alert_warning";
    }
    alertLabel(name) {
        return this.fields[name]?.string || name;
    }

    // ---- list ---------------------------------------------------------------------------

    sortBy(field) {
        const sort = this.state.sort;
        this.state.sort = { field, asc: sort.field === field ? !sort.asc : true };
        this.state.offset = 0;
        this.loadPage();
    }
    canSort(field) {
        return SORTABLE.includes(field) && this.has(field);
    }
    ariaSort(field) {
        const sort = this.state.sort;
        return sort.field !== field ? "none" : sort.asc ? "ascending" : "descending";
    }
    sortIcon(field) {
        const sort = this.state.sort;
        if (sort.field !== field) {
            return "fa fa-sort o_smm_sort_idle";
        }
        return sort.asc ? "fa fa-sort-asc" : "fa fa-sort-desc";
    }
    onPager({ offset }) {
        this.state.offset = offset;
        this.loadPage();
    }
    onSearch(ev) {
        this.state.filters.search = ev.target.value;
        clearTimeout(this.searchTimer);
        this.searchTimer = setTimeout(() => this.load(), 300);
    }

    // ---- detail and keyboard ------------------------------------------------------------

    async openRow(row) {
        this.lastRow = row.id;
        if (this.state.selected === row.id) {
            this.closeDetail();
            return;
        }
        const names = Object.keys(this.fields).filter((name) => name !== "id");
        try {
            const [detail] = await this.orm.webRead(MODEL, [row.id], { specification: this.specification(names) });
            Object.assign(this.state, { selected: row.id, detail });
        } catch {
            this.notification.add(_t("The item could not be loaded."), { type: "danger" });
        }
    }
    onRowKey(ev, row) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.openRow(row);
        }
    }
    onKeydown(ev) {
        if (ev.key === "Escape" && this.state.selected) {
            ev.stopPropagation();
            this.closeDetail();
        }
    }
    closeDetail() {
        Object.assign(this.state, { selected: null, detail: null });
    }
    get detailMeasures() {
        const r = this.state.detail;
        return MEASURES.filter((name) => this.has(name) && r[`${name}_source_amount`] !== undefined && (r[`${name}_known`] || r[`${name}_rate_missing`] || r[name])).map((name) => ({
            name,
            label: this.fields[name].string,
            known: r[`${name}_known`],
            missing: r[`${name}_rate_missing`],
            fallback: r[`${name}_rate_fallback`],
            value: r[name],
            source: r[`${name}_source_amount`],
            sourceCurrency: r[`${name}_source_currency_id`],
            rate: r[`${name}_rate`],
            rateDate: r[`${name}_rate_date`],
            converted: r[`${name}_source_currency_id`] && r[`${name}_source_currency_id`] !== r.currency_id,
        }));
    }
    openEquipment() {
        const equipment = this.state.detail && this.state.detail.equipment_id;
        if (equipment) {
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "maintenance.equipment",
                res_id: equipment,
                views: [[false, "form"]],
            });
        }
    }
    openAnalysis() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Stock Monitor – Detailed Analysis"),
            res_model: MODEL,
            views: [[false, "list"], [false, "pivot"], [false, "graph"], [false, "form"]],
            domain: this.state.data ? this.state.data.domain : [],
            context: { group_by: ["currency_id", "stock_name"] },
        });
    }

    // ---- formatting -----------------------------------------------------------------------

    money(amount, currencyId, digits) {
        if (amount === false || amount === null || amount === undefined) {
            return "—";
        }
        const options = { currencyId };
        if (digits !== undefined) {
            options.digits = [16, digits];
        }
        return formatMonetary(amount, options);
    }
    whole(amount, currencyId) {
        return this.money(amount, currencyId, 0);
    }
    number(value) {
        return formatFloat(value, { digits: [16, 3], trailingZeros: false });
    }
    rate(value) {
        return formatFloat(value, { digits: [16, 6], trailingZeros: false });
    }
    date(value) {
        return value ? formatDate(deserializeDate(value)) : "";
    }
    selectionLabel(field, value) {
        const found = (this.fields[field]?.selection || []).find(([key]) => key === value);
        return found ? found[1] : value || "";
    }
    rentLabel(row) {
        if (!row.rent_amount && !row.rent_start) {
            return "";
        }
        const periods = {
            daily: _t("day"),
            weekly: _t("week"),
            monthly: _t("month"),
            monthlylastday: _t("month (last day)"),
            quarterly: _t("quarter"),
            semesterly: _t("semester"),
            yearly: _t("year"),
        };
        const every = row.rent_interval > 1 ? `${row.rent_interval} × ` : "";
        const period = periods[row.rent_rule_type] || row.rent_rule_type || "";
        return `${this.money(row.rent_amount, row.rent_currency_id)} / ${every}${period}`;
    }
    get today() {
        return this.state.data ? this.date(this.state.data.date) : "";
    }
}

registry.category("actions").add("lartdubati_stock_monitor", StockMonitorDashboard);
