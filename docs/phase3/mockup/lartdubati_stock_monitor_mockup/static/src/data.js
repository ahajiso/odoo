/** @odoo-module **/
// Demo data of the mock-up only. The real dashboard reads lartdubati.stock.monitor
// through the ORM: the SQL view computes the three values, the conversions and the
// alerts; nothing is computed in the browser. Here, values are computed in JS only to
// keep the demo data short and consistent.

export const TODAY = "2026-10-09";
export const COMPANY_CURRENCY = "EUR";
// Rates in units per 1 EUR, by date (res.currency.rate). USD has no rate on purpose.
export const RATES = {
    EUR: [["2000-01-01", 1]],
    IRR: [["2024-01-01", 45200], ["2025-06-01", 46400], ["2026-05-01", 47300], ["2026-08-01", 48100], ["2026-10-08", 48500]],
};

export const STOCKS = [
    { id: 1, name: "Bg/Stock", city: "Bougival", state: "Île-de-France", country: "France", currency: "EUR", place: "physical" },
    { id: 2, name: "Bg/Chantier Versailles", city: "Versailles", state: "Île-de-France", country: "France", currency: "EUR", place: "physical" },
    { id: 3, name: "WH/Chez tiers/SCI Les Tilleuls", city: "Lyon", state: "Auvergne-Rhône-Alpes", country: "France", currency: "EUR", place: "lent_out" },
    { id: 4, name: "THR/Stock", city: "Téhéran", state: "Téhéran", country: "Iran", currency: "IRR", place: "physical" },
    { id: 5, name: "ISF/Dépôt", city: "Ispahan", state: "Ispahan", country: "Iran", currency: "IRR", place: "physical" },
];

// Items not under any monitor stock (never shown to investors).
export const OUTSIDE_STOCK = { id: 0, name: "Hors stock du moniteur", city: "", state: "", country: "", currency: "EUR", place: "" };

// Accounting treatment of the product category:
// fixed: fixed-asset category (manual valuation, account.asset per unit);
// valued: automated stock valuation, no asset; expensed: manual valuation, expensed.
const asset = (vals) => ({ family: "asset", qty: 1, uom: "Unité", ...vals });
const consumable = (vals) => ({ family: "consumable", ownership: "owned", treatment: "valued", ...vals });

