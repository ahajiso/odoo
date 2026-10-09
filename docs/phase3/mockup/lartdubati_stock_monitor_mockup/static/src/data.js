/** @odoo-module **/
// Demo data of the mock-up only. The real dashboard reads lartdubati.stock.monitor
// through the ORM. Amounts are given in their source currency; the dashboard converts
// them into the stock's currency with RATES (EUR = company currency).

export const TODAY = "2026-10-09";
export const COMPANY_CURRENCY = "EUR";
// Units of currency per 1 EUR, with the date of the rate. USD has no rate on purpose.
export const RATES = {
    EUR: { rate: 1, date: TODAY },
    IRR: { rate: 48500, date: "2026-10-08" },
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

const asset = (vals) => ({ family: "asset", qty: 1, uom: "Unité", ...vals });
const consumable = (vals) => ({ family: "consumable", ownership: "owned", ...vals });

export const ITEMS = [
    // Bg/Stock
    asset({ id: 1, name: "Scie sur table Bosch GTS 10 XC", serial: "1234", stock: 1, location: "Bg/Stock", category: "Matériel et outillage (immobilisé)", ownership: "owned", values: { cur: "EUR", orig: 1290, dep: 64.5 }, asset: "IMM/2026/0012", warranty: "Sous garantie", insurance: "Assuré", acquired: "2026-10-09" }),
    asset({ id: 2, name: "Perforateur Hilti TE 30-A36", serial: "H30-88412", stock: 1, location: "Bg/Stock/Étagère A", category: "Matériel et outillage (immobilisé)", ownership: "owned", values: { cur: "EUR", orig: 980, dep: 310 }, asset: "IMM/2024/0031", warranty: "Garantie expirée", insurance: "Assuré", acquired: "2024-03-12" }),
    asset({ id: 3, name: "Laser rotatif Leica Rugby 640", serial: "LR-20931", stock: 1, location: "Bg/Stock/Étagère A", category: "Matériel et outillage (immobilisé)", ownership: "owned", values: { cur: "EUR", orig: 1850, dep: 555 }, asset: "IMM/2024/0044", warranty: "Garantie expirée", insurance: "Assuré", acquired: "2024-06-03" }),
    asset({ id: 4, name: "Compresseur Atlas Copco C55", serial: "AC-77120", stock: 1, location: "Bg/Stock", category: "Matériel et outillage (immobilisé)", ownership: "borrowed", owner: "Karim Rahimi (associé)", repl: { amount: 2400, cur: "EUR", date: "2026-03-15" }, contract: "CTR-F/2026/003 (prêt gratuit)", warranty: "Non applicable", insurance: "Assuré", acquired: "2026-03-15" }),
    asset({ id: 5, name: "Bétonnière Altrad B160", serial: "ALT-55102", stock: 1, location: "Bg/Stock", category: "Matériel et outillage (immobilisé)", ownership: "borrowed", owner: "SARL Batinord", contract: "CTR-F/2026/005 (prêt gratuit)", warranty: "Non applicable", insurance: "Non assuré", acquired: "2026-09-28", alerts: ["no_replacement"] }),
    asset({ id: 6, name: "Mini-pelle Kubota U17-3", serial: "KU17-30882", stock: 1, location: "Bg/Stock", category: "Engins (immobilisé)", ownership: "rented", owner: "Kiloutou", repl: { amount: 32000, cur: "EUR", date: "2026-09-02" }, rent: { amount: 1450, cur: "EUR", period: "month", start: "2026-09-01", end: null, contract: "CTR-F/2026/004" }, rentPaid: { amount: 1450, cur: "EUR" }, warranty: "Non applicable", insurance: "Assuré", acquired: "2026-09-01" }),
    asset({ id: 7, name: "Camion benne Renault Master", serial: "FX-482-KL", stock: 1, location: "Bg/Stock (équipement hors stock)", nonStock: true, category: "Véhicules (immobilisé)", ownership: "owned", values: { cur: "EUR", orig: 38500, dep: 12833 }, asset: "IMM/2025/0002", warranty: "Sous garantie", insurance: "Assuré", acquired: "2025-01-20" }),
    asset({ id: 8, name: "Groupe électrogène SDMO Perform 6000", serial: "SD-60-1189", stock: 1, location: "Bg/Stock/Étagère B", category: "Petit matériel (non immobilisé)", ownership: "owned", values: { cur: "EUR", orig: 720, dep: 0 }, warranty: "Sous garantie", insurance: "Non applicable", acquired: "2026-05-11", noAsset: true }),
    consumable({ id: 101, name: "Ciment CEM II 35 kg", stock: 1, location: "Bg/Stock", category: "Consommables / Liants", qty: 42, uom: "Sac", unit: { cur: "EUR", cost: 9.8 } }),
    consumable({ id: 102, name: "Plaque de plâtre BA13 250×120", stock: 1, location: "Bg/Stock/Étagère C", category: "Consommables / Plaques", qty: 68, uom: "Unité", unit: { cur: "EUR", cost: 7.45 } }),
    consumable({ id: 103, name: "Vis placo 3,5×25 (boîte de 1000)", stock: 1, location: "Bg/Stock/Étagère C", category: "Consommables / Fixations", qty: 15, uom: "Boîte", unit: { cur: "EUR", cost: 18.9 } }),
    consumable({ id: 104, name: "Rail R48 3 m", stock: 1, location: "Bg/Stock/Étagère C", category: "Consommables / Ossature", qty: 120, uom: "Unité", unit: { cur: "EUR", cost: 3.1 } }),
    consumable({ id: 105, name: "Mortier colle C2", stock: 1, location: "Bg/Stock", category: "Consommables / Liants", qty: 20, uom: "Sac", unit: { cur: "EUR", cost: 14.2 } }),
    consumable({ id: 106, name: "Sable 0/4", stock: 1, location: "Bg/Stock/Aire extérieure", category: "Consommables / Granulats", qty: 6.5, uom: "t", unit: { cur: "EUR", cost: 38 } }),
    // Bg/Chantier Versailles
    asset({ id: 9, name: "Échafaudage roulant Altrad 8 m", serial: "ECH-8M-0412", stock: 2, location: "Bg/Chantier Versailles", category: "Échafaudages (immobilisé)", ownership: "rented", owner: "Loxam", repl: { amount: 4200, cur: "EUR", date: "2025-06-20" }, rent: { amount: 95, cur: "EUR", period: "week", start: "2026-09-15", end: null, contract: "CTR-F/2026/006" }, rentPaid: { amount: 380, cur: "EUR" }, warranty: "Non applicable", insurance: "Assuré", acquired: "2026-09-15", alerts: ["replacement_old"] }),
    asset({ id: 10, name: "Nacelle ciseaux Genie GS-1932", serial: "GS19-55821", stock: 2, location: "Bg/Chantier Versailles", category: "Engins (immobilisé)", ownership: "rented", owner: "Loxam", repl: { amount: 14500, cur: "EUR", date: "2026-06-01" }, rent: { amount: 550, cur: "EUR", period: "month", start: "2026-07-01", end: "2026-09-30", contract: "CTR-F/2026/002" }, rentPaid: { amount: 1650, cur: "EUR" }, warranty: "Non applicable", insurance: "Assuré", acquired: "2026-07-01", alerts: ["rental_ended"] }),
    asset({ id: 11, name: "Scie à onglets Makita LS1019L", serial: "MK-19L-7731", stock: 2, location: "Bg/Chantier Versailles", category: "Matériel et outillage (immobilisé)", ownership: "owned", values: { cur: "EUR", orig: 690, dep: 23 }, asset: "IMM/2026/0009", warranty: "Sous garantie", insurance: "Assuré", acquired: "2026-08-25" }),
    asset({ id: 12, name: "Aspirateur de chantier Festool CTL 36", serial: "FT-36-20817", stock: 2, location: "Bg/Chantier Versailles", category: "Petit matériel (non immobilisé)", ownership: "borrowed", owner: "Karim Rahimi (associé)", repl: { amount: 650, cur: "EUR", date: "2026-09-10" }, contract: "CTR-F/2026/007 (prêt gratuit)", warranty: "Non applicable", insurance: "Non applicable", acquired: "2026-09-10" }),
    consumable({ id: 107, name: "Ciment CEM II 35 kg", stock: 2, location: "Bg/Chantier Versailles", category: "Consommables / Liants", qty: 18, uom: "Sac", unit: { cur: "EUR", cost: 9.8 } }),
    consumable({ id: 108, name: "Plaque de plâtre BA13 250×120", stock: 2, location: "Bg/Chantier Versailles", category: "Consommables / Plaques", qty: 24, uom: "Unité", unit: { cur: "EUR", cost: 7.45 } }),
    // WH/Chez tiers/SCI Les Tilleuls (lent out)
    asset({ id: 13, name: "Échafaudage de façade Layher 50 m²", serial: "LAY-50-0098", stock: 3, location: "WH/Chez tiers/SCI Les Tilleuls", category: "Échafaudages (immobilisé)", ownership: "lent_out", owner: "L'Art du Bâti", holder: "SCI Les Tilleuls", values: { cur: "EUR", orig: 6800, dep: 1360 }, asset: "IMM/2025/0018", contract: "CTR-C/2026/002 (prêt gratuit)", warranty: "Garantie expirée", insurance: "Non assuré", acquired: "2025-04-02", alerts: ["lent_uninsured"] }),
    asset({ id: 14, name: "Bétonnière Altrad B190", serial: "ALT-19-3307", stock: 3, location: "WH/Chez tiers/SCI Les Tilleuls", category: "Matériel et outillage (immobilisé)", ownership: "lent_out", owner: "L'Art du Bâti", holder: "SCI Les Tilleuls", values: { cur: "EUR", orig: 1150, dep: 460 }, asset: "IMM/2024/0050", contract: "CTR-C/2026/002 (prêt gratuit)", warranty: "Garantie expirée", insurance: "Assuré", acquired: "2024-09-16" }),
    // THR/Stock (IRR)
    asset({ id: 15, name: "Perceuse visseuse Bosch GSB 18V-55", serial: "BS-18-66102", stock: 4, location: "THR/Stock", category: "Matériel et outillage (immobilisé)", ownership: "owned", values: { cur: "EUR", orig: 210, dep: 42 }, asset: "IMM/2025/0027", warranty: "Sous garantie", insurance: "Assuré", acquired: "2025-11-04" }),
    asset({ id: 16, name: "Groupe électrogène Perkins 20 kVA", serial: "PK-20-11873", stock: 4, location: "THR/Stock", category: "Engins (immobilisé)", ownership: "rented", owner: "Tehran Machinery Co.", repl: { amount: 1450000000, cur: "IRR", date: "2026-08-01" }, rent: { amount: 95000000, cur: "IRR", period: "month", start: "2026-08-01", end: null, contract: "CTR-F/2026/008" }, rentPaid: { amount: 3917.53, cur: "EUR" }, warranty: "Non applicable", insurance: "Assuré", acquired: "2026-08-01" }),
    asset({ id: 17, name: "Plaque vibrante Wacker VP1550", serial: "WK-15-40291", stock: 4, location: "THR/Stock", category: "Matériel et outillage (immobilisé)", ownership: "borrowed", owner: "Reza Tavakoli (associé)", repl: { amount: 410000000, cur: "IRR", date: "2026-05-01" }, contract: "CTR-F/2026/001 (prêt gratuit)", warranty: "Non applicable", insurance: "Assuré", acquired: "2026-05-01" }),
    consumable({ id: 109, name: "Ciment Tehran Type 2, 50 kg", stock: 4, location: "THR/Stock", category: "Consommables / Liants", qty: 300, uom: "Sac", unit: { cur: "EUR", cost: 29.9 } }),
    consumable({ id: 110, name: "Fer à béton HA12", stock: 4, location: "THR/Stock/Cour", category: "Consommables / Aciers", qty: 2.4, uom: "t", unit: { cur: "EUR", cost: 6392 } }),
    // ISF/Dépôt (IRR)
    asset({ id: 18, name: "Bétonnière 350 L", serial: "ISF-BT-0071", stock: 5, location: "ISF/Dépôt", category: "Matériel et outillage (immobilisé)", ownership: "rented", owner: "Isfahan Equip LLC", repl: { amount: 820000000, cur: "IRR", date: "2026-07-15" }, rent: { amount: 120, cur: "USD", period: "month", start: "2026-07-15", end: null, contract: "CTR-F/2026/009" }, rentPaid: { amount: 220, cur: "EUR" }, warranty: "Non applicable", insurance: "Assuré", acquired: "2026-07-15", alerts: ["missing_rate"] }),
    asset({ id: 19, name: "Échafaudage tubulaire 30 m²", serial: "ISF-ECH-0013", stock: 5, location: "ISF/Dépôt", category: "Échafaudages (immobilisé)", ownership: "owned", values: { cur: "EUR", orig: 2100, dep: 420 }, asset: "IMM/2025/0033", warranty: "Garantie expirée", insurance: "Assuré", acquired: "2025-07-01" }),
    consumable({ id: 111, name: "Plâtre Gach 40 kg", stock: 5, location: "ISF/Dépôt", category: "Consommables / Liants", qty: 150, uom: "Sac", unit: { cur: "EUR", cost: 13.4 } }),
    // Outside any monitor stock
    asset({ id: 20, name: "Ponceuse Festool ETS 150/5", serial: "FT-150-99310", stock: 0, location: "WH/Contrôle qualité", category: "Petit matériel (non immobilisé)", ownership: "owned", values: { cur: "EUR", orig: 540, dep: 0 }, warranty: "Sous garantie", insurance: "Non applicable", acquired: "2026-10-02", noAsset: true, alerts: ["outside_stock"] }),
];

// Alerts not attached to a row of the monitor.
export const GLOBAL_ALERTS = [
    { code: "to_complete", count: 2, text: "2 équipements reçus à compléter (non intégrés, absents du moniteur)" },
];
