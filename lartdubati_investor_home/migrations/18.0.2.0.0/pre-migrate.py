"""Phase 3: the conversion modes « Rate on Entry Date » and « No Conversion » are
replaced (P9): entry_date -> historical, none -> latest. Done before the selection is
updated, so that no company is left with a removed value."""


def migrate(cr, version):
    cr.execute("""
        UPDATE res_company
           SET stock_monitor_currency_mode = CASE stock_monitor_currency_mode
                   WHEN 'entry_date' THEN 'historical' WHEN 'none' THEN 'latest' END
         WHERE stock_monitor_currency_mode IN ('entry_date', 'none')
    """)
