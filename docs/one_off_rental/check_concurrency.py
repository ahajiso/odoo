"""Run with Odoo shell on the LOCAL fixture DB only, after preparing an unbilled
TEST one-off line and setting ONE_OFF_CONCURRENCY_LINE_ID to its id. This creates
one draft bill and commits it. Never run on a remote business database.

The two connections must establish their snapshots before the first bill commits.
The stale transaction must fail serialization, then retry in a fresh transaction.
"""
import os

import psycopg2

from odoo import SUPERUSER_ID, api, sql_db

assert env.cr.dbname == "artdubati_test_oneoff_local"  # noqa: F821
line = env["contract.line"].browse(int(os.environ["ONE_OFF_CONCURRENCY_LINE_ID"]))  # noqa: F821
line.ensure_one()
assert line.equipment_billing_mode == "one_off"
assert line.equipment_id.name.startswith("TEST")
assert not line._equipment_one_off_bills()
line_id = line.id
context = {"allowed_company_ids": [line.contract_id.company_id.id]}
database = env.cr.dbname  # noqa: F821
env.cr.commit()  # noqa: F821
connection = sql_db.db_connect(database)
cr1, cr2 = connection.cursor(), connection.cursor()
try:
    env1 = api.Environment(cr1, SUPERUSER_ID, context)
    env2 = api.Environment(cr2, SUPERUSER_ID, context)
    first = env1["contract.line"].browse(line_id)
    second = env2["contract.line"].browse(line_id)
    assert not first._equipment_one_off_bills()
    assert not second._equipment_one_off_bills()
    bill_id = first._create_equipment_one_off_bill().id
    cr1.commit()
    try:
        second._create_equipment_one_off_bill()
    except psycopg2.errors.SerializationFailure:
        cr2.rollback()
    else:
        raise AssertionError("A stale snapshot must retry, never create a duplicate")
finally:
    cr1.close()
    cr2.close()

with connection.cursor() as cr3:
    fresh = api.Environment(cr3, SUPERUSER_ID, context)["contract.line"].browse(line_id)
    assert fresh._create_equipment_one_off_bill().id == bill_id
    assert len(fresh._equipment_one_off_bills()) == 1
    cr3.commit()
print("ONE-OFF CONCURRENCY OK: serialization retry reused one draft bill")
