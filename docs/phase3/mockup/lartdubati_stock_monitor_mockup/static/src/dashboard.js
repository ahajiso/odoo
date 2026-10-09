/** @odoo-module **/
// Mock-up of the stock monitor dashboard (phase 3). Static demo data, no model:
// the real dashboard reads lartdubati.stock.monitor through the ORM, under the
// record rules and field groups of the user. The « view as » switch only exists
// in the mock-up, to show what each profile sees.

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Pager } from "@web/core/pager/pager";
import { SelectMenu } from "@web/core/select_menu/select_menu";
import { COMPANY_CURRENCY, GLOBAL_ALERTS, ITEMS, OUTSIDE_STOCK, RATES, STOCKS, TODAY } from "./data";

const OWNERSHIP = {
    owned: { label: "Possédé", cls: "owned" },
    borrowed: { label: "Emprunté", cls: "borrowed" },
    rented: { label: "Loué", cls: "rented" },
    lent_out: { label: "Prêté", cls: "lent_out" },
};
const ALERTS = {
    missing_rate: { label: "Taux de change manquant", help: "Montant affiché dans sa devise d'origine, exclu des totaux.", level: "danger" },
    rental_ended: { label: "Location terminée, matériel présent", help: "Le contrat de location est échu mais le matériel est toujours en stock.", level: "danger" },
    outside_stock: { label: "Hors de tout stock du moniteur", help: "Emplacement interne sans stock du moniteur au-dessus.", level: "danger" },
    no_replacement: { label: "Valeur de remplacement manquante", help: "Obligatoire pour un bien emprunté ou loué.", level: "warning" },
    replacement_old: { label: "Valeur de remplacement > 12 mois", help: "À réévaluer.", level: "warning" },
    lent_uninsured: { label: "Matériel prêté non assuré", help: "Bien de la société chez un tiers, sans assurance.", level: "warning" },
};
const PROFILES = {
    investor: { label: "Investisseur", owner: false, rent: false, accounting: false, outside: false, alerts: ["missing_rate"] },
    store: { label: "Magasin", owner: true, rent: true, accounting: false, outside: true, alerts: null },
    accountant: { label: "Comptable", owner: true, rent: true, accounting: true, outside: true, alerts: null },
};
const PERIOD = { month: { label: "mois", monthly: 1 }, week: { label: "semaine", monthly: 52 / 12 } };
const PAGE = 10;

function convert(amount, from, to) {
    if (amount === null || amount === undefined) {
        return { value: null, ok: true };
    }
    const src = RATES[from];
    const dst = RATES[to];
    if (!src || !dst) {
        return { value: null, ok: false, amount, cur: from };
    }
    return { value: (amount / src.rate) * dst.rate, ok: true, converted: from !== to, amount, cur: from, rate: dst.rate / src.rate, date: dst.date };
}

function compute(item) {
    const stock = STOCKS.find((s) => s.id === item.stock) || OUTSIDE_STOCK;
    const cur = stock.currency;
    const row = { ...item, stockRec: stock, cur, unconverted: [], conversions: [] };
    const take = (field, label, amount, from) => {
        const res = convert(amount, from, cur);
        if (!res.ok) {
            row.unconverted.push({ field, label, amount, cur: from });
        } else if (res.converted) {
            row.conversions.push({ label, amount, cur: from, rate: res.rate, date: res.date });
        }
        return res.value;
    };
    const companyOwned = ["owned", "lent_out"].includes(item.ownership);
    if (item.family === "consumable") {
        row.orig = take("orig", "Valeur au coût moyen", item.qty * item.unit.cost, item.unit.cur);
        row.dep = 0;
        row.nbv = row.orig;
        row.inv = row.orig;
    } else if (companyOwned) {
        row.orig = take("orig", "Valeur d'origine", item.values.orig, item.values.cur);
        row.dep = take("dep", "Amortissements", item.values.dep, item.values.cur);
        row.nbv = row.orig - row.dep;
        row.inv = row.orig;
    } else {
        row.orig = null;
        row.dep = null;
        row.nbv = 0;
        row.repl = item.repl ? take("repl", "Valeur de remplacement", item.repl.amount, item.repl.cur) : null;
        row.inv = row.repl;
    }
    if (companyOwned && item.repl) {
        row.repl = take("repl", "Valeur de remplacement", item.repl.amount, item.repl.cur);
    }
    const rent = item.rent;
    row.rentActive = Boolean(rent && rent.start <= TODAY && (!rent.end || rent.end >= TODAY));
    row.rentMonthly = row.rentActive ? take("rent", "Loyer en cours (équiv. mensuel)", rent.amount * PERIOD[rent.period].monthly, rent.cur) : null;
    row.rentPaid = item.rentPaid ? take("rentPaid", "Loyers payés", item.rentPaid.amount, item.rentPaid.cur) : null;
    row.replDate = item.repl ? item.repl.date : null;
    row.alerts = item.alerts || [];
    return row;
}

