"""Compare the recorded 122-module server platform with the local integration run.

Run from any directory: python docs/one_off_rental/check_parity.py.
The historical file report is reusable only for its identical image and hash pairs.
This checks source parity, not Python packages or a copy of server business data.
"""
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
HISTORICAL = HERE.parent / 'phase4' / 'parity'
UPDATED = {'maintenance_shareholder_equipment', 'lartdubati_investor_home', 'lartdubati_manual'}
COSMETIC = {'account', 'barcodes', 'base', 'board', 'mail', 'payment', 'product', 'sale_management', 'web'}


def records(path, prefix='MODULE'):
    rows = [line.split() for line in path.read_text().splitlines() if line.startswith(prefix + ' ')]
    result = {row[1]: tuple(row[2:4]) for row in rows}
    assert len(result) == len(rows), f'Duplicate module in {path}'
    return result


expected = HERE / 'platform_expected.txt'
server = records(expected)
after = records(expected, 'AFTER')
local = records(HERE / 'platform-local.txt')
old_server = records(HISTORICAL / 'platform_server_20261010.txt')
old_local = records(HISTORICAL / 'platform_local.txt')
assert len(server) == 122 and server.keys() == local.keys(), 'Installed module set differs'
assert after.keys() == UPDATED, 'Unexpected update scope'
report = (HISTORICAL / 'odoo_files_report_20261010.txt').read_text()
for key in ('IMAGE_ID', 'ODOO_VERSION'):
    value = re.search(rf'^{key}=(.+)$', expected.read_text(), re.M)[1]
    assert value in report.splitlines()[0], f'{key} differs from file comparison'
assert 'different_other=0 ' in report and 'only_on_server=0' in report
missing = report.split('## missing_on_server (14)\n')[1].split('## ')[0].strip().splitlines()
assert len(missing) == 14 and all(re.fullmatch(
    r'web/static/fonts/google/[^/]+/([^/]+\.ttf|LICENSE\.txt)', name) for name in missing)
for name in server:
    if name in UPDATED:
        assert local[name] == after[name], f'Proposed code differs: {name}'
    elif name in COSMETIC:
        assert server[name] == old_server[name], f'Server proof expired: {name}'
        assert local[name] == old_local[name], f'Local proof expired: {name}'
    else:
        assert local[name] == server[name], f'Unexplained version/code difference: {name}'
print('SOURCE PARITY OK: 122 modules; 3 proposed updates; 9 documented image/font exceptions.')
print('Python packages and server business data are not reproduced by this check.')
