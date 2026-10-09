/** @odoo-module **/
// Mock-up of the stock monitor dashboard (phase 3). Static demo data, no model.
// The real dashboard reads lartdubati.stock.monitor through the ORM, page by page
// (web_search_read with limit/offset/order) and aggregated (read_group), under the
// record rules and field groups of the user. Here the demo rows are computed and
// filtered in JS only because there is no server: this is NOT the target design.
// The « view as » and « simulate » switches only exist in the mock-up.

import { Component, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Pager } from "@web/core/pager/pager";
import { SelectMenu } from "@web/core/select_menu/select_menu";
import { COMPANY_CURRENCY, CONTROLS, ITEMS, OUTSIDE_STOCK, RATES, STOCKS, TODAY } from "./data";

const OWNERSHIP = {
    owned: { label: "Possédé", icon: "fa-home" },
    borrowed: { label: "Emprunté", icon: "fa-sign-in" },
    rented: { label: "Loué", icon: "fa-refresh" },
    lent_out: { label: "Prêté", icon: "fa-sign-out" },
};
// level: danger (wrong or missing figure), warning (to check), info.
// scope: who sees it (investor = every user who sees the figure; staff; accountant).
const ALERTS = {
    missing_rate: { label: "Taux de change manquant", help: "Montant gardé dans sa devise d'origine, exclu des totaux.", level: "danger", scope: "investor" },
    integrity: { label: "N° de série à plusieurs emplacements", help: "Plusieurs quants internes positifs pour un même numéro de série : une seule ligne, valeurs comptées une fois.", level: "danger", scope: "staff" },
    rental_ended: { label: "Location terminée, matériel présent", help: "Le contrat de location est échu mais le matériel est toujours en stock.", level: "danger", scope: "staff" },
    outside_stock: { label: "Hors de tout stock du moniteur", help: "Emplacement interne sans stock du moniteur au-dessus.", level: "danger", scope: "staff" },
    no_replacement: { label: "Valeur de remplacement manquante", help: "Obligatoire pour un bien emprunté ou loué.", level: "warning", scope: "staff" },
    replacement_old: { label: "Valeur de remplacement > 12 mois", help: "À réévaluer (seuil réglable).", level: "warning", scope: "staff" },
    lent_uninsured: { label: "Matériel prêté non assuré", help: "Bien de la société chez un tiers, sans assurance.", level: "warning", scope: "staff" },
    period_unsupported: { label: "Périodicité de loyer non gérée", help: "Loyer hebdomadaire ou journalier : pas d'équivalent mensuel, exclu du total des loyers en cours.", level: "warning", scope: "staff" },
    no_asset: { label: "Matériel sans immobilisation", help: "Catégorie non immobilisée : passé en charge, valeur comptable nulle.", level: "warning", scope: "staff" },
    no_responsible: { label: "Responsable manquant", help: "Un équipement intégré doit avoir un responsable.", level: "warning", scope: "staff" },
    asset_draft: { label: "Immobilisation en brouillon", help: "Valeur comptable provisoire jusqu'à la validation de l'immobilisation.", level: "warning", scope: "accountant" },
};
const PROFILES = {
    investor: { label: "Investisseur", staff: false, accountant: false },
    store: { label: "Magasin", staff: true, accountant: false },
    accountant: { label: "Comptable", staff: true, accountant: true },
};
// P8: monthly equivalent = amount / (months per period × interval); others unsupported.
const PERIOD = {
    monthly: { label: "mois", months: 1 },
    monthlylastday: { label: "mois (fin)", months: 1 },
    quarterly: { label: "trimestre", months: 3 },
    semesterly: { label: "semestre", months: 6 },
    yearly: { label: "an", months: 12 },
    weekly: { label: "semaine", months: null },
    daily: { label: "jour", months: null },
};
const ASSET_STATE = { draft: "Brouillon", open: "En cours", close: "Clôturée", removed: "Sortie" };
const PAGE = 10;

function rateAt(cur, date) {
    const list = RATES[cur];
    if (!list) {
        return null;
    }
    let found = null;
    for (const [day, rate] of list) {
        if (day <= date) {
            found = { rate, date: day };
        }
    }
    return found;
}

