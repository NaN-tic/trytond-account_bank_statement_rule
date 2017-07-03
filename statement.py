# This file is part account_bank_statement_rule module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from decimal import Decimal
from trytond.pool import Pool, PoolMeta
from trytond.model import ModelView, ModelSQL, MatchMixin, fields
from trytond.transaction import Transaction
from trytond.pyson import If, Eval, Bool
from simpleeval import simple_eval
from trytond.tools import decistmt

__all__ = ['StatementLineRule', 'StatementLine', 'StatementLineRuleLine']


class StatementLineRule(ModelSQL, ModelView, MatchMixin):
    'Statement Line Rule'
    __name__ = 'account.bank.statement.line.rule'
    name = fields.Char('Name')
    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        select=True)
    journal = fields.Many2One('account.bank.statement.journal', 'Journal',
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    description = fields.Char('Description')
    minimum_amount = fields.Numeric('Minimum Amount',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    maximum_amount = fields.Numeric('Maximum Amount',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    currency = fields.Many2One('currency.currency', 'Currency')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    sequence = fields.Integer('Sequence')
    lines = fields.One2Many('account.bank.statement.line.rule.line',
        'rule', 'Lines')

    @classmethod
    def __setup__(cls):
        super(StatementLineRule, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')

        company = Transaction().context.get('company')
        if company:
            return Company(company).currency.id

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')

        company = Transaction().context.get('company')
        if company:
            return Company(company).currency.digits
        return 2

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2


class StatementLineRuleLine(ModelSQL, ModelView):
    'Statement Line Rule Line'
    __name__ = 'account.bank.statement.line.rule.line'
    _rec_name = 'rule'
    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        select=True)
    rule = fields.Many2One('account.bank.statement.line.rule', 'Rule',
        ondelete='CASCADE', select=True, required=True)
    amount = fields.Char('Amount',required=True,
        help=('Numeric value or a Python expression that will be evaluated with:\n'
            '- total_amount: the total amount of the line\n'
            '- pending_amount: the pending amount of all line\n'))
    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[
            ('company', '=', Eval('company', 0)),
            ('kind', '!=', 'view'),
            ],
        depends=['company'])
    party = fields.Many2One('party.party', 'Party',
        states={
            'required': Bool(Eval('party_required')),
            },
        depends=['party_required'])
    party_required = fields.Function(fields.Boolean('Party Required'),
        'on_change_with_party_required')
    description = fields.Char('Description')
    sequence = fields.Integer('Sequence')

    @classmethod
    def __setup__(cls):
        super(StatementLineRuleLine, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('account')
    def on_change_with_party_required(self, name=None):
        if self.account and self.account.party_required:
            return True
        return False


class StatementLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.bank.statement.line'

    def _get_rule_pattern(self):
        pattern = {}
        pattern.setdefault('company', self.company.id)
        pattern.setdefault('currency', self.statement_currency.id)
        if self.journal:
            pattern.setdefault('journal', self.journal.id)
        return pattern

    def get_move_line_from_rline(self, rline, amount):
        MoveLine = Pool().get('account.bank.statement.move.line')

        mline = MoveLine()
        mline.line = self
        mline.date = self.date.date()
        mline.amount = amount
        mline.party = rline.party
        mline.account = rline.account
        mline.description = rline.description
        return mline

    @classmethod
    def search_lines_by_rules(cls, st_lines):
        pool = Pool()
        Rule = pool.get('account.bank.statement.line.rule')
        BSMoveLine = pool.get('account.bank.statement.move.line')

        to_create = []
        for line in st_lines:
            if line.reconciled:
                continue
            pattern = line._get_rule_pattern()

            for rule in Rule.search([]):
                if rule.match(pattern):
                    if (rule.minimum_amount and not (
                            rule.minimum_amount <= line.amount)):
                        continue
                    if (rule.maximum_amount and not (
                            rule.maximum_amount >= line.amount)):
                        continue
                    if (rule.description and not (
                                rule.description in line.description)):
                        continue

                    # TODO convert amount currency to company_amount currency

                    context = {}
                    context.setdefault('names', {})['total_amount'] = str(line.amount)
                    context.setdefault('functions', {})['Decimal'] = Decimal
                    pending_amount = line.amount
                    for rline in rule.lines:
                        context['names']['pending_amount'] = str(pending_amount)

                        amount = simple_eval(decistmt(str(rline.amount)),
                            **context)
                        amount = Decimal(amount) if amount else Decimal('0.0')
                        pending_amount -= amount
                        mline = line.get_move_line_from_rline(rline, amount)
                        to_create.append(mline._save_values)
                    break

        if to_create:
            BSMoveLine.create(to_create)

    @classmethod
    def search_reconcile(cls, st_lines):
        super(StatementLine, cls).search_reconcile(st_lines)
        cls.search_lines_by_rules(st_lines)
