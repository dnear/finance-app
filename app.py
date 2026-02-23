from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Category, Wallet, Transaction, Budget, SharedWallet
from datetime import datetime
import pandas as pd
from io import BytesIO
import xlsxwriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'kunci-rahasia-ubah-sekarang'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Buat direktori instance jika belum ada
os.makedirs(os.path.join(app.root_path, 'instance'), exist_ok=True)

with app.app_context():
    db.create_all()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']  # hash password disarankan
        # Cek apakah username sudah ada
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username sudah digunakan')
            return redirect(url_for('register'))
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        flash('Registrasi berhasil, silakan login')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Username atau password salah')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    # Ambil total pemasukan dan pengeluaran bulan ini
    now = datetime.now()
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    
    # Hitung saldo total dari semua dompet milik sendiri
    total_balance = db.session.query(db.func.sum(Wallet.balance)).filter_by(user_id=current_user.id).scalar() or 0
    
    # Data untuk grafik pengeluaran per kategori bulan ini
    from sqlalchemy import func, extract
    expense_data = db.session.query(Category.name, func.sum(Transaction.amount)).\
        join(Transaction, Transaction.category_id == Category.id).\
        filter(Transaction.user_id == current_user.id,
               Transaction.type == 'expense',
               extract('month', Transaction.date) == now.month,
               extract('year', Transaction.date) == now.year).\
        group_by(Category.id).all()
    
    expense_labels = [d[0] for d in expense_data]
    expense_values = [float(d[1]) for d in expense_data]
    
    return render_template('index.html', 
                           total_balance=total_balance,
                           expense_labels=expense_labels,
                           expense_values=expense_values)

@app.route('/categories')
@login_required
def categories():
    cats = Category.query.filter_by(user_id=current_user.id).all()
    return render_template('categories.html', categories=cats)

@app.route('/category/add', methods=['POST'])
@login_required
def add_category():
    name = request.form['name']
    type_ = request.form['type']
    cat = Category(name=name, type=type_, user_id=current_user.id)
    db.session.add(cat)
    db.session.commit()
    flash('Kategori ditambahkan')
    return redirect(url_for('categories'))

@app.route('/category/edit/<int:id>', methods=['POST'])
@login_required
def edit_category(id):
    cat = Category.query.get_or_404(id)
    if cat.user_id != current_user.id:
        flash('Anda tidak memiliki akses')
        return redirect(url_for('categories'))
    cat.name = request.form['name']
    cat.type = request.form['type']
    db.session.commit()
    flash('Kategori diperbarui')
    return redirect(url_for('categories'))

@app.route('/category/delete/<int:id>')
@login_required
def delete_category(id):
    cat = Category.query.get_or_404(id)
    if cat.user_id != current_user.id:
        flash('Anda tidak memiliki akses')
        return redirect(url_for('categories'))
    db.session.delete(cat)
    db.session.commit()
    flash('Kategori dihapus')
    return redirect(url_for('categories'))

@app.route('/wallets')
@login_required
def wallets():
    owned = Wallet.query.filter_by(user_id=current_user.id).all()
    # Dompet yang dibagikan kepada saya
    shared = SharedWallet.query.filter_by(shared_with_id=current_user.id).all()
    return render_template('wallets.html', owned=owned, shared=shared)

@app.route('/wallet/add', methods=['POST'])
@login_required
def add_wallet():
    name = request.form['name']
    type_ = request.form['type']
    balance = float(request.form['balance'])
    wallet = Wallet(name=name, type=type_, balance=balance, user_id=current_user.id)
    db.session.add(wallet)
    db.session.commit()
    flash('Dompet ditambahkan')
    return redirect(url_for('wallets'))

@app.route('/wallet/edit/<int:id>', methods=['POST'])
@login_required
def edit_wallet(id):
    wallet = Wallet.query.get_or_404(id)
    if wallet.user_id != current_user.id:
        flash('Anda tidak memiliki akses')
        return redirect(url_for('wallets'))
    wallet.name = request.form['name']
    wallet.type = request.form['type']
    wallet.balance = float(request.form['balance'])
    db.session.commit()
    flash('Dompet diperbarui')
    return redirect(url_for('wallets'))

