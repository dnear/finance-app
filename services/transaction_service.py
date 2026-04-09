from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import joinedload

from models import db, Transaction, Wallet
from utils.datetime_utils import now_wib, to_wib


DATETIME_LOCAL_FORMAT = '%Y-%m-%dT%H:%M'
DATE_INPUT_FORMAT = '%Y-%m-%d'


def normalize_wib_storage(dt):
    converted = to_wib(dt)
    return converted.replace(tzinfo=None) if converted else None


def parse_positive_amount(raw_value, field_name='Nominal', allow_zero=False):
    if raw_value is None or str(raw_value).strip() == '':
        raise ValueError(f'{field_name} tidak valid')

    normalized = str(raw_value).strip().replace(',', '')

    try:
        amount = float(Decimal(normalized))
    except (InvalidOperation, ValueError):
        raise ValueError(f'{field_name} tidak valid')

    if allow_zero:
        if amount < 0:
            raise ValueError(f'{field_name} tidak valid')
    elif amount <= 0:
        raise ValueError(f'{field_name} tidak valid')

    return amount


def parse_transaction_datetime(raw_value):
    if not raw_value or not str(raw_value).strip():
        raise ValueError('Tanggal tidak boleh kosong')

    try:
        parsed = datetime.strptime(raw_value.strip(), DATETIME_LOCAL_FORMAT)
    except ValueError:
        raise ValueError('Format tanggal tidak valid')

    return normalize_wib_storage(parsed)


def parse_date_filter(raw_value, end_of_day=False):
    if not raw_value or not str(raw_value).strip():
        raise ValueError('Tanggal tidak boleh kosong')

    try:
        parsed = datetime.strptime(raw_value.strip(), DATE_INPUT_FORMAT)
    except ValueError:
        raise ValueError('Format tanggal tidak valid')

    if end_of_day:
        parsed = parsed + timedelta(days=1)

    return normalize_wib_storage(parsed)


def get_filtered_transactions(user_id, filters):
    category_filter = filters.get('category_id')
    wallet_filter = filters.get('wallet_id')
    start_date = filters.get('start_date')
    end_date = filters.get('end_date')
    tx_type = filters.get('type')
    search = filters.get('search')

    query = Transaction.query.options(
        joinedload(Transaction.wallet),
        joinedload(Transaction.category),
    ).filter_by(user_id=user_id)

    if category_filter:
        try:
            query = query.filter_by(category_id=int(category_filter))
        except (TypeError, ValueError):
            pass

    if wallet_filter:
        try:
            query = query.filter(Transaction.wallet_id == int(wallet_filter))
        except (TypeError, ValueError):
            pass

    if start_date:
        try:
            query = query.filter(Transaction.date >= parse_date_filter(start_date))
        except ValueError:
            pass

    if end_date:
        try:
            query = query.filter(Transaction.date < parse_date_filter(end_date, end_of_day=True))
        except ValueError:
            pass

    if tx_type in {'income', 'expense'}:
        query = query.filter(Transaction.type == tx_type)

    if search:
        search = search.strip()
        if search:
            query = query.filter(Transaction.description.ilike(f'%{search}%'))

    return query


def calculate_transaction_totals(transactions):
    total_income = sum(t.amount for t in transactions if t.type == 'income')
    total_expense = sum(t.amount for t in transactions if t.type == 'expense')
    return {
        'total_income': total_income,
        'total_expense': total_expense,
        'net_total': total_income - total_expense,
    }


def create_transaction(user_id, wallet_id, amount, category_id, description, transaction_type, date=None):
    from services.wallet_service import apply_transaction_effect, get_wallet_for_transaction

    try:
        transaction_date = date or normalize_wib_storage(now_wib())
        wallet = get_wallet_for_transaction(user_id, wallet_id, require_add_permission=True)
        apply_transaction_effect(wallet, amount, transaction_type)

        transaction = Transaction(
            user_id=user_id,
            wallet_id=wallet_id,
            amount=amount,
            category_id=category_id,
            description=description,
            type=transaction_type,
            date=transaction_date,
        )

        db.session.add(transaction)
        db.session.commit()
        return transaction
    except Exception:
        db.session.rollback()
        raise


def update_transaction(transaction, user_id, wallet_id, amount, category_id, description, transaction_type, date):
    from services.wallet_service import (
        apply_transaction_effect,
        get_wallet_for_transaction,
        revert_transaction_effect,
    )

    if transaction.user_id != user_id:
        raise ValueError('Anda tidak memiliki akses')

    try:
        old_wallet = Wallet.query.get(transaction.wallet_id)
        revert_transaction_effect(old_wallet, transaction.amount, transaction.type)

        new_wallet = get_wallet_for_transaction(user_id, wallet_id, require_add_permission=True)

        transaction.amount = amount
        transaction.description = description
        transaction.type = transaction_type
        transaction.category_id = category_id
        transaction.wallet_id = wallet_id
        transaction.date = date

        apply_transaction_effect(new_wallet, transaction.amount, transaction.type)
        db.session.commit()
        return transaction
    except Exception:
        db.session.rollback()
        raise


def delete_transaction(transaction, user_id):
    from services.wallet_service import revert_transaction_effect

    if transaction.user_id != user_id:
        raise ValueError('Anda tidak memiliki akses')

    try:
        wallet = Wallet.query.get(transaction.wallet_id)
        revert_transaction_effect(wallet, transaction.amount, transaction.type)
        db.session.delete(transaction)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise