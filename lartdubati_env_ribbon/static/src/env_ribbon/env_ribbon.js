/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { session } from "@web/session";

// Suffixes de base de données considérés comme "hors production".
// Toute base dont le nom se termine par l'un de ces suffixes affichera
// le bandeau (ex: artdubati_test, artdubati_staging).
const TEST_DB_SUFFIXES = ["_test", "_staging", "_dev"];

export class EnvRibbon extends Component {
    static template = "lartdubati_env_ribbon.EnvRibbon";
    static props = {};

    get dbName() {
        return (session && session.db) || "";
    }

    get isTestDb() {
        const name = this.dbName.toLowerCase();
        return TEST_DB_SUFFIXES.some((suffix) => name.endsWith(suffix));
    }
}

registry.category("main_components").add("EnvRibbon", {
    Component: EnvRibbon,
});