@app.route('/wallet/delete/<int:id>')
@login_required
def delete_wallet(id):
    wallet = Wallet.query.get_or_404(id)
    if wallet.user_id != current_user.id:
        flash('Anda tidak memiliki akses')
        return redirect(url_for('wallets'))
    # Hapus juga transaksi terkait? Atau larang hapus jika ada transaksi
    if wallet.transactions:
        flash('Dompet memiliki transaksi, tidak dapat dihapus')
        return redirect(url_for('wallets'))
    db.session.delete(wallet)
    db.session.commit()
    flash('Dompet dihapus')
    return redirect(url_for('wallets'))

@app.route('/transactions')
@login_required
def transactions():
    trans = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()
    categories = Category.query.filter_by(user_id=current_user.id).all()
    wallets = Wallet.query.filter_by(user_id=current_user.id).all()
    # Tambahkan dompet bersama yang memiliki izin 'add'
    shared_wallets = SharedWallet.query.filter_by(shared_with_id=current_user.id, permission='add').all()
    shared_wallet_objects = [sw.wallet for sw in shared_wallets]
    all_wallets = wallets + shared_wallet_objects
    return render_template('transactions.html', transactions=trans, categories=categories, wallets=all_wallets)

@app.route('/transaction/add', methods=['POST'])
@login_required
def add_transaction():
    amount = float(request.form['amount'])
    desc = request.form['description']
    ttype = request.form['type']
    cat_id = int(request.form['category_id'])
    wallet_id = int(request.form['wallet_id'])

    # Validasi wallet: apakah milik sendiri atau bersama dengan izin add
    wallet = Wallet.query.get(wallet_id)
    if not wallet:
        flash('Dompet tidak ditemukan')
        return redirect(url_for('transactions'))
    
    if wallet.user_id != current_user.id:
        # Cek shared wallet
        shared = SharedWallet.query.filter_by(wallet_id=wallet_id, shared_with_id=current_user.id).first()
        if not shared or shared.permission != 'add':
            flash('Anda tidak memiliki izin menambah transaksi di dompet ini')
            return redirect(url_for('transactions'))

    trans = Transaction(amount=amount, description=desc, type=ttype,
                        category_id=cat_id, wallet_id=wallet_id,
                        user_id=current_user.id)
    # Update saldo dompet
    if ttype == 'income':
        wallet.balance += amount
    else:
        wallet.balance -= amount

    db.session.add(trans)
    db.session.commit()
    flash('Transaksi disimpan')
    return redirect(url_for('transactions'))

@app.route('/transaction/edit/<int:id>', methods=['POST'])
@login_required
def edit_transaction(id):
    trans = Transaction.query.get_or_404(id)
    if trans.user_id != current_user.id:
        flash('Anda tidak memiliki akses')
        return redirect(url_for('transactions'))
    # Kembalikan saldo lama
    wallet = Wallet.query.get(trans.wallet_id)
    if trans.type == 'income':
        wallet.balance -= trans.amount
    else:
        wallet.balance += trans.amount

    # Update data baru
    trans.amount = float(request.form['amount'])
    trans.description = request.form['description']
    trans.type = request.form['type']
    trans.category_id = int(request.form['category_id'])
    trans.wallet_id = int(request.form['wallet_id'])

    # Update saldo baru
    new_wallet = Wallet.query.get(trans.wallet_id)
    if trans.type == 'income':
        new_wallet.balance += trans.amount
    else:
        new_wallet.balance -= trans.amount

    db.session.commit()
    flash('Transaksi diperbarui')
    return redirect(url_for('transactions'))

@app.route('/transaction/delete/<int:id>')
@login_required
def delete_transaction(id):
    trans = Transaction.query.get_or_404(id)
    if trans.user_id != current_user.id:
        flash('Anda tidak memiliki akses')
        return redirect(url_for('transactions'))
    # Kembalikan saldo
    wallet = Wallet.query.get(trans.wallet_id)
    if trans.type == 'income':
        wallet.balance -= trans.amount
    else:
        wallet.balance += trans.amount
    db.session.delete(trans)
    db.session.commit()
    flash('Transaksi dihapus')
    return redirect(url_for('transactions'))

@app.route('/budgets')
@login_required
def budgets():
    now = datetime.now()
    month = request.args.get('month', now.month, type=int)
    year = request.args.get('year', now.year, type=int)
    budgets = Budget.query.filter_by(user_id=current_user.id, month=month, year=year).all()
    categories = Category.query.filter_by(user_id=current_user.id).all()
    return render_template('budgets.html', budgets=budgets, categories=categories, month=month, year=year)

