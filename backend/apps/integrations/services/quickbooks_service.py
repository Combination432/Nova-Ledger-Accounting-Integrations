"""
QuickBooks integration service for Nova Ledger.
Handles syncing journal entries and account mappings to QuickBooks Online.
"""
from quickbooks import QuickBooks
from quickbooks.objects import JournalEntry as QBJournalEntry, JournalEntryLine as QBJournalEntryLine
from quickbooks.objects import Account as QBAccount
from decimal import Decimal
from datetime import datetime
from django.utils import timezone
from apps.transactions.models import JournalEntry, JournalEntryLine
from apps.integrations.models import Integration, SyncLog, AccountMapping
from apps.accounts.models import ChartOfAccounts
import logging

logger = logging.getLogger(__name__)


class QuickBooksIntegrationService:
    """
    Service for syncing Nova Ledger data to QuickBooks Online.
    Bidirectional sync of journal entries and chart of accounts.
    """

    def __init__(self, integration: Integration):
        self.integration = integration
        self.organization = integration.organization

        # Initialize QuickBooks client
        realm_id = integration.settings.get('realm_id')
        access_token = integration.oauth_access_token
        refresh_token = integration.oauth_refresh_token

        if not realm_id or not access_token:
            raise ValueError("QuickBooks realm ID and access token are required")

        self.client = QuickBooks(
            sandbox=integration.settings.get('sandbox', False),
            consumer_key=integration.settings.get('consumer_key'),
            consumer_secret=integration.settings.get('consumer_secret'),
            access_token=access_token,
            access_token_secret=refresh_token,
            company_id=realm_id
        )

    def sync_chart_of_accounts(self, direction='import'):
        """
        Sync chart of accounts between Nova Ledger and QuickBooks.

        Args:
            direction: 'import' (QB -> Nova), 'export' (Nova -> QB), or 'bidirectional'
        """
        sync_log = SyncLog.objects.create(
            integration=self.integration,
            sync_type='quickbooks_chart_of_accounts',
            status='running'
        )

        try:
            if direction in ['import', 'bidirectional']:
                self._import_accounts_from_qb(sync_log)

            if direction in ['export', 'bidirectional']:
                self._export_accounts_to_qb(sync_log)

            sync_log.status = 'completed'
            sync_log.completed_at = timezone.now()
            sync_log.save()

            return sync_log

        except Exception as e:
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.save()
            raise

    def _import_accounts_from_qb(self, sync_log):
        """
        Import chart of accounts from QuickBooks.
        """
        qb_accounts = QBAccount.all(qb=self.client)

        created_count = 0
        updated_count = 0

        for qb_account in qb_accounts:
            # Map QuickBooks account types to Nova Ledger types
            account_type_mapping = {
                'Asset': 'asset',
                'Liability': 'liability',
                'Equity': 'equity',
                'Income': 'revenue',
                'Expense': 'expense',
                'Cost of Goods Sold': 'cogs',
            }

            nova_account_type = account_type_mapping.get(qb_account.AccountType, 'expense')

            # Map subtypes
            subtype_mapping = {
                'Cash': 'cash',
                'AccountsReceivable': 'accounts_receivable',
                'Inventory': 'inventory',
                'AccountsPayable': 'accounts_payable',
                'CreditCard': 'credit_card',
                # Add more mappings as needed
            }

            nova_subtype = subtype_mapping.get(qb_account.AccountSubType, 'other')

            account, created = ChartOfAccounts.objects.update_or_create(
                organization=self.organization,
                quickbooks_id=str(qb_account.Id),
                defaults={
                    'account_number': qb_account.AcctNum or str(qb_account.Id),
                    'account_name': qb_account.Name,
                    'account_type': nova_account_type,
                    'account_subtype': nova_subtype,
                    'description': qb_account.Description or "",
                    'is_active': qb_account.Active,
                }
            )

            # Create account mapping
            AccountMapping.objects.update_or_create(
                integration=self.integration,
                nova_ledger_account=account,
                defaults={
                    'external_account_id': str(qb_account.Id),
                    'external_account_name': qb_account.Name,
                    'last_synced_at': timezone.now(),
                }
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        sync_log.records_created = created_count
        sync_log.records_updated = updated_count

    def _export_accounts_to_qb(self, sync_log):
        """
        Export Nova Ledger accounts to QuickBooks.
        """
        # Get accounts that don't have QuickBooks IDs
        accounts_to_export = ChartOfAccounts.objects.filter(
            organization=self.organization,
            quickbooks_id='',
            is_active=True
        )

        created_count = 0

        for account in accounts_to_export:
            try:
                # Map Nova Ledger types to QuickBooks types
                type_mapping = {
                    'asset': 'Asset',
                    'liability': 'Liability',
                    'equity': 'Equity',
                    'revenue': 'Income',
                    'expense': 'Expense',
                    'cogs': 'Cost of Goods Sold',
                }

                qb_account = QBAccount()
                qb_account.Name = account.account_name
                qb_account.AccountType = type_mapping.get(account.account_type, 'Expense')
                qb_account.AcctNum = account.account_number
                qb_account.Description = account.description
                qb_account.Active = account.is_active

                qb_account.save(qb=self.client)

                # Update Nova Ledger account with QuickBooks ID
                account.quickbooks_id = str(qb_account.Id)
                account.save()

                created_count += 1

            except Exception as e:
                logger.error(f"Failed to export account {account.id} to QuickBooks: {str(e)}")

        sync_log.records_created += created_count

    def sync_journal_entries(self, start_date=None, end_date=None):
        """
        Sync journal entries from Nova Ledger to QuickBooks.
        """
        sync_log = SyncLog.objects.create(
            integration=self.integration,
            sync_type='quickbooks_journal_entries',
            status='running'
        )

        try:
            # Get unsynced journal entries
            query = JournalEntry.objects.filter(
                organization=self.organization,
                status='posted',
                synced_to_accounting=False
            )

            if start_date:
                query = query.filter(entry_date__gte=start_date)
            if end_date:
                query = query.filter(entry_date__lte=end_date)

            processed_count = 0
            created_count = 0
            failed_count = 0

            for journal_entry in query:
                try:
                    if self._export_journal_entry(journal_entry):
                        created_count += 1
                    processed_count += 1

                except Exception as e:
                    logger.error(f"Failed to sync journal entry {journal_entry.id}: {str(e)}")
                    failed_count += 1

            sync_log.status = 'completed'
            sync_log.completed_at = timezone.now()
            sync_log.records_processed = processed_count
            sync_log.records_created = created_count
            sync_log.records_failed = failed_count
            sync_log.save()

            return sync_log

        except Exception as e:
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.save()
            raise

    def _export_journal_entry(self, journal_entry):
        """
        Export a single journal entry to QuickBooks.
        """
        # Check if entry is balanced
        if not journal_entry.is_balanced():
            raise ValueError(f"Journal entry {journal_entry.id} is not balanced")

        qb_je = QBJournalEntry()
        qb_je.TxnDate = journal_entry.entry_date.isoformat()
        qb_je.PrivateNote = journal_entry.description[:4000]  # QuickBooks has a character limit

        # Add lines
        qb_lines = []
        for line in journal_entry.lines.all():
            # Get QuickBooks account ID
            if not line.account.quickbooks_id:
                raise ValueError(f"Account {line.account.account_name} has no QuickBooks ID mapping")

            qb_line = QBJournalEntryLine()
            qb_line.Description = line.description[:1000]

            # Set debit or credit
            if line.debit_amount > 0:
                qb_line.DetailType = "JournalEntryLineDetail"
                qb_line.Amount = float(line.debit_amount)
                qb_line.JournalEntryLineDetail = {
                    "PostingType": "Debit",
                    "AccountRef": {"value": line.account.quickbooks_id}
                }
            else:
                qb_line.DetailType = "JournalEntryLineDetail"
                qb_line.Amount = float(line.credit_amount)
                qb_line.JournalEntryLineDetail = {
                    "PostingType": "Credit",
                    "AccountRef": {"value": line.account.quickbooks_id}
                }

            qb_lines.append(qb_line)

        qb_je.Line = qb_lines

        # Save to QuickBooks
        qb_je.save(qb=self.client)

        # Update Nova Ledger journal entry
        journal_entry.quickbooks_id = str(qb_je.Id)
        journal_entry.synced_to_accounting = True
        journal_entry.sync_date = timezone.now()
        journal_entry.save()

        return True

    def fetch_transactions(self, date_from: datetime, date_to: datetime):
        """
        Fetch transactions from QuickBooks for the sync engine.
        Currently focused on importing journal entries.

        Args:
            date_from: Start date for fetching transactions
            date_to: End date for fetching transactions

        Returns:
            List of raw QuickBooks journal entry dictionaries
        """
        logger.info(f"Fetching QuickBooks journal entries from {date_from} to {date_to}")

        # Query journal entries in date range
        from_date_str = date_from.strftime('%Y-%m-%d')
        to_date_str = date_to.strftime('%Y-%m-%d')

        query = f"SELECT * FROM JournalEntry WHERE TxnDate >= '{from_date_str}' AND TxnDate <= '{to_date_str}' MAXRESULTS 1000"
        journal_entries = self.client.query(query)

        # Convert to dictionaries
        transactions = []
        for je in journal_entries:
            transactions.append(je.to_dict())

        return transactions

    def parse_transaction(self, platform_data: dict) -> dict:
        """
        Parse QuickBooks journal entry data into Nova Ledger transaction format.

        Args:
            platform_data: Raw QuickBooks journal entry dictionary

        Returns:
            Normalized transaction data with structure:
            {
                'transaction': {...},
                'fees': [],
                'line_items': []
            }
        """
        # Extract journal entry details
        entry_id = platform_data.get('Id')
        txn_date = platform_data.get('TxnDate')
        private_note = platform_data.get('PrivateNote', '')
        doc_number = platform_data.get('DocNumber', '')

        # Build transaction data
        # Note: QuickBooks journal entries map to Nova Ledger journal entries,
        # not regular transactions. This is a simplified mapping.
        transaction_data = {
            'external_transaction_id': f"quickbooks_je_{entry_id}",
            'transaction_number': doc_number or f"QB-JE-{entry_id}",
            'transaction_type': 'journal_entry',
            'transaction_date': txn_date,
            'description': private_note or f"QuickBooks Journal Entry {entry_id}",
            'gross_amount': Decimal(0),  # Will be calculated from lines
            'net_amount': Decimal(0),
            'currency': 'USD',  # Default, could be extracted from company settings
            'metadata': {
                'quickbooks_id': entry_id,
                'raw_data': platform_data
            }
        }

        # Parse journal entry lines
        # QuickBooks journal entries have debit/credit lines
        line_items = []
        lines = platform_data.get('Line', [])

        total_debits = Decimal(0)
        total_credits = Decimal(0)

        for line in lines:
            detail = line.get('JournalEntryLineDetail', {})
            account_ref = detail.get('AccountRef', {})
            posting_type = detail.get('PostingType', 'Debit')
            amount = Decimal(str(line.get('Amount', 0)))
            description = line.get('Description', '')

            if posting_type == 'Debit':
                total_debits += amount
            else:
                total_credits += amount

            line_item_data = {
                'product_name': f"{posting_type}: {account_ref.get('name', 'Unknown')}",
                'description': description,
                'quantity': Decimal(1),
                'unit_price': amount,
                'total_price': amount,
                'metadata': {
                    'posting_type': posting_type,
                    'account_id': account_ref.get('value', ''),
                    'account_name': account_ref.get('name', '')
                }
            }
            line_items.append(line_item_data)

        # Update transaction amounts
        transaction_data['gross_amount'] = max(total_debits, total_credits)
        transaction_data['net_amount'] = max(total_debits, total_credits)

        # QuickBooks journal entries don't have fees
        fees = []

        return {
            'transaction': transaction_data,
            'line_items': line_items,
            'fees': fees
        }

    def test_connection(self):
        """
        Test QuickBooks connection.
        """
        try:
            company_info = self.client.query("SELECT * FROM CompanyInfo")
            return True, f"Connected to {company_info[0].CompanyName}"
        except Exception as e:
            return False, str(e)
