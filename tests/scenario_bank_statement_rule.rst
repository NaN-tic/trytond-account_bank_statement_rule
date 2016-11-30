====================================
Account Bank Statement Rule Scenario
====================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()
    >>> now = datetime.datetime.now()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install account_bank_statement_rule::

    >>> Module = Model.get('ir.module.module')
    >>> account_bank_module, = Module.find(
    ...     [('name', '=', 'account_bank_statement_rule')])
    >>> Module.install([account_bank_module.id], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> currencies = Currency.find([('code', '=', 'USD')])
    >>> if not currencies:
    ...     dollar = Currency(name='US Dollar', symbol=u'$', code='USD',
    ...         rounding=Decimal('0.01'), mon_grouping='[]',
    ...         mon_decimal_point='.')
    ...     dollar.save()
    ...     CurrencyRate(date=today + relativedelta(month=1, day=1),
    ...         rate=Decimal('1.25'), currency=dollar).save()
    ... else:
    ...     dollar, = currencies
    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='Dunder Mifflin')
    >>> party.save()
    >>> company.party = party
    >>> company.currency = dollar
    >>> company_config.execute('add')
    >>> company, = Company.find([])

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create fiscal year::

    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> fiscalyear = FiscalYear(name=str(today.year))
    >>> fiscalyear.start_date = today + relativedelta(month=1, day=1)
    >>> fiscalyear.end_date = today + relativedelta(month=12, day=31)
    >>> fiscalyear.company = company
    >>> post_move_seq = Sequence(name=str(today.year), code='account.move',
    ...     company=company)
    >>> post_move_seq.save()
    >>> fiscalyear.post_move_sequence = post_move_seq
    >>> invoice_seq = SequenceStrict(name=str(today.year),
    ...     code='account.invoice', company=company)
    >>> invoice_seq.save()
    >>> fiscalyear.out_invoice_sequence = invoice_seq
    >>> fiscalyear.in_invoice_sequence = invoice_seq
    >>> fiscalyear.out_credit_note_sequence = invoice_seq
    >>> fiscalyear.in_credit_note_sequence = invoice_seq
    >>> fiscalyear.save()
    >>> FiscalYear.create_period([fiscalyear.id], config.context)

Create chart of accounts::

    >>> AccountTemplate = Model.get('account.account.template')
    >>> Account = Model.get('account.account')
    >>> account_template, = AccountTemplate.find([('parent', '=', None)])
    >>> create_chart = Wizard('account.create_chart')
    >>> create_chart.execute('account')
    >>> create_chart.form.account_template = account_template
    >>> create_chart.form.company = company
    >>> create_chart.execute('create_account')
    >>> receivable, = Account.find([
    ...         ('kind', '=', 'receivable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> payable, = Account.find([
    ...         ('kind', '=', 'payable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> revenue, = Account.find([
    ...         ('kind', '=', 'revenue'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> expense, = Account.find([
    ...         ('kind', '=', 'expense'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> account_tax, = Account.find([
    ...         ('kind', '=', 'other'),
    ...         ('company', '=', company.id),
    ...         ('name', '=', 'Main Tax'),
    ...         ])
    >>> cash, = Account.find([
    ...         ('kind', '=', 'other'),
    ...         ('company', '=', company.id),
    ...         ('name', '=', 'Main Cash'),
    ...         ])
    >>> cash.bank_reconcile = True
    >>> cash.save()
    >>> create_chart.form.account_receivable = receivable
    >>> create_chart.form.account_payable = payable
    >>> create_chart.execute('create_properties')

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create Journal::

    >>> sequence = Sequence(name='Bank', code='account.journal',
    ...     company=company)
    >>> sequence.save()
    >>> AccountJournal = Model.get('account.journal')
    >>> account_journal = AccountJournal(name='Statement',
    ...     type='cash',
    ...     credit_account=cash,
    ...     debit_account=cash,
    ...     sequence=sequence)
    >>> account_journal.save()

Create Statement Journal::

    >>> StatementJournal = Model.get('account.bank.statement.journal')
    >>> statement_journal_dollar = StatementJournal(name='Test',
    ...     journal=account_journal, currency=dollar)
    >>> statement_journal_dollar.save()

Create Rules:

    >>> Rule = Model.get('account.bank.statement.line.rule')
    >>> RuleLine = Model.get('account.bank.statement.line.rule.line')
    >>> rule1 = Rule()
    >>> rule1.name = 'Rule 1'
    >>> rule1.description = 'Apply Rule 1'
    >>> rule1.minimum_amount = Decimal('40')
    >>> rule1.party = party
    >>> rule1.sequence = 1
    >>> rline1 = RuleLine()
    >>> rule1.lines.append(rline1)
    >>> rline1.amount = '5'
    >>> rline1.description = 'Rule Line 1'
    >>> rline1.account = payable
    >>> rline1.party = party
    >>> rline1.sequence = 1
    >>> rline2 = RuleLine()
    >>> rule1.lines.append(rline2)
    >>> rline2.amount = 'pending_amount'
    >>> rline2.description = 'Rule Line 2'
    >>> rline2.account = revenue
    >>> rline2.sequence = 2
    >>> rule1.save()

    >>> rule2 = Rule()
    >>> rule2.name = 'Rule 2'
    >>> rule2.maximum_amount = Decimal('40')
    >>> rule2.sequence = 2
    >>> rline3 = RuleLine()
    >>> rule2.lines.append(rline3)
    >>> rline3.amount = 'total_amount'
    >>> rline3.account = revenue
    >>> rline3.sequence = 1
    >>> rule2.save()

Create Bank Statement 1 to apply description and minimum amount rules::

    >>> BankStatement = Model.get('account.bank.statement')
    >>> StatementLine = Model.get('account.bank.statement.line')

    >>> statement = BankStatement(journal=statement_journal_dollar, date=now)
    >>> statement_line = StatementLine()
    >>> statement.lines.append(statement_line)
    >>> statement_line.date = now
    >>> statement_line.description = 'Apply Rule 1'
    >>> statement_line.amount = Decimal('80.0')
    >>> statement_line.party = party
    >>> statement.save()
    >>> statement.reload()

Apply rules in Bank Statement 1::

    >>> slines = [l for l in statement.lines]
    >>> StatementLine.search_reconcile([l.id for l in slines], config.context)
    >>> statement.reload()
    >>> r1line, r2line = statement.lines[0].lines
    >>> r1line.amount == Decimal('5')
    True
    >>> r2line.amount == Decimal('75')
    True

Create Bank Statement 2 to apply account and maximum amount rules::

    >>> statement2 = BankStatement(journal=statement_journal_dollar, date=now)
    >>> statement_line2 = StatementLine()
    >>> statement2.lines.append(statement_line2)
    >>> statement_line2.date = now
    >>> statement_line2.description = 'Apply Rule 2'
    >>> statement_line2.amount = Decimal('30')
    >>> statement_line2.account = revenue
    >>> statement2.save()
    >>> statement2.reload()

Apply rules in Bank Statement 2::

    >>> slines = [l for l in statement2.lines]
    >>> StatementLine.search_reconcile([l.id for l in slines], config.context)
    >>> statement2.reload()
    >>> r1line, = statement2.lines[0].lines
    >>> r1line.amount == Decimal('30')
    True