@app.route('/budget/add', methods=['POST'])
@login_required
def add_budget():
    cat_id = int(request.form['category_id'])
    month = int(request.form['month'])
    year = int(request.form['year'])
    amount = float(request.form['amount'])
    # Cek apakah sudah ada
    existing = Budget.query.filter_by(user_id=current_user.id, category_id=cat_id, month=month, year=year).first()
    if existing:
        existing.amount = amount
    else:
        budget = Budget(category_id=cat_id, month=month, year=year, amount=amount, user_id=current_user.id)
        db.session.add(budget)
    db.session.commit()
    flash('Anggaran disimpan')
    return redirect(url_for('budgets', month=month, year=year))

@app.route('/budget/delete/<int:id>')
@login_required
def delete_budget(id):
    budget = Budget.query.get_or_404(id)
    if budget.user_id != current_user.id:
        flash('Anda tidak memiliki akses')
        return redirect(url_for('budgets'))
    month, year = budget.month, budget.year
    db.session.delete(budget)
    db.session.commit()
    flash('Anggaran dihapus')
    return redirect(url_for('budgets', month=month, year=year))

@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html')

@app.route('/api/chart-data')
@login_required
def chart_data():
    from sqlalchemy import func, extract
    now = datetime.now()
    data = db.session.query(Category.name, func.sum(Transaction.amount)).\
           join(Transaction).\
           filter(Transaction.user_id == current_user.id,
                  Transaction.type == 'expense',
                  extract('month', Transaction.date) == now.month,
                  extract('year', Transaction.date) == now.year).\
           group_by(Category.id).all()
    return jsonify({'labels': [d[0] for d in data], 'values': [float(d[1]) for d in data]})

@app.route('/export/excel')
@login_required
def export_excel():
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    data = []
    for t in transactions:
        data.append([t.date.strftime('%Y-%m-%d %H:%M'), t.description, t.amount, t.type, t.category.name, t.wallet.name])
    df = pd.DataFrame(data, columns=['Tanggal', 'Deskripsi', 'Jumlah', 'Tipe', 'Kategori', 'Dompet'])
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Transaksi', index=False)
    output.seek(0)
    return send_file(output, download_name='laporan_keuangan.xlsx', as_attachment=True)

@app.route('/export/pdf')
@login_required
def export_pdf():
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    elements = []
    
    # Judul
    styles = getSampleStyleSheet()
    elements.append(Paragraph("Laporan Keuangan", styles['Title']))
    
    # Tabel
    table_data = [['Tanggal', 'Deskripsi', 'Jumlah', 'Tipe', 'Kategori', 'Dompet']]
    for t in transactions:
        table_data.append([
            t.date.strftime('%Y-%m-%d'),
            t.description,
            f"Rp {t.amount:,.0f}",
            'Pemasukan' if t.type=='income' else 'Pengeluaran',
            t.category.name,
            t.wallet.name
        ])
    
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, download_name='laporan.pdf', as_attachment=True)

@app.route('/share/wallet', methods=['POST'])
@login_required
def share_wallet():
    wallet_id = request.form['wallet_id']
    username = request.form['username']
    permission = request.form['permission']
    user_to_share = User.query.filter_by(username=username).first()
    if not user_to_share:
        flash('User tidak ditemukan')
        return redirect(url_for('wallets'))
    # Cek apakah wallet milik current_user
    wallet = Wallet.query.get(wallet_id)
    if wallet.user_id != current_user.id:
        flash('Anda hanya dapat membagikan dompet milik sendiri')
        return redirect(url_for('wallets'))
    # Cek apakah sudah ada
    existing = SharedWallet.query.filter_by(wallet_id=wallet_id, shared_with_id=user_to_share.id).first()
    if existing:
        existing.permission = permission
    else:
        share = SharedWallet(wallet_id=wallet_id, shared_with_id=user_to_share.id, permission=permission)
        db.session.add(share)
    db.session.commit()
    flash('Dompet dibagikan')
    return redirect(url_for('wallets'))

@app.route('/unshare/wallet/<int:id>')
@login_required
def unshare_wallet(id):
    share = SharedWallet.query.get_or_404(id)
    # Pastikan yang menghapus adalah pemilik dompet
    if share.wallet.user_id != current_user.id:
        flash('Anda tidak memiliki izin')
        return redirect(url_for('wallets'))
    db.session.delete(share)
    db.session.commit()
    flash('Berbagi dompet dihentikan')
    return redirect(url_for('wallets'))
