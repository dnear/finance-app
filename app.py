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
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'kunci-rahasia-ubah-sekarang'
# durasi cookie untuk fitur "ingat saya" (opsional, default 365 hari)
from datetime import timedelta
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads', 'profile_photos')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_categories_wallets():
    try:
        if current_user.is_authenticated:
            categories = Category.query.filter_by(user_id=current_user.id).all()
            wallets = Wallet.query.filter_by(user_id=current_user.id).all()
            shared_wallets = SharedWallet.query.filter_by(shared_with_id=current_user.id, permission='add').all()
            shared_wallet_objects = [sw.wallet for sw in shared_wallets]
            all_wallets = wallets + shared_wallet_objects
            return dict(categories=categories, wallets=all_wallets)
    except Exception:
        pass
    return dict(categories=[], wallets=[])

# Buat direktori instance jika belum ada
os.makedirs(os.path.join(app.root_path, 'instance'), exist_ok=True)

# Buat direktori untuk upload foto profil
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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
        db.session.flush()  # Dapatkan id user sebelum commit

        # Buat kategori default
        default_categories = [
            Category(name='Gaji', type='income', user_id=user.id),
            Category(name='Hadiah', type='income', user_id=user.id),
            Category(name='Makanan', type='expense', user_id=user.id),
            Category(name='Transport', type='expense', user_id=user.id),
            Category(name='Belanja', type='expense', user_id=user.id),
            Category(name='Tagihan', type='expense', user_id=user.id),
            Category(name='Transfer (Keluar)', type='expense', user_id=user.id),
            Category(name='Transfer (Masuk)', type='income', user_id=user.id),
            Category(name='Biaya Transfer', type='expense', user_id=user.id),
        ]
        db.session.add_all(default_categories)
        db.session.commit()
        flash('Registrasi berhasil, silakan login')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            # cek apakah user memilih "ingat saya"
            remember = True if request.form.get('remember') else False
            login_user(user, remember=remember)
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

@app.route('/api/income-expense-data')
@login_required
def income_expense_data():
    from sqlalchemy import func, extract
    now = datetime.now()
    
    # Get monthly income and expense totals
    income = db.session.query(func.sum(Transaction.amount)).\
             filter(Transaction.user_id == current_user.id,
                    Transaction.type == 'income',
                    extract('month', Transaction.date) == now.month,
                    extract('year', Transaction.date) == now.year).scalar() or 0
    
    expense = db.session.query(func.sum(Transaction.amount)).\
              filter(Transaction.user_id == current_user.id,
                     Transaction.type == 'expense',
                     extract('month', Transaction.date) == now.month,
                     extract('year', Transaction.date) == now.year).scalar() or 0
    
    return jsonify({
        'labels': ['Pemasukan', 'Pengeluaran'],
        'income': float(income),
        'expense': float(expense)
    })

@app.route('/api/income-expense-line')
@login_required
def income_expense_line():
    from sqlalchemy import func, extract
    now = datetime.now()
    labels = []
    incomes = []
    expenses = []
    # last 6 months
    for i in range(5, -1, -1):
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1
        label = f"{month}/{year}"
        inc = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == current_user.id,
            Transaction.type == 'income',
            extract('month', Transaction.date) == month,
            extract('year', Transaction.date) == year
        ).scalar() or 0
        exp = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == current_user.id,
            Transaction.type == 'expense',
            extract('month', Transaction.date) == month,
            extract('year', Transaction.date) == year
        ).scalar() or 0
        labels.append(label)
        incomes.append(float(inc))
        expenses.append(float(exp))
    return jsonify({'labels': labels, 'income': incomes, 'expense': expenses})

@app.route('/api/budget-realization')
@login_required
def budget_realization():
    from sqlalchemy import func, extract
    now = datetime.now()
    budgets = Budget.query.filter_by(user_id=current_user.id, month=now.month, year=now.year).all()
    labels = []
    budget_vals = []
    real_vals = []
    for b in budgets:
        labels.append(b.category.name)
        budget_vals.append(b.amount)
        real = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == current_user.id,
            Transaction.category_id == b.category_id,
            Transaction.type == 'expense',
            extract('month', Transaction.date) == now.month,
            extract('year', Transaction.date) == now.year
        ).scalar() or 0
        real_vals.append(float(real))
    return jsonify({'labels': labels, 'budget': budget_vals, 'real': real_vals})