const ROWS = ITEMS.map(compute);

export class StockMonitorDashboard extends Component {
    static template = "lartdubati_stock_monitor_mockup.Dashboard";
    static components = { Pager, SelectMenu };
    static props = ["*"];

    setup() {
        this.notification = useService("notification");
        this.state = useState({
            profile: "accountant",
            country: "all",
            city: "all",
            stock: "all",
            family: "all",
            ownership: [],
            alert: null,
            search: "",
            sort: { field: "stock", asc: true },
            offset: 0,
            selected: null,
            alertsOpen: true,
        });
        this.OWNERSHIP = OWNERSHIP;
        this.ALERTS = ALERTS;
        this.PERIOD = PERIOD;
        this.TODAY = TODAY;
        this.COMPANY_CURRENCY = COMPANY_CURRENCY;
    }

    // ---- profile -----------------------------------------------------------------
    get profile() {
        return PROFILES[this.state.profile];
    }
    get profiles() {
        return Object.entries(PROFILES).map(([key, p]) => ({ key, label: p.label }));
    }
    setProfile(key) {
        Object.assign(this.state, { profile: key, alert: null, selected: null, offset: 0 });
        if (!PROFILES[key].outside && this.state.stock === 0) {
            this.state.stock = "all";
        }
    }
    alertVisible(code) {
        const allowed = this.profile.alerts;
        return !allowed || allowed.includes(code);
    }
    rowAlerts(row) {
        return row.alerts.filter((code) => this.alertVisible(code));
    }

    // ---- selection: country, city, stock ------------------------------------------
    get stocks() {
        const list = [...STOCKS];
        if (this.profile.outside) {
            list.push(OUTSIDE_STOCK);
        }
        return list;
    }
    get countryChoices() {
        const countries = [...new Set(STOCKS.map((s) => s.country))];
        return [{ value: "all", label: "Tous les pays" }, ...countries.map((c) => ({ value: c, label: c }))];
    }
    get cityChoices() {
        const cities = STOCKS.filter((s) => this.state.country === "all" || s.country === this.state.country).map((s) => s.city);
        return [{ value: "all", label: "Toutes les villes" }, ...[...new Set(cities)].map((c) => ({ value: c, label: c }))];
    }
    get geoStocks() {
        return this.stocks.filter(
            (s) =>
                (this.state.country === "all" || s.country === this.state.country) &&
                (this.state.city === "all" || s.city === this.state.city)
        );
    }
    get stockGroups() {
        const groups = {};
        for (const s of this.geoStocks) {
            const key = s.id === 0 ? "Contrôle" : `${s.country} · ${s.city}`;
            (groups[key] = groups[key] || []).push({ value: s.id, label: s.name });
        }
        return Object.entries(groups).map(([label, choices]) => ({ label, choices }));
    }
    onCountry(value) {
        Object.assign(this.state, { country: value, city: "all", stock: "all", offset: 0, selected: null });
    }
    onCity(value) {
        const stock = value === "all" ? null : STOCKS.find((s) => s.city === value);
        Object.assign(this.state, { city: value, stock: "all", offset: 0, selected: null });
        if (stock && this.state.country === "all") {
            this.state.country = stock.country;
        }
    }
    onStock(value) {
        Object.assign(this.state, { stock: value, offset: 0, selected: null });
        const stock = STOCKS.find((s) => s.id === value);
        if (stock) {
            Object.assign(this.state, { country: stock.country, city: stock.city });
        }
    }
    selectStockCard(id) {
        this.onStock(this.state.stock === id ? "all" : id);
        if (this.state.stock === "all") {
            Object.assign(this.state, { country: "all", city: "all" });
        }
    }
    resetAll() {
        Object.assign(this.state, { country: "all", city: "all", stock: "all", family: "all", ownership: [], alert: null, search: "", offset: 0, selected: null });
    }
    get hasFilters() {
        const s = this.state;
        return s.country !== "all" || s.city !== "all" || s.stock !== "all" || s.family !== "all" || s.ownership.length || s.alert || s.search;
    }

