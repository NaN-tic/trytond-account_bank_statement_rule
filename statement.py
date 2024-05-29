# This file is part account_bank_statement_rule module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from decimal import Decimal
from trytond.pool import Pool, PoolMeta
from trytond.model import (ModelView, ModelSQL, MatchMixin, sequence_ordered,
    fields)
from trytond.transaction import Transaction
from trytond.pyson import If, Eval, Bool
from simpleeval import simple_eval
from trytond.tools import decistmt
from trytond.modules.currency.fields import Monetary

__all__ = ['StatementLineRule', 'StatementLine', 'StatementLineRuleLine']


class StatementLineRule(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    'Statement Line Rule'
    __name__ = 'account.bank.statement.line.rule'
    name = fields.Char('Name')
    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])
    journal = fields.Many2One('account.bank.statement.journal', 'Journal',
        domain=[
            ('company', '=', Eval('company', -1)),
            ])
    description = fields.Char('Description')
    minimum_amount = Monetary('Minimum Amount',
        digits='currency', currency='currency')
    maximum_amount = Monetary('Maximum Amount',
        digits='currency', currency='currency')
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    lines = fields.One2Many('account.bank.statement.line.rule.line',
        'rule', 'Lines')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')

        company = Transaction().context.get('company')
        if company:
            return Company(company).currency.id


class StatementLineRuleLine(sequence_ordered(), ModelSQL, ModelView):
    'Statement Line Rule Line'
    __name__ = 'account.bank.statement.line.rule.line'
    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])
    rule = fields.Many2One('account.bank.statement.line.rule', 'Rule',
        ondelete='CASCADE', required=True)
    amount = fields.Char('Amount', required=True,
        help=('Numeric value or a Python expression '
            'that will be evaluated with:\n'
            '- total_amount: the total amount of the line\n'
            '- pending_amount: the pending amount of all line\n'))
    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[
            ('company', '=', Eval('company', 0)),
            ('type', '!=', None),
            ])
    party = fields.Many2One('party.party', 'Party',
        states={
            'required': Bool(Eval('party_required')),
            },
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    party_required = fields.Function(fields.Boolean('Party Required'),
        'on_change_with_party_required')
    description = fields.Char('Description')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('account')
    def on_change_with_party_required(self, name=None):
        if self.account and self.account.party_required:
            return True
        return False


class StatementLine(metaclass=PoolMeta):
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
                    if (rule.minimum_amount is not None and not (
                            rule.minimum_amount <= line.amount)):
                        continue
                    if (rule.maximum_amount is not None and not (
                            rule.maximum_amount >= line.amount)):
                        continue
                    if (rule.description and not (
                                rule.description in line.description)):
                        continue

                    # TODO convert amount currency to company_amount currency

                    context = {}
                    context.setdefault('names', {})['total_amount'] = (
                        str(line.amount))
                    context.setdefault('functions', {})['Decimal'] = Decimal
                    pending_amount = line.amount
                    for rline in rule.lines:
                        context['names']['pending_amount'] = (
                            str(pending_amount))

                        amount = simple_eval(decistmt(str(rline.amount)),
                            **context)
                        amount = Decimal(amount) if amount else Decimal(0)
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
