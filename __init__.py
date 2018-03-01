# This file is part account_bank_statement_rule module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import statement


def register():
    Pool.register(
        statement.StatementLineRule,
        statement.StatementLineRuleLine,
        statement.StatementLine,
        module='account_bank_statement_rule', type_='model')