    // ---- rows ----------------------------------------------------------------------
    get visibleRows() {
        return ROWS.filter((r) => this.profile.outside || r.stock !== 0);
    }
    get geoRows() {
        const ids = new Set(this.geoStocks.map((s) => s.id));
        return this.visibleRows.filter((r) => ids.has(r.stock) && (this.state.stock === "all" || r.stock === this.state.stock));
    }
    familyCount(family) {
        return this.geoRows.filter((r) => family === "all" || r.family === family).length;
    }
    get familyRows() {
        return this.geoRows.filter((r) => this.state.family === "all" || r.family === this.state.family);
    }
    ownershipCount(key) {
        return this.familyRows.filter((r) => r.ownership === key).length;
    }
    toggleOwnership(key) {
        const list = this.state.ownership;
        const index = list.indexOf(key);
        if (index >= 0) {
            list.splice(index, 1);
        } else {
            list.push(key);
        }
        Object.assign(this.state, { offset: 0, selected: null });
    }
    setFamily(family) {
        Object.assign(this.state, { family, offset: 0, selected: null });
    }
    get filteredRows() {
        const s = this.state;
        const term = s.search.trim().toLowerCase();
        return this.familyRows.filter(
            (r) =>
                (!s.ownership.length || s.ownership.includes(r.ownership)) &&
                (!s.alert || this.rowAlerts(r).includes(s.alert)) &&
                (!term || [r.name, r.serial, r.location, r.category, r.stockRec.name].some((v) => v && v.toLowerCase().includes(term)))
        );
    }
    get sortedRows() {
        const { field, asc } = this.state.sort;
        const key = {
            name: (r) => r.name,
            stock: (r) => `${r.stock === 0 ? "\uffff" : r.stockRec.name} ${r.family} ${r.name}`,
            ownership: (r) => OWNERSHIP[r.ownership].label,
            qty: (r) => r.qty,
            inv: (r) => r.inv ?? -1,
            nbv: (r) => r.nbv ?? -1,
            rent: (r) => r.rentMonthly ?? -1,
        }[field];
        return [...this.filteredRows].sort((a, b) => {
            const x = key(a);
            const y = key(b);
            const cmp = typeof x === "number" ? x - y : String(x).localeCompare(String(y), "fr");
            return asc ? cmp : -cmp;
        });
    }
    get pageRows() {
        return this.sortedRows.slice(this.state.offset, this.state.offset + PAGE);
    }
    get limit() {
        return PAGE;
    }
    onPager({ offset }) {
        this.state.offset = offset;
    }
    sortBy(field) {
        const sort = this.state.sort;
        this.state.sort = { field, asc: sort.field === field ? !sort.asc : true };
        this.state.offset = 0;
    }
    sortIcon(field) {
        const sort = this.state.sort;
        if (sort.field !== field) {
            return "fa fa-sort o_smm_sort_idle";
        }
        return sort.asc ? "fa fa-sort-asc" : "fa fa-sort-desc";
    }
    onSearch(ev) {
        Object.assign(this.state, { search: ev.target.value, offset: 0 });
    }

