# ====================================
# Account Bank Statement Rule Scenario
# ====================================

# Imports
from trytond.modules.account_invoice.tests.tools import set_fiscalyear_invoice_sequences
from trytond.modules.account.tests.tools import create_fiscalyear, create_chart, get_accounts
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.tools import activate_modules
from proteus import Model, Wizard
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

        today = datetime.date.today()
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

        # Create party2
        party2 = Party(name='Party')
        party2.save()

        # Create Journal
        Sequence = Model.get('ir.sequence')
        SequenceType = Model.get('ir.sequence.type')
        sequence_type, = SequenceType.find([('name', '=', 'Account Journal')])
        sequence = Sequence(name='Bank', sequence_type=sequence_type,
            company=company)
        sequence.save()
        AccountJournal = Model.get('account.journal')
        account_journal = AccountJournal(name='Statement',
            type='cash', sequence=sequence)
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

        # Try replace active party
        replace = Wizard('party.replace', models=[party])
        replace.form.source = party
        replace.form.destination = party2
        replace.execute('replace')

        # Check fields have been replaced
        rule1.reload()
        line1, line2 = rule1.lines
        self.assertEqual(line1.party, party2)