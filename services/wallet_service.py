from models import db, Category, SharedWallet, Transaction, Wallet
from utils.datetime_utils import now_wib
from services.transaction_service import normalize_wib_storage


def validate_wallet_ownership(wallet, user_id):
    if wallet.user_id != user_id:
        raise ValueError('Anda tidak memiliki akses')


def get_owned_wallet(user_id, wallet_id):
    wallet = Wallet.query.get(wallet_id)
    if not wallet:
        raise ValueError('Dompet tidak ditemukan')

    if wallet.user_id != user_id:
        raise ValueError('Anda tidak memiliki akses ke dompet yang dipilih')

    return wallet


def get_wallet_for_transaction(user_id, wallet_id, require_add_permission=False):
    wallet = Wallet.query.get(wallet_id)
    if not wallet:
        raise ValueError('Dompet tidak ditemukan')

    if wallet.user_id == user_id:
        return wallet

    shared = SharedWallet.query.filter_by(wallet_id=wallet_id, shared_with_id=user_id).first()
    if not shared:
        raise ValueError('Anda tidak memiliki akses ke dompet yang dipilih')

    if require_add_permission and shared.permission != 'add':
        raise ValueError('Anda tidak memiliki izin menambah transaksi di dompet ini')

    return wallet


def apply_transaction_effect(wallet, amount, transaction_type):
    if transaction_type == 'income':
        wallet.balance += amount
        return wallet

    if wallet.balance < amount:
        raise ValueError('Saldo tidak mencukupi')

    wallet.balance -= amount
    return wallet


def revert_transaction_effect(wallet, amount, transaction_type):
    if transaction_type == 'income':
        wallet.balance -= amount
    else:
        wallet.balance += amount
    return wallet


def create_wallet(user_id, name, wallet_type, balance):
    wallet = Wallet(name=name, type=wallet_type, balance=balance, user_id=user_id)
    db.session.add(wallet)
    db.session.commit()
    return wallet


def update_wallet(wallet, user_id, name, wallet_type, balance):
    validate_wallet_ownership(wallet, user_id)
    wallet.name = name
    wallet.type = wallet_type
    wallet.balance = balance
    db.session.commit()
    return wallet


def delete_wallet(wallet, user_id):
    validate_wallet_ownership(wallet, user_id)

    if wallet.transactions:
        raise ValueError('Dompet memiliki transaksi, tidak dapat dihapus')

    db.session.delete(wallet)
    db.session.commit()


def get_or_create_transfer_category(user_id, name, category_type):
    category = Category.query.filter_by(user_id=user_id, name=name, type=category_type).first()
    if category:
        return category

    category = Category(name=name, type=category_type, user_id=user_id)
    db.session.add(category)
    db.session.flush()
    return category


def transfer_balance(user_id, from_wallet_id, to_wallet_id, amount, fee=0, description='Transfer'):
    if from_wallet_id == to_wallet_id:
        raise ValueError('Tidak bisa transfer ke wallet yang sama')

    try:
        from_wallet = get_owned_wallet(user_id, from_wallet_id)
        to_wallet = get_owned_wallet(user_id, to_wallet_id)

        if from_wallet.balance < amount + fee:
            raise ValueError('Saldo tidak mencukupi (termasuk biaya transfer)')

        transfer_time = normalize_wib_storage(now_wib())
        transfer_out_cat = get_or_create_transfer_category(user_id, 'Transfer (Keluar)', 'expense')
        transfer_in_cat = get_or_create_transfer_category(user_id, 'Transfer (Masuk)', 'income')

        trans_out = Transaction(
            amount=amount,
            description=f'Transfer ke {to_wallet.name}: {description}',
            type='expense',
            category_id=transfer_out_cat.id,
            wallet_id=from_wallet.id,
            user_id=user_id,
            date=transfer_time,
        )
        from_wallet.balance -= amount
        db.session.add(trans_out)

        trans_in = Transaction(
            amount=amount,
            description=f'Transfer dari {from_wallet.name}: {description}',
            type='income',
            category_id=transfer_in_cat.id,
            wallet_id=to_wallet.id,
            user_id=user_id,
            date=transfer_time,
        )
        to_wallet.balance += amount
        db.session.add(trans_in)

        if fee > 0:
            fee_cat = get_or_create_transfer_category(user_id, 'Biaya Transfer', 'expense')
            trans_fee = Transaction(
                amount=fee,
                description=f'Biaya transfer ke {to_wallet.name}',
                type='expense',
                category_id=fee_cat.id,
                wallet_id=from_wallet.id,
                user_id=user_id,
                date=transfer_time,
            )
            from_wallet.balance -= fee
            db.session.add(trans_fee)

        db.session.commit()
        return {'from_wallet': from_wallet, 'to_wallet': to_wallet, 'amount': amount, 'fee': fee}
    except Exception:
        db.session.rollback()
        raise