    // ---- totals per currency ----------------------------------------------------------
    totals(rows, field) {
        const byCur = {};
        const missing = {};
        for (const r of rows) {
            if (r[field] !== null && r[field] !== undefined) {
                byCur[r.cur] = (byCur[r.cur] || 0) + r[field];
            }
            for (const u of r.unconverted.filter((u) => u.field === field || (field === "rentMonthly" && u.field === "rent"))) {
                missing[u.cur] = (missing[u.cur] || 0) + u.amount;
            }
        }
        return {
            lines: Object.entries(byCur).map(([cur, amount]) => ({ cur, amount })),
            missing: Object.entries(missing).map(([cur, amount]) => ({ cur, amount })),
        };
    }
    get cards() {
        const rows = this.filteredRows;
        const assets = rows.filter((r) => r.family === "asset").length;
        const cards = [
            {
                key: "count",
                icon: "fa-cubes",
                title: "Articles",
                counts: [
                    { value: assets, label: assets > 1 ? "équipements" : "équipement" },
                    { value: rows.length - assets, label: "lignes de consommables" },
                ],
                note: "Quantités des consommables : par article (unités différentes)",
            },
            { key: "inv", icon: "fa-archive", title: "Valeur d'inventaire", note: "Tout ce qui est dans le stock, quel qu'en soit le propriétaire", ...this.totals(rows, "inv") },
        ];
        if (this.profile.accounting) {
            cards.push({ key: "nbv", icon: "fa-balance-scale", title: "Valeur comptable nette", note: "Biens de la société uniquement", ...this.totals(rows, "nbv") });
        }
        if (this.profile.rent) {
            const active = rows.filter((r) => r.rentActive).length;
            cards.push({ key: "rent", icon: "fa-refresh", title: "Loyers en cours", note: `${active} location${active > 1 ? "s" : ""} active${active > 1 ? "s" : ""} · équivalent mensuel`, ...this.totals(rows, "rentMonthly") });
        }
        if (this.profile.accounting) {
            cards.push({ key: "paid", icon: "fa-check-square-o", title: "Loyers payés (cumul)", note: "Factures validées moins avoirs", ...this.totals(rows, "rentPaid") });
        }
        return cards;
    }
    get currencyMix() {
        return new Set(this.filteredRows.map((r) => r.cur)).size > 1;
    }

    // ---- stock cards -------------------------------------------------------------------
    get stockCards() {
        return this.geoStocks.map((s) => {
            const own = this.state.ownership;
            const rows = this.visibleRows.filter(
                (r) =>
                    r.stock === s.id &&
                    (this.state.family === "all" || r.family === this.state.family) &&
                    (!own.length || own.includes(r.ownership))
            );
            const inv = this.totals(rows, "inv");
            return {
                stock: s,
                assets: rows.filter((r) => r.family === "asset").length,
                consumables: rows.filter((r) => r.family === "consumable").length,
                inv: inv.lines[0],
                missing: inv.missing.length,
                alerts: rows.reduce((n, r) => n + this.rowAlerts(r).length, 0),
                active: this.state.stock === s.id,
            };
        });
    }

    // ---- alerts --------------------------------------------------------------------------
    get alertSummary() {
        const counts = {};
        for (const r of this.geoRows) {
            for (const code of this.rowAlerts(r)) {
                counts[code] = (counts[code] || 0) + 1;
            }
        }
        return Object.entries(counts).map(([code, count]) => ({ code, count, ...ALERTS[code] }));
    }
    get globalAlerts() {
        return this.profile.outside ? GLOBAL_ALERTS : [];
    }
    get alertTotal() {
        return this.alertSummary.reduce((n, a) => n + a.count, 0) + this.globalAlerts.length;
    }
    filterAlert(code) {
        Object.assign(this.state, { alert: this.state.alert === code ? null : code, offset: 0, selected: null });
    }

    // ---- detail -------------------------------------------------------------------------
    get selectedRow() {
        return ROWS.find((r) => r.id === this.state.selected) || null;
    }
    openRow(row) {
        this.state.selected = this.state.selected === row.id ? null : row.id;
    }
    closeDetail() {
        this.state.selected = null;
    }
    openAnalysis() {
        this.notification.add("Ouvre les vues standard (liste, tableau croisé, graphique, export) avec les filtres actuels.", { title: "Analyse détaillée", type: "info" });
    }

    // ---- formatting --------------------------------------------------------------------
    money(amount, cur, digits = 0) {
        if (amount === null || amount === undefined) {
            return "—";
        }
        return new Intl.NumberFormat("fr-FR", { style: "currency", currency: cur, currencyDisplay: cur === "EUR" ? "symbol" : "code", minimumFractionDigits: digits, maximumFractionDigits: digits }).format(amount);
    }
    number(value) {
        return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(value);
    }
    date(value) {
        if (!value) {
            return "";
        }
        const [y, m, d] = value.split("-");
        return `${d}/${m}/${y}`;
    }
    rentLabel(row) {
        const rent = row.rent;
        return rent ? `${this.money(rent.amount, rent.cur)} / ${PERIOD[rent.period].label}` : "";
    }
}

registry.category("actions").add("lartdubati_stock_monitor_mockup", StockMonitorDashboard);