@app.route('/api/cashflow-data')
@login_required
def cashflow_data():
    from datetime import timedelta
    now = datetime.now()
    start = now - timedelta(days=30)
    transactions = Transaction.query.filter(Transaction.user_id == current_user.id,
                                         Transaction.date >= start).order_by(Transaction.date).all()
    labels = []
    balances = []
    bal = 0
    for t in transactions:
        if t.type == 'income':
            bal += t.amount
        else:
            bal -= t.amount
        labels.append(t.date.strftime('%d/%m'))
        balances.append(bal)
    return jsonify({'labels': labels, 'balance': balances})

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

# ================== FITUR TRANSFER ==================
@app.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    wallets = Wallet.query.filter_by(user_id=current_user.id).all()
    if request.method == 'POST':
        from_wallet_id = int(request.form['from_wallet'])
        to_wallet_id = int(request.form['to_wallet'])
        amount = float(request.form['amount'])
        fee = float(request.form.get('fee', 0))
        description = request.form.get('description', 'Transfer')

        # Validasi dompet sama
        if from_wallet_id == to_wallet_id:
            flash('Dompet asal dan tujuan tidak boleh sama')
            return redirect(url_for('transfer'))

        from_wallet = Wallet.query.get(from_wallet_id)
        to_wallet = Wallet.query.get(to_wallet_id)

        # Validasi saldo
        if from_wallet.balance < amount + fee:
            flash('Saldo tidak mencukupi (termasuk biaya transfer)')
            return redirect(url_for('transfer'))

        # Cari atau buat kategori khusus transfer
        transfer_out_cat = Category.query.filter_by(user_id=current_user.id, name='Transfer (Keluar)', type='expense').first()
        if not transfer_out_cat:
            transfer_out_cat = Category(name='Transfer (Keluar)', type='expense', user_id=current_user.id)
            db.session.add(transfer_out_cat)
            db.session.flush()  # Penting: dapatkan ID

        transfer_in_cat = Category.query.filter_by(user_id=current_user.id, name='Transfer (Masuk)', type='income').first()
        if not transfer_in_cat:
            transfer_in_cat = Category(name='Transfer (Masuk)', type='income', user_id=current_user.id)
            db.session.add(transfer_in_cat)
            db.session.flush()  # Penting: dapatkan ID

        # Proses transaksi keluar
        trans_out = Transaction(
            amount=amount,
            description=f'Transfer ke {to_wallet.name}: {description}',
            type='expense',
            category_id=transfer_out_cat.id,
            wallet_id=from_wallet.id,
            user_id=current_user.id
        )
        from_wallet.balance -= amount
        db.session.add(trans_out)

        # Proses transaksi masuk
        trans_in = Transaction(
            amount=amount,
            description=f'Transfer dari {from_wallet.name}: {description}',
            type='income',
            category_id=transfer_in_cat.id,
            wallet_id=to_wallet.id,
            user_id=current_user.id
        )
        to_wallet.balance += amount
        db.session.add(trans_in)

        # Proses biaya transfer (jika ada)
        if fee > 0:
            fee_cat = Category.query.filter_by(user_id=current_user.id, name='Biaya Transfer', type='expense').first()
            if not fee_cat:
                fee_cat = Category(name='Biaya Transfer', type='expense', user_id=current_user.id)
                db.session.add(fee_cat)
                db.session.flush()  # Penting: dapatkan ID

            trans_fee = Transaction(
                amount=fee,
                description=f'Biaya transfer ke {to_wallet.name}',
                type='expense',
                category_id=fee_cat.id,
                wallet_id=from_wallet.id,
                user_id=current_user.id
            )
            from_wallet.balance -= fee
            db.session.add(trans_fee)

        db.session.commit()
        flash('Transfer berhasil')
        return redirect(url_for('wallets'))

    return render_template('transfer.html', wallets=wallets)

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@app.route('/upload_photo', methods=['POST'])
@login_required
def upload_photo():
    if 'photo' not in request.files:
        flash('Tidak ada file yang dipilih')
        return redirect(url_for('profile'))
    
    file = request.files['photo']
    if file.filename == '':
        flash('Tidak ada file yang dipilih')
        return redirect(url_for('profile'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(f"user_{current_user.id}_{file.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Hapus foto lama jika ada
        if current_user.photo and os.path.exists(os.path.join(app.root_path, 'static', current_user.photo)):
            os.remove(os.path.join(app.root_path, 'static', current_user.photo))
        
        # Update database
        current_user.photo = f'uploads/profile_photos/{filename}'
        db.session.commit()
        
        flash('Foto profil berhasil diubah')
    else:
        flash('Format file tidak didukung. Gunakan JPG, PNG, atau GIF')
    
    return redirect(url_for('profile'))

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        if current_user.password != current_password:
            flash('Password saat ini salah')
            return redirect(url_for('change_password'))
        
        if new_password != confirm_password:
            flash('Password baru tidak cocok')
            return redirect(url_for('change_password'))
        
        current_user.password = new_password
        db.session.commit()
        flash('Password berhasil diubah')
        return redirect(url_for('profile'))
    
    return render_template('change_password.html')

@app.route('/backup')
@login_required
def backup():
    # Backup data ke CSV
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Header untuk transactions
    writer.writerow(['Date', 'Amount', 'Description', 'Type', 'Category', 'Wallet'])
    
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    for t in transactions:
        category = Category.query.get(t.category_id)
        wallet = Wallet.query.get(t.wallet_id)
        writer.writerow([
            t.date.strftime('%Y-%m-%d %H:%M:%S'),
            t.amount,
            t.description,
            t.type,
            category.name if category else '',
            wallet.name if wallet else ''
        ])
    
    output.seek(0)
    return send_file(
        BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='finance_backup.csv'
    )

@app.route('/import_data', methods=['GET', 'POST'])
@login_required
def import_data():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Tidak ada file yang dipilih')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('Tidak ada file yang dipilih')
            return redirect(request.url)
        
        if file and file.filename.endswith('.csv'):
            import csv
            from io import TextIOWrapper
            
            stream = TextIOWrapper(file.stream, encoding='utf-8')
            csv_reader = csv.reader(stream)
            
            # Skip header
            next(csv_reader, None)
            
            imported_count = 0
            errors = []
            
            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    if len(row) != 6:
                        errors.append(f'Baris {row_num}: Format tidak valid')
                        continue
                    
                    date_str, amount_str, description, type_, category_name, wallet_name = row
                    
                    # Parse date
                    try:
                        date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        errors.append(f'Baris {row_num}: Format tanggal tidak valid')
                        continue
                    
                    # Parse amount
                    try:
                        amount = float(amount_str)
                    except ValueError:
                        errors.append(f'Baris {row_num}: Jumlah tidak valid')
                        continue
                    
                    # Validate type
                    if type_ not in ['income', 'expense']:
                        errors.append(f'Baris {row_num}: Tipe harus income atau expense')
                        continue
                    
                    # Get or create category
                    category = Category.query.filter_by(user_id=current_user.id, name=category_name, type=type_).first()
                    if not category:
                        category = Category(name=category_name, type=type_, user_id=current_user.id)
                        db.session.add(category)
                        db.session.flush()
                    
                    # Get or create wallet
                    wallet = Wallet.query.filter_by(user_id=current_user.id, name=wallet_name).first()
                    if not wallet:
                        wallet = Wallet(name=wallet_name, type='cash', balance=0.0, user_id=current_user.id)
                        db.session.add(wallet)
                        db.session.flush()
                    
                    # Create transaction
                    transaction = Transaction(
                        amount=amount,
                        description=description,
                        date=date,
                        type=type_,
                        category_id=category.id,
                        wallet_id=wallet.id,
                        user_id=current_user.id
                    )
                    db.session.add(transaction)
                    
                    # Update wallet balance
                    if type_ == 'income':
                        wallet.balance += amount
                    else:
                        wallet.balance -= amount
                    
                    imported_count += 1
                    
                except Exception as e:
                    errors.append(f'Baris {row_num}: Error - {str(e)}')
            
            db.session.commit()
            
            if imported_count > 0:
                flash(f'Berhasil mengimpor {imported_count} transaksi')
            if errors:
                flash(f'Error pada {len(errors)} baris: ' + '; '.join(errors[:5]))  # Show first 5 errors
            
            return redirect(url_for('profile'))
        else:
            flash('File harus berformat CSV')
            return redirect(request.url)
    
    return render_template('import_data.html')
