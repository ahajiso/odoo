"""Configure the investor home page (OCA web_quick_start_screen) and hide the menus
investors do not need (OCA base_menu_visibility_restriction). Safe to run again: it
updates what exists. Run once per database (artdubati_test, then production), and
again after the Stock Monitor report is rebuilt (its action changes).

Usage (credentials from the environment, never stored):
    ODOO_URL=https://erp.lartdubati.com ODOO_DB=artdubati_test \
    ODOO_LOGIN=... ODOO_PASSWORD=... python3 setup_investor_home.py [investor_login ...]
Given logins get the home page as their start screen and home action.
The user running it needs Settings and Access Rights rights.
"""
import http.cookiejar
import json
import os
import sys
import urllib.request

URL, DB = os.environ["ODOO_URL"], os.environ["ODOO_DB"]
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
)


def post(path, params):
    req = urllib.request.Request(
        URL + path,
        json.dumps({"jsonrpc": "2.0", "params": params}).encode(),
        {"Content-Type": "application/json"},
    )
    res = json.load(opener.open(req, timeout=120))
    if "error" in res:
        raise RuntimeError(res["error"]["data"]["message"])
    return res.get("result")


def call(model, method, *args, **kwargs):
    return post(
        "/web/dataset/call_kw",
        {"model": model, "method": method, "args": list(args), "kwargs": kwargs},
    )


def ref(xmlid):
    module, name = xmlid.split(".")
    return call("ir.model.data", "check_object_reference", module, name)[1]


def upsert(model, name, vals, key="name"):
    ids = call(model, "search", [(key, "=", name)], context={"lang": "en_US"})
    if ids:
        call(model, "write", ids[:1], vals, context={"lang": "en_US"})
        return ids[0]
    return call(model, "create", dict(vals, **{key: name}), context={"lang": "en_US"})


def translate(model, rec_id, values):
    """values: {lang: {field: text}}; en_US is the source text. Html fields are
    translated term by term (update_field_translations), others by a write."""
    source = values["en_US"]
    call(model, "write", [rec_id], source, context={"lang": "en_US"})
    for lang, vals in values.items():
        if lang == "en_US":
            continue
        for field, text in vals.items():
            if text.startswith("<p>"):
                call(model, "update_field_translations", [rec_id], field,
                     {lang: {source[field][3:-4]: text[3:-4]}})
            else:
                call(model, "write", [rec_id], {field: text}, context={"lang": lang})


post(
    "/web/session/authenticate",
    {"db": DB, "login": os.environ["ODOO_LOGIN"], "password": os.environ["ODOO_PASSWORD"]},
)

# "Coming soon" message, in the user's language.
coming_soon = upsert(
    "ir.actions.server",
    "Investor Home: coming soon",
    {
        "model_id": ref("base.model_res_users"),
        # With a group, Odoo checks the group instead of write access on the model
        # (investors cannot write users).
        "groups_id": [(6, 0, [ref("base.group_user")])],
        "state": "code",
        "code": (
            "texts = {\n"
            "    'fr': ('Bientôt disponible', \"Cette fonction n'est pas encore disponible.\"),\n"
            "    'fa': ('به‌زودی', 'این بخش هنوز در دسترس نیست.'),\n"
            "}\n"
            "title, message = texts.get((env.user.lang or 'en')[:2],"
            " ('Coming soon', 'This function is not available yet.'))\n"
            "action = {'type': 'ir.actions.client', 'tag': 'display_notification',"
            " 'params': {'title': title, 'message': message, 'type': 'info'}}\n"
        ),
    },
)

# The Stock Monitor action is created by bi_sql_editor (changes when rebuilt).
monitor = call("bi.sql.view", "search_read", [("technical_name", "=", "stock_monitor")], ["action_id"])
monitor_action = monitor[0]["action_id"][0]

BUTTONS = [
    # (sequence, en name, icon, action, {lang: (name, description)})
    (10, "Financial", "fa-line-chart", f"ir.actions.act_window,{monitor_action}", {
        "en_US": ("Financial", "Stock monitor: quantities and values per stock."),
        "fr_FR": ("Financier", "Suivi des stocks : quantités et valeurs par stock."),
        "fa_IR": ("مالی", "پایش انبار: مقادیر و ارزش‌ها برای هر انبار."),
    }),
    (20, "Administrative", "fa-building", f"ir.actions.server,{coming_soon}", {
        "en_US": ("Administrative", "Coming soon."),
        "fr_FR": ("Administratif", "Bientôt disponible."),
        "fa_IR": ("اداری", "به‌زودی."),
    }),
    (30, "Commerce & Services", "fa-shopping-cart", f"ir.actions.server,{coming_soon}", {
        "en_US": ("Commerce & Services", "Coming soon."),
        "fr_FR": ("Commerce et services", "Bientôt disponible."),
        "fa_IR": ("بازرگانی و خدمات", "به‌زودی."),
    }),
    (40, "Production", "fa-cogs", f"ir.actions.server,{coming_soon}", {
        "en_US": ("Production", "Coming soon."),
        "fr_FR": ("Production", "Bientôt disponible."),
        "fa_IR": ("تولید", "به‌زودی."),
    }),
]
button_ids = []
for sequence, name, icon, action, texts in BUTTONS:
    bid = upsert("quick.start.screen.action", name,
                 {"sequence": sequence, "icon_name": icon, "action_ref_id": action})
    translate("quick.start.screen.action", bid,
              {lang: {"name": n, "description": f"<p>{d}</p>"} for lang, (n, d) in texts.items()})
    button_ids.append(bid)

screen = upsert("quick.start.screen", "Investor Home", {"action_ids": [(6, 0, button_ids)]})
translate("quick.start.screen", screen, {
    "en_US": {"name": "Investor Home"},
    "fr_FR": {"name": "Accueil investisseur"},
    "fa_IR": {"name": "خانه سرمایه‌گذار"},
})

# Menus investors do not need.
investor_group = ref("lartdubati_investor_home.group_stock_investor")
for xmlid in (
    "mail.menu_root_discuss",
    "spreadsheet_dashboard.spreadsheet_dashboard_menu_dashboard",
    "board.menu_board_my_dash",
    "spreadsheet_dashboard.spreadsheet_dashboard_menu_configuration",
):
    call("ir.ui.menu", "write", [ref(xmlid)], {"excluded_group_ids": [(4, investor_group)]})

# Investor users given on the command line.
home_action = ref("web_quick_start_screen.start_screen_action")
for login in sys.argv[1:]:
    users = call("res.users", "search", [("login", "=", login)])
    call("res.users", "write", users, {"quick_start_screen_id": screen, "action_id": home_action})
print("Investor Home ready; buttons", button_ids, "; users:", sys.argv[1:] or "none")