export const ITEMS = [
    // Bg/Stock
    asset({ id: 1, name: "Scie sur table Bosch GTS 10 XC", serial: "1234", stock: 1, location: "Bg/Stock", category: "All", treatment: "expensed", ownership: "owned", cost: { amount: 329, cur: "EUR", date: "2026-10-09" }, warranty: "Sous garantie", insurance: "Non applicable", acquired: "2026-10-09", responsible: null, alerts: ["no_asset", "no_responsible"] }),
    asset({ id: 2, name: "Perforateur Hilti TE 30-A36", serial: "H30-88412", stock: 1, location: "Bg/Stock/Étagère A", locations: ["Bg/Stock/Étagère A", "Bg/Stock/Retours"], category: "Matériel et outillage (immobilisé)", treatment: "fixed", ownership: "owned", fa: { ref: "IMM/2024/0031", state: "open", orig: 980, dep: 310, date: "2024-03-12" }, warranty: "Garantie expirée", insurance: "Assuré", acquired: "2024-03-12", responsible: "Farid Tehrani", alerts: ["integrity"] }),
    asset({ id: 3, name: "Laser rotatif Leica Rugby 640", serial: "LR-20931", stock: 1, location: "Bg/Stock/Étagère A", category: "Matériel et outillage (immobilisé)", treatment: "fixed", ownership: "owned", fa: { ref: "IMM/2024/0044", state: "open", orig: 1850, dep: 555, date: "2024-06-03" }, warranty: "Garantie expirée", insurance: "Assuré", acquired: "2024-06-03", responsible: "Farid Tehrani" }),
    asset({ id: 4, name: "Compresseur Atlas Copco C55", serial: "AC-77120", stock: 1, location: "Bg/Stock", category: "Matériel et outillage (immobilisé)", treatment: "fixed", ownership: "borrowed", owner: "Karim Rahimi (associé)", repl: { amount: 2400, cur: "EUR", date: "2026-03-15" }, contract: "CTR-F/2026/003 (prêt gratuit)", warranty: "Non applicable", insurance: "Assuré", acquired: "2026-03-15", responsible: "Farid Tehrani" }),
    asset({ id: 5, name: "Bétonnière Altrad B160", serial: "ALT-55102", stock: 1, location: "Bg/Stock", category: "Matériel et outillage (immobilisé)", treatment: "fixed", ownership: "borrowed", owner: "SARL Batinord", contract: "CTR-F/2026/005 (prêt gratuit)", warranty: "Non applicable", insurance: "Non assuré", acquired: "2026-09-28", responsible: "Farid Tehrani", alerts: ["no_replacement"] }),
    asset({ id: 6, name: "Mini-pelle Kubota U17-3", serial: "KU17-30882", stock: 1, location: "Bg/Stock", category: "Engins (immobilisé)", treatment: "fixed", ownership: "rented", owner: "Kiloutou", repl: { amount: 32000, cur: "EUR", date: "2026-09-02" }, rent: { amount: 1450, cur: "EUR", rule: "monthly", interval: 1, start: "2026-09-01", end: null, contract: "CTR-F/2026/004" }, bills: [{ amount: 1450, date: "2026-09-30" }], warranty: "Non applicable", insurance: "Assuré", acquired: "2026-09-01", responsible: "Farid Tehrani" }),
    asset({ id: 7, name: "Camion benne Renault Master", serial: "FX-482-KL", stock: 1, location: "Bg/Stock (équipement hors stock)", nonStock: true, category: "Véhicules (immobilisé)", treatment: "fixed", ownership: "owned", fa: { ref: "IMM/2025/0002", state: "open", orig: 38500, dep: 12833, date: "2025-01-20" }, warranty: "Sous garantie", insurance: "Assuré", acquired: "2025-01-20", responsible: "Hossein Karimi" }),
    asset({ id: 8, name: "Groupe électrogène SDMO Perform 6000", serial: "SD-60-1189", stock: 1, location: "Bg/Stock/Étagère B", category: "Petit matériel (valorisé en stock)", treatment: "valued", ownership: "owned", cost: { amount: 720, cur: "EUR", date: "2026-05-11" }, warranty: "Sous garantie", insurance: "Non applicable", acquired: "2026-05-11", responsible: "Farid Tehrani" }),
    consumable({ id: 101, name: "Ciment CEM II 35 kg", stock: 1, location: "Bg/Stock", category: "Consommables / Liants", qty: 42, uom: "Sac", unit: 9.8 }),
    consumable({ id: 102, name: "Plaque de plâtre BA13 250×120", stock: 1, location: "Bg/Stock/Étagère C", category: "Consommables / Plaques", qty: 68, uom: "Unité", unit: 7.45 }),
    consumable({ id: 103, name: "Vis placo 3,5×25 (boîte de 1000)", stock: 1, location: "Bg/Stock/Étagère C", category: "Consommables / Fixations", qty: 15, uom: "Boîte", unit: 18.9 }),
    consumable({ id: 104, name: "Rail R48 3 m", stock: 1, location: "Bg/Stock/Étagère C", category: "Consommables / Ossature", qty: 120, uom: "Unité", unit: 3.1 }),
    consumable({ id: 105, name: "Mortier colle C2", stock: 1, location: "Bg/Stock", category: "Consommables / Liants", qty: 20, uom: "Sac", unit: 14.2 }),
    consumable({ id: 106, name: "Sable 0/4", stock: 1, location: "Bg/Stock/Aire extérieure", category: "Consommables / Granulats", qty: 6.5, uom: "t", unit: 38 }),
    // Bg/Chantier Versailles
    asset({ id: 9, name: "Échafaudage roulant Altrad 8 m", serial: "ECH-8M-0412", stock: 2, location: "Bg/Chantier Versailles", category: "Échafaudages (immobilisé)", treatment: "fixed", ownership: "rented", owner: "Loxam", repl: { amount: 4200, cur: "EUR", date: "2025-06-20" }, rent: { amount: 95, cur: "EUR", rule: "weekly", interval: 1, start: "2026-09-15", end: null, contract: "CTR-F/2026/006" }, bills: [{ amount: 190, date: "2026-09-30" }, { amount: 190, date: "2026-10-07" }], warranty: "Non applicable", insurance: "Assuré", acquired: "2026-09-15", responsible: "Hossein Karimi", alerts: ["replacement_old", "period_unsupported"] }),
    asset({ id: 10, name: "Nacelle ciseaux Genie GS-1932", serial: "GS19-55821", stock: 2, location: "Bg/Chantier Versailles", category: "Engins (immobilisé)", treatment: "fixed", ownership: "rented", owner: "Loxam", repl: { amount: 14500, cur: "EUR", date: "2026-06-01" }, rent: { amount: 550, cur: "EUR", rule: "monthly", interval: 1, start: "2026-07-01", end: "2026-09-30", contract: "CTR-F/2026/002" }, bills: [{ amount: 550, date: "2026-07-31" }, { amount: 550, date: "2026-08-31" }, { amount: 550, date: "2026-09-30" }, { amount: -120, date: "2026-10-05", refund: true }], warranty: "Non applicable", insurance: "Assuré", acquired: "2026-07-01", responsible: "Hossein Karimi", alerts: ["rental_ended"] }),
    asset({ id: 11, name: "Scie à onglets Makita LS1019L", serial: "MK-19L-7731", stock: 2, location: "Bg/Chantier Versailles", category: "Matériel et outillage (immobilisé)", treatment: "fixed", ownership: "owned", fa: { ref: "IMM/2026/0009", state: "draft", orig: 690, dep: 0, date: "2026-08-25" }, warranty: "Sous garantie", insurance: "Assuré", acquired: "2026-08-25", responsible: "Hossein Karimi", alerts: ["asset_draft"] }),
    asset({ id: 12, name: "Aspirateur de chantier Festool CTL 36", serial: "FT-36-20817", stock: 2, location: "Bg/Chantier Versailles", category: "Petit matériel (valorisé en stock)", treatment: "valued", ownership: "borrowed", owner: "Karim Rahimi (associé)", repl: { amount: 650, cur: "EUR", date: "2026-09-10" }, contract: "CTR-F/2026/007 (prêt gratuit)", warranty: "Non applicable", insurance: "Non applicable", acquired: "2026-09-10", responsible: "Hossein Karimi" }),
    consumable({ id: 107, name: "Ciment CEM II 35 kg", stock: 2, location: "Bg/Chantier Versailles", category: "Consommables / Liants", qty: 18, uom: "Sac", unit: 9.8 }),
    consumable({ id: 108, name: "Plaque de plâtre BA13 250×120", stock: 2, location: "Bg/Chantier Versailles", category: "Consommables / Plaques", qty: 24, uom: "Unité", unit: 7.45 }),
    // WH/Chez tiers/SCI Les Tilleuls (lent out)
    asset({ id: 13, name: "Échafaudage de façade Layher 50 m²", serial: "LAY-50-0098", stock: 3, location: "WH/Chez tiers/SCI Les Tilleuls", category: "Échafaudages (immobilisé)", treatment: "fixed", ownership: "lent_out", owner: "L'Art du Bâti", holder: "SCI Les Tilleuls", fa: { ref: "IMM/2025/0018", state: "open", orig: 6800, dep: 1360, date: "2025-04-02" }, contract: "CTR-C/2026/002 (prêt gratuit)", warranty: "Garantie expirée", insurance: "Non assuré", acquired: "2025-04-02", responsible: "Farid Tehrani", alerts: ["lent_uninsured"] }),
    asset({ id: 14, name: "Bétonnière Altrad B190", serial: "ALT-19-3307", stock: 3, location: "WH/Chez tiers/SCI Les Tilleuls", category: "Matériel et outillage (immobilisé)", treatment: "fixed", ownership: "lent_out", owner: "L'Art du Bâti", holder: "SCI Les Tilleuls", fa: { ref: "IMM/2024/0050", state: "open", orig: 1150, dep: 460, date: "2024-09-16" }, contract: "CTR-C/2026/002 (prêt gratuit)", warranty: "Garantie expirée", insurance: "Assuré", acquired: "2024-09-16", responsible: "Farid Tehrani" }),
    // THR/Stock (IRR)
    asset({ id: 15, name: "Perceuse visseuse Bosch GSB 18V-55", serial: "BS-18-66102", stock: 4, location: "THR/Stock", category: "Matériel et outillage (immobilisé)", treatment: "fixed", ownership: "owned", fa: { ref: "IMM/2025/0027", state: "open", orig: 210, dep: 42, date: "2025-11-04" }, warranty: "Sous garantie", insurance: "Assuré", acquired: "2025-11-04", responsible: "Reza Tavakoli" }),
    asset({ id: 16, name: "Groupe électrogène Perkins 20 kVA", serial: "PK-20-11873", stock: 4, location: "THR/Stock", category: "Engins (immobilisé)", treatment: "fixed", ownership: "rented", owner: "Tehran Machinery Co.", repl: { amount: 1450000000, cur: "IRR", date: "2026-08-01" }, rent: { amount: 285000000, cur: "IRR", rule: "quarterly", interval: 1, start: "2026-08-01", end: null, contract: "CTR-F/2026/008" }, bills: [{ amount: 5925.15, date: "2026-08-01" }], warranty: "Non applicable", insurance: "Assuré", acquired: "2026-08-01", responsible: "Reza Tavakoli" }),
    asset({ id: 17, name: "Plaque vibrante Wacker VP1550", serial: "WK-15-40291", stock: 4, location: "THR/Stock", category: "Matériel et outillage (immobilisé)", treatment: "fixed", ownership: "borrowed", owner: "Reza Tavakoli (associé)", repl: { amount: 410000000, cur: "IRR", date: "2026-05-01" }, contract: "CTR-F/2026/001 (prêt gratuit)", warranty: "Non applicable", insurance: "Assuré", acquired: "2026-05-01", responsible: "Reza Tavakoli" }),
    consumable({ id: 109, name: "Ciment Tehran Type 2, 50 kg", stock: 4, location: "THR/Stock", category: "Consommables / Liants", qty: 300, uom: "Sac", unit: 29.9 }),
    consumable({ id: 110, name: "Fer à béton HA12", stock: 4, location: "THR/Stock/Cour", category: "Consommables / Aciers", qty: 2.4, uom: "t", unit: 6392 }),
    // ISF/Dépôt (IRR)
    asset({ id: 18, name: "Bétonnière 350 L", serial: "ISF-BT-0071", stock: 5, location: "ISF/Dépôt", category: "Matériel et outillage (immobilisé)", treatment: "fixed", ownership: "rented", owner: "Isfahan Equip LLC", repl: { amount: 820000000, cur: "IRR", date: "2026-07-15" }, rent: { amount: 120, cur: "USD", rule: "monthly", interval: 1, start: "2026-07-15", end: null, contract: "CTR-F/2026/009" }, bills: [{ amount: 110, date: "2026-08-14" }, { amount: 110, date: "2026-09-14" }], warranty: "Non applicable", insurance: "Assuré", acquired: "2026-07-15", responsible: "Reza Tavakoli", alerts: ["missing_rate"] }),
    asset({ id: 19, name: "Échafaudage tubulaire 30 m²", serial: "ISF-ECH-0013", stock: 5, location: "ISF/Dépôt", category: "Échafaudages (immobilisé)", treatment: "fixed", ownership: "owned", fa: { ref: "IMM/2025/0033", state: "open", orig: 2100, dep: 420, date: "2025-07-01" }, warranty: "Garantie expirée", insurance: "Assuré", acquired: "2025-07-01", responsible: "Reza Tavakoli" }),
    consumable({ id: 111, name: "Plâtre Gach 40 kg", stock: 5, location: "ISF/Dépôt", category: "Consommables / Liants", qty: 150, uom: "Sac", unit: 13.4 }),
    // Outside any monitor stock
    asset({ id: 20, name: "Ponceuse Festool ETS 150/5", serial: "FT-150-99310", stock: 0, location: "WH/Contrôle qualité", category: "Petit matériel (valorisé en stock)", treatment: "valued", ownership: "owned", cost: { amount: 540, cur: "EUR", date: "2026-10-02" }, warranty: "Sous garantie", insurance: "Non applicable", acquired: "2026-10-02", responsible: "Farid Tehrani", alerts: ["outside_stock"] }),
];

// Staff controls, not rows of the monitor (separate counts under the user's own rights).
export const CONTROLS = [
    { code: "to_complete", count: 2, text: "équipements reçus à compléter (hors moniteur, non comptés)" },
    { code: "orphan_serial", count: 1, text: "numéro de série en stock sans équipement (hors moniteur)" },
];
