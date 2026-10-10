// « Coming soon » buttons of the investor home page (docs/phase4/PLAN.md §3, P4-0): a
// client action, so that an investor account needs no server action (P4-2d).
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

function comingSoon(env) {
    env.services.notification.add(_t("This function is not available yet."), {
        title: _t("Coming soon"),
        type: "info",
    });
}

registry.category("actions").add("lartdubati_coming_soon", comingSoon);
