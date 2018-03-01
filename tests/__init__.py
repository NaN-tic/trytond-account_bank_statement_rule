# This file is part account_bank_statement_rule module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
try:
    from trytond.modules.account_bank_statement_rule.tests.test_account_bank_statement_rule import suite
except ImportError:
    from .test_account_bank_statement_rule import suite

__all__ = ['suite']
