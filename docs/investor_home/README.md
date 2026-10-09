# Investor home page (OCA web_quick_start_screen)

The investor home page is configuration, not code: a quick start screen of the OCA
module `web_quick_start_screen` (OCA/web 18.0), plus menus hidden from investors with
OCA `base_menu_visibility_restriction` (OCA/server-ux 18.0).
`setup_investor_home.py` creates or updates all of it (usage in its header). Run it once
per database, and again after phase 3 (the Financial button opens the stock monitor
dashboard, lartdubati_investor_home.action_stock_monitor, through the server action
lartdubati_investor_home.action_server_stock_monitor).

## What it sets up
- **Investor Home** screen with 4 buttons (name and description in EN/FR/FA):
  Financial (opens the Stock Monitor dashboard), Administrative, Commerce & Services,
  Production (these three run the server action "Investor Home: coming soon", a
  notification in the user's language; limited to Internal Users, so investors can run it).
- Menus hidden from the group "Stock Monitor Investor" (field "Excluded groups" on the
  menu): Discuss, Dashboards > Dashboards, Dashboards > My Dashboard,
  Dashboards > Configuration.

## Set up an investor user (Settings > Users & Companies > Users)
1. New user, user type Internal User, language.
2. Access Rights tab: tick **Investor > Stock Monitor Investor**; no Inventory,
   Maintenance or other application rights.
3. Stock Access tab: choose a **Stock Access Profile** (no profile = sees nothing).
4. Preferences tab: **Quick start screen** = Investor Home, **Home Action** =
   Quick Start Screen. (Or run `setup_investor_home.py <login>`, which sets both.)

## Change it later (developer mode)
- Buttons: Settings > Technical > User Interface > Screen actions (name, description,
  icon, action, sequence; language code next to a field to translate it).
- Screen: Settings > Technical > User Interface > Quick start screens.
- "Coming soon" text: Settings > Technical > Actions > Server Actions > "Investor Home:
  coming soon" (Python code, texts per language).
- Hidden menus: Settings > Technical > User Interface > Menu Items > menu > Excluded groups.
Then copy the change into `setup_investor_home.py` so production gets it too.
