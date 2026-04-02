from flask import jsonify, request
from flask_login import current_user, login_required

from api import api_bp
from models import Transaction
from services.transaction_service import (
    calculate_transaction_totals,
    create_transaction,
    get_filtered_transactions,
    parse_positive_amount,
    parse_transaction_datetime,
)
from services.wallet_service import transfer_balance
from utils.datetime_utils import to_wib


def _serialize_transaction(transaction):
    return {
        "id": transaction.id,
        "amount": float(transaction.amount),
        "description": transaction.description or "",
        "type": transaction.type,
        "date": to_wib(transaction.date).strftime('%Y-%m-%d %H:%M:%S') if transaction.date else None,
        "category": transaction.category.name if transaction.category else None,
        "wallet": transaction.wallet.name if transaction.wallet else None,
        "category_id": transaction.category_id,
        "wallet_id": transaction.wallet_id,
    }


@api_bp.route("/transactions", methods=["GET"])
@login_required
def get_transactions():
    try:
        page = max(request.args.get("page", 1, type=int), 1)
        per_page = request.args.get("per_page", 10, type=int)
        per_page = min(max(per_page, 1), 100)

        filters = {
            "category_id": request.args.get("category_id", type=int),
            "wallet_id": request.args.get("wallet_id", type=int),
            "start_date": request.args.get("start_date"),
            "end_date": request.args.get("end_date"),
            "search": request.args.get("search", ""),
        }

        pagination = get_filtered_transactions(current_user.id, filters) \
            .order_by(Transaction.date.desc()) \
            .paginate(page=page, per_page=per_page, error_out=False)

        data = {
            "total": pagination.total,
            "page": pagination.page,
            "pages": pagination.pages,
            "data": [_serialize_transaction(transaction) for transaction in pagination.items],
        }
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400


@api_bp.route("/transactions", methods=["POST"])
@login_required
def create_transaction_api():
    try:
        payload = request.get_json(silent=True) or {}

        amount = parse_positive_amount(payload.get("amount"))
        category_id = int(payload.get("category_id"))
        wallet_id = int(payload.get("wallet_id"))
        transaction_type = str(payload.get("type", "")).strip()
        if transaction_type not in {"income", "expense"}:
            raise ValueError("Tipe transaksi tidak valid")

        raw_date = payload.get("date")
        transaction = create_transaction(
            user_id=current_user.id,
            wallet_id=wallet_id,
            amount=amount,
            category_id=category_id,
            description=(payload.get("description") or "").strip(),
            transaction_type=transaction_type,
            date=parse_transaction_datetime(raw_date) if raw_date else None,
        )

        return {
            "status": "success",
            "data": _serialize_transaction(transaction),
        }, 201
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400


@api_bp.route("/transfer", methods=["POST"])
@login_required
def transfer_api():
    try:
        payload = request.get_json(silent=True) or {}
        from_wallet_id = int(payload.get("from_wallet_id"))
        to_wallet_id = int(payload.get("to_wallet_id"))
        amount = parse_positive_amount(payload.get("amount"))
        fee = parse_positive_amount(payload.get("fee", 0), 'Biaya transfer', allow_zero=True)
        description = (payload.get("description") or "Transfer").strip() or "Transfer"

        result = transfer_balance(
            user_id=current_user.id,
            from_wallet_id=from_wallet_id,
            to_wallet_id=to_wallet_id,
            amount=amount,
            fee=fee,
            description=description,
        )

        return {
            "status": "success",
            "data": {
                "from_wallet": result["from_wallet"].name,
                "to_wallet": result["to_wallet"].name,
                "amount": float(result["amount"]),
                "fee": float(result["fee"]),
            },
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400


@api_bp.route("/reports/preview", methods=["GET"])
@login_required
def preview_report_api():
    try:
        filters = {
            "category_id": request.args.get("category_id", type=int),
            "wallet_id": request.args.get("wallet_id", type=int),
            "start_date": request.args.get("start_date"),
            "end_date": request.args.get("end_date"),
            "search": request.args.get("search", ""),
        }

        transactions = get_filtered_transactions(current_user.id, filters) \
            .order_by(Transaction.date.desc()) \
            .limit(100) \
            .all()
        totals = calculate_transaction_totals(transactions)

        data = {
            "transactions": [
                {
                    "date": to_wib(transaction.date).strftime('%d/%m/%Y %H:%M'),
                    "description": transaction.description or '-',
                    "amount": float(transaction.amount),
                    "type": transaction.type,
                    "category": transaction.category.name if transaction.category else '-',
                }
                for transaction in transactions
            ],
            "summary": {
                "total_income": float(totals["total_income"]),
                "total_expense": float(totals["total_expense"]),
                "balance": float(totals["net_total"]),
            },
        }
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400