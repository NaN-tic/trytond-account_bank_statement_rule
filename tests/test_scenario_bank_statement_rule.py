from trytond.modules.account_invoice.tests.tools import set_fiscalyear_invoice_sequences
from trytond.modules.account.tests.tools import create_fiscalyear, create_chart, get_accounts
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.tools import activate_modules
from proteus import Model
from decimal import Decimal
import datetime
import unittest
from trytond.tests.test_tryton import drop_db

class Test(unittest.TestCase):
    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        now = datetime.datetime.now()

        # Install account_bank_statement_rule
        config = activate_modules('account_bank_statement_rule')

        # Create company
        _ = create_company()
        company = get_company()
        company.save()

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        payable = accounts['payable']
        revenue = accounts['revenue']
        cash = accounts['cash']
        cash.bank_reconcile = True
        cash.save()

        # Create party
        Party = Model.get('party.party')
        party = Party(name='Party')
        party.save()

        # Create Journal
        AccountJournal = Model.get('account.journal')
        account_journal = AccountJournal(name='Statement', type='cash')
        account_journal.save()

        # Create Statement Journal
        StatementJournal = Model.get('account.bank.statement.journal')
        statement_journal = StatementJournal(name='Test',
            journal=account_journal, currency=company.currency, account=cash)
        statement_journal.save()

        # Create Rules
        Rule = Model.get('account.bank.statement.line.rule')
        RuleLine = Model.get('account.bank.statement.line.rule.line')
        rule1 = Rule()
        rule1.name = 'Rule 1'
        rule1.description = 'Apply Rule 1'
        rule1.minimum_amount = Decimal('40')
        rule1.sequence = 1
        rline1 = RuleLine()
        rule1.lines.append(rline1)
        rline1.amount = '5'
        rline1.description = 'Rule Line 1'
        rline1.account = payable
        rline1.party = party
        rline1.sequence = 1
        rline2 = RuleLine()
        rule1.lines.append(rline2)
        rline2.amount = 'pending_amount'
        rline2.description = 'Rule Line 2'
        rline2.account = revenue
        rline2.sequence = 2
        rule1.save()
        rule2 = Rule()
        rule2.name = 'Rule 2'
        rule2.maximum_amount = Decimal('40')
        rule2.sequence = 2
        rline3 = RuleLine()
        rule2.lines.append(rline3)
        rline3.amount = 'total_amount'
        rline3.account = revenue
        rline3.sequence = 1
        rule2.save()

        # Create Bank Statement 1 to apply description and minimum amount rules
        BankStatement = Model.get('account.bank.statement')
        StatementLine = Model.get('account.bank.statement.line')
        statement = BankStatement(journal=statement_journal, date=now)
        statement_line = StatementLine()
        statement.lines.append(statement_line)
        statement_line.date = now
        statement_line.description = 'Apply Rule 1'
        statement_line.amount = Decimal('80.0')
        statement.save()
        statement.reload()

        # Apply rules in Bank Statement 1
        slines = [l for l in statement.lines]
        StatementLine.search_reconcile([l.id for l in slines], config.context)
        statement.reload()
        r1line, r2line = statement.lines[0].lines
        self.assertEqual(r1line.amount, Decimal('5'))
        self.assertEqual(r2line.amount, Decimal('75'))

        # Create Bank Statement 2 to apply account and maximum amount rules
        statement2 = BankStatement(journal=statement_journal, date=now)
        statement_line2 = StatementLine()
        statement2.lines.append(statement_line2)
        statement_line2.date = now
        statement_line2.description = 'Apply Rule 2'
        statement_line2.amount = Decimal('30')
        statement_line2.account = revenue
        statement2.save()
        statement2.reload()

        # Apply rules in Bank Statement 2
        slines = [l for l in statement2.lines]
        StatementLine.search_reconcile([l.id for l in slines], config.context)
        statement2.reload()
        r1line, = statement2.lines[0].lines
        self.assertEqual(r1line.amount, Decimal('30'))
