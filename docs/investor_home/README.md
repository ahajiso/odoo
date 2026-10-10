# Investor home page

Since phase 4 (docs/phase4/) the investor home page is **data of the module
`lartdubati_investor_home`**: the OCA quick start screen « Investor Home », its four
buttons (Financial → stock monitor dashboard; Administrative, Commerce & Services,
Production → « coming soon »), the home window action and the « coming soon » client
action, with their English, French and Persian texts in the module's translations. It is
installed and updated with the module; the former `setup_investor_home.py` is retired.

## Set up an investor user (Settings > Users & Companies > Users)
1. New user, user type Internal User, language.
2. Access Rights tab: tick **Investor > Stock Monitor Investor** and nothing else
   (any other right is refused: an investor account reads only the stock monitor).
3. Stock Access tab: choose a **Stock Access Profile** (without one the user sees no
   stock; the form shows a warning).
The home page is set automatically as the user's home action.

## Change it later
Screens and buttons can only be changed by Settings (developer mode: Settings >
Technical > User Interface > Quick start screens / Screen actions); a module update
puts the module's version back. For an investor account, each button opens only its own
action (docs/phase4/PLAN.md §2, P4-2d): change the module, not the data.