// One measure: converted value (null when a rate is missing, never 0), source amount,
// source currency, rate and rate date.
function measure(amount, from, to, date, label) {
    if (amount === null || amount === undefined) {
        return { value: null, label, empty: true };
    }
    if (from === to) {
        return { value: amount, amount, cur: from, label, ok: true };
    }
    const src = rateAt(from, date);
    const dst = rateAt(to, date);
    if (!src || !dst) {
        return { value: null, amount, cur: from, label, ok: false, date };
    }
    const rate = dst.rate / src.rate;
    return { value: amount * rate, amount, cur: from, label, ok: true, converted: true, rate, rateDate: dst.date };
}

function compute(item) {
    const stock = STOCKS.find((s) => s.id === item.stock) || OUTSIDE_STOCK;
    const cur = stock.currency;
    const row = { ...item, stockRec: stock, cur, m: {} };
    const C = COMPANY_CURRENCY;
    const companyOwned = ["owned", "lent_out"].includes(item.ownership);
    const zero = (label) => measure(0, cur, cur, TODAY, label);
    if (item.family === "consumable") {
        const value = item.qty * item.unit;
        row.m.inv = measure(value, C, cur, TODAY, "Valeur d'inventaire (coût moyen)");
        row.m.stock = measure(value, C, cur, TODAY, "Valeur de stock");
        row.m.acct = measure(value, C, cur, TODAY, "Valeur comptable");
    } else if (companyOwned) {
        if (item.fa) {
            row.m.orig = measure(item.fa.orig, C, cur, item.fa.date, "Valeur d'origine");
            row.m.dep = measure(item.fa.dep, C, cur, item.fa.date, "Amortissements comptabilisés");
            row.m.inv = measure(item.fa.orig, C, cur, item.fa.date, "Valeur d'inventaire (valeur d'origine)");
            row.m.stock = zero("Valeur de stock");
            row.m.acct = measure(item.fa.orig - item.fa.dep, C, cur, item.fa.date, "Valeur nette comptable");
            row.provisional = item.fa.state === "draft";
        } else {
            row.m.inv = measure(item.cost.amount, C, cur, item.cost.date, "Valeur d'inventaire (coût d'achat)");
            row.m.stock = item.treatment === "valued" ? measure(item.cost.amount, C, cur, TODAY, "Valeur de stock") : zero("Valeur de stock");
            row.m.acct = item.treatment === "valued" ? measure(item.cost.amount, C, cur, TODAY, "Valeur comptable (stock)") : zero("Valeur comptable");
        }
    } else {
        row.m.inv = item.repl ? measure(item.repl.amount, item.repl.cur, cur, item.repl.date, "Valeur d'inventaire (remplacement)") : measure(null, cur, cur, TODAY, "Valeur d'inventaire");
        row.m.stock = zero("Valeur de stock");
        row.m.acct = zero("Valeur comptable");
    }
    if (item.repl) {
        row.m.repl = measure(item.repl.amount, item.repl.cur, cur, item.repl.date, "Valeur de remplacement");
    }
    const rent = item.rent;
    row.rentActive = Boolean(rent && rent.start <= TODAY && (!rent.end || rent.end >= TODAY));
    if (row.rentActive) {
        const months = PERIOD[rent.rule].months;
        row.m.rent = months ? measure(rent.amount / (months * rent.interval), rent.cur, cur, rent.start, "Loyer en cours (équiv. mensuel)") : measure(null, cur, cur, TODAY, "Loyer en cours (équiv. mensuel)");
    }
    if (item.bills) {
        const parts = item.bills.map((b) => measure(b.amount, C, cur, b.date, "Loyers payés"));
        const missing = parts.some((p) => !p.ok);
        const source = item.bills.reduce((n, b) => n + b.amount, 0);
        row.m.paid = missing
            ? { value: null, amount: source, cur: C, label: "Loyers payés", ok: false }
            : { value: parts.reduce((n, p) => n + p.value, 0), amount: source, cur: C, label: "Loyers payés", ok: true, converted: C !== cur, perBill: true };
    }
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
        this.root = useRef("root");
        this.closeButton = useRef("closeButton");
        this.state = useState({
            profile: "accountant",
            sim: "data",
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
        this.lastRow = null;
        this.OWNERSHIP = OWNERSHIP;
        this.ALERTS = ALERTS;
        this.PERIOD = PERIOD;
        this.ASSET_STATE = ASSET_STATE;
        this.TODAY = TODAY;
        // Focus goes into the panel when it opens, and back to the row when it closes.
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

    // ---- mock-up switches ------------------------------------------------------------
    get profile() {
        return PROFILES[this.state.profile];
    }
    get profiles() {
        return Object.entries(PROFILES).map(([key, p]) => ({ key, label: p.label }));
    }
    get sims() {
        return [
            { key: "data", label: "Données" },
            { key: "loading", label: "Chargement" },
            { key: "empty", label: "Aucun résultat" },
            { key: "error", label: "Erreur RPC" },
        ];
    }
    setProfile(key) {
        Object.assign(this.state, { profile: key, alert: null, selected: null, offset: 0 });
        if (!PROFILES[key].staff && this.state.stock === 0) {
            this.state.stock = "all";
        }
    }
    setSim(key) {
        Object.assign(this.state, { sim: key, selected: null });
    }
    retry() {
        this.state.sim = "data";
    }
    alertVisible(code) {
        const scope = ALERTS[code].scope;
        return scope === "investor" || (scope === "staff" && this.profile.staff) || (scope === "accountant" && this.profile.accountant);
    }
    rowAlerts(row) {
        return row.alerts.filter((code) => this.alertVisible(code));
    }

    // ---- selection: country, city, stock ------------------------------------------
    get stocks() {
        return this.profile.staff ? [...STOCKS, OUTSIDE_STOCK] : [...STOCKS];
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
            (s) => (this.state.country === "all" || s.country === this.state.country) && (this.state.city === "all" || s.city === this.state.city)
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
        Object.assign(this.state, { country: "all", city: "all", stock: "all", family: "all", ownership: [], alert: null, search: "", offset: 0, selected: null, sim: this.state.sim === "empty" ? "data" : this.state.sim });
    }
    get hasFilters() {
        const s = this.state;
        return s.country !== "all" || s.city !== "all" || s.stock !== "all" || s.family !== "all" || s.ownership.length || s.alert || s.search;
    }

    // ---- rows (server side in the real dashboard) -------------------------------------
    get visibleRows() {
        if (this.state.sim === "empty") {
            return [];
        }
        return ROWS.filter((r) => this.profile.staff || r.stock !== 0);
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
        const num = (m) => (m && m.value !== null ? m.value : -1);
        const key = {
            name: (r) => r.name,
            stock: (r) => `${r.stock === 0 ? "￿" : r.stockRec.name} ${r.family} ${r.name}`,
            ownership: (r) => OWNERSHIP[r.ownership].label,
            qty: (r) => r.qty,
            inv: (r) => num(r.m.inv),
            acct: (r) => num(r.m.acct),
            rent: (r) => num(r.m.rent),
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
        Object.assign(this.state, { offset, selected: null });
    }
    sortBy(field) {
        const sort = this.state.sort;
        this.state.sort = { field, asc: sort.field === field ? !sort.asc : true };
        this.state.offset = 0;
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
    onSearch(ev) {
        Object.assign(this.state, { search: ev.target.value, offset: 0, selected: null });
    }

    // ---- totals per currency (read_group in the real dashboard) ----------------------------
    totals(rows, key) {
        const byCur = {};
        const missing = {};
        const provisional = {};
        for (const r of rows) {
            const m = r.m[key];
            if (!m || m.empty) {
                continue;
            }
            if (m.value !== null) {
                byCur[r.cur] = (byCur[r.cur] || 0) + m.value;
                if (key === "acct" && r.provisional) {
                    provisional[r.cur] = (provisional[r.cur] || 0) + m.value;
                }
            } else if (m.ok === false) {
                missing[m.cur] = (missing[m.cur] || 0) + m.amount;
            }
        }
        return {
            lines: Object.entries(byCur).map(([cur, amount]) => ({ cur, amount })),
            missing: Object.entries(missing).map(([cur, amount]) => ({ cur, amount })),
            provisional: Object.entries(provisional).map(([cur, amount]) => ({ cur, amount })),
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
            { key: "inv", icon: "fa-archive", title: "Valeur d'inventaire", note: "Tout ce qui est physiquement dans le stock, quel qu'en soit le propriétaire", ...this.totals(rows, "inv") },
        ];
        if (this.profile.staff) {
            cards.push({ key: "stock", icon: "fa-cube", title: "Valeur de stock", note: "Valorisation du stock ; biens immobilisés à 0", ...this.totals(rows, "stock") });
        }
        if (this.profile.accountant) {
            cards.push({ key: "acct", icon: "fa-balance-scale", title: "Valeur nette comptable", note: "Biens de la société uniquement", ...this.totals(rows, "acct") });
        }
        if (this.profile.staff) {
            const active = rows.filter((r) => r.rentActive).length;
            cards.push({ key: "rent", icon: "fa-refresh", title: "Loyers en cours", note: `${active} location${active > 1 ? "s" : ""} active${active > 1 ? "s" : ""} · équivalent mensuel`, ...this.totals(rows, "rent") });
        }
        if (this.profile.accountant) {
            cards.push({ key: "paid", icon: "fa-check-square-o", title: "Loyers payés (cumul)", note: "Factures comptabilisées HT, avoirs déduits", ...this.totals(rows, "paid") });
        }
        return cards;
    }
    get skeletonCards() {
        return this.profile.accountant ? [1, 2, 3, 4, 5, 6] : this.profile.staff ? [1, 2, 3, 4] : [1, 2];
    }
    get currencyMix() {
        return new Set(this.filteredRows.map((r) => r.cur)).size > 1;
    }

    // ---- stock cards -------------------------------------------------------------------
    get stockCards() {
        const own = this.state.ownership;
        return this.geoStocks.map((s) => {
            const rows = this.visibleRows.filter(
                (r) => r.stock === s.id && (this.state.family === "all" || r.family === this.state.family) && (!own.length || own.includes(r.ownership))
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
        const order = Object.keys(ALERTS);
        return Object.entries(counts)
            .sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0]))
            .map(([code, count]) => ({ code, count, ...ALERTS[code] }));
    }
    get controls() {
        return this.profile.staff ? CONTROLS : [];
    }
    get alertTotal() {
        return this.alertSummary.reduce((n, a) => n + a.count, 0);
    }
    filterAlert(code) {
        Object.assign(this.state, { alert: this.state.alert === code ? null : code, offset: 0, selected: null });
    }

    // ---- detail and keyboard -------------------------------------------------------------
    get selectedRow() {
        return ROWS.find((r) => r.id === this.state.selected) || null;
    }
    openRow(row) {
        this.lastRow = row.id;
        this.state.selected = this.state.selected === row.id ? null : row.id;
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
        this.state.selected = null;
    }
    openAnalysis() {
        this.notification.add("Ouvre les vues standard (liste, tableau croisé, graphique, export) avec les filtres actuels et les mêmes restrictions.", { title: "Analyse détaillée", type: "info" });
    }
    measuresFor(row) {
        const keys = ["inv", "repl"];
        if (this.profile.staff) {
            keys.push("stock");
        }
        if (this.profile.accountant) {
            keys.push("orig", "dep", "acct");
        }
        return keys.map((k) => ({ key: k, ...row.m[k] })).filter((m) => m.label);
    }
    conversionsFor(row) {
        const keys = Object.keys(row.m).filter((k) => {
            if (k === "inv" || k === "repl") {
                return true;
            }
            if (k === "stock" || k === "rent") {
                return this.profile.staff;
            }
            return this.profile.accountant;
        });
        return keys.map((k) => row.m[k]).filter((m) => m && !m.empty && (m.ok === false || m.converted));
    }

    // ---- formatting (Odoo formatMonetary in the real dashboard) ---------------------------
    money(amount, cur, digits = 0) {
        if (amount === null || amount === undefined) {
            return "—";
        }
        return new Intl.NumberFormat("fr-FR", { style: "currency", currency: cur, currencyDisplay: cur === "EUR" ? "symbol" : "code", minimumFractionDigits: digits, maximumFractionDigits: digits }).format(amount);
    }
    cell(row, key) {
        const m = row.m[key];
        if (!m || m.empty) {
            return "—";
        }
        return m.value === null ? this.money(m.amount, m.cur) : this.money(m.value, row.cur);
    }
    number(value) {
        return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 6 }).format(value);
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
        if (!rent) {
            return "";
        }
        const every = rent.interval > 1 ? `${rent.interval} ` : "";
        return `${this.money(rent.amount, rent.cur)} / ${every}${PERIOD[rent.rule].label}`;
    }
}

registry.category("actions").add("lartdubati_stock_monitor_mockup", StockMonitorDashboard);
