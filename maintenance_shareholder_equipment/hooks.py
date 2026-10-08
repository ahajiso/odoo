import logging

_logger = logging.getLogger(__name__)

RENT_ACCOUNT_CODE = "613500"  # test choice, question C10 of docs/QUESTIONS_COMPTABLE.md


def set_default_rent_account(env):
    """Give each company its equipment rental expense account when it has none:
    the account whose code is 613500 (looked up, never hard-coded by id)."""
    for company in env["res.company"].search([("equipment_rent_account_id", "=", False)]):
        account = env["account.account"].with_company(company).search(
            [("code", "=", RENT_ACCOUNT_CODE), ("company_ids", "in", company.id)], limit=1
        )
        if account:
            company.equipment_rent_account_id = account
            _logger.info("Company %s: equipment rental account set to %s %s",
                         company.name, account.code, account.name)
        else:
            _logger.warning("Company %s: no account %s, equipment rental account left empty",
                            company.name, RENT_ACCOUNT_CODE)


def post_init_hook(env):
    set_default_rent_account(env)
