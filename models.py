from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # Increased length for hash storage
    photo = db.Column(db.String(200), nullable=True)  # Path to profile photo
    categories = db.relationship('Category', backref='user', lazy=True, cascade='all, delete-orphan')
    wallets = db.relationship('Wallet', backref='user', lazy=True, cascade='all, delete-orphan')
    transactions = db.relationship('Transaction', backref='user', lazy=True, cascade='all, delete-orphan')
    budgets = db.relationship('Budget', backref='user', lazy=True, cascade='all, delete-orphan')
    # Relasi ke shared_wallets (dompet yang diterima dari orang lain)
    shared_wallets = db.relationship('SharedWallet', foreign_keys='SharedWallet.shared_with_id', back_populates='shared_with_user', lazy=True)

    def set_password(self, password):
        """Hash dan simpan password"""
        self.password = generate_password_hash(password)

    def check_password(self, password):
        """Verifikasi password dengan hash yang tersimpan"""
        return check_password_hash(self.password, password)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(10))  # 'income' atau 'expense'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(10))  # 'cash' atau 'digital'
    balance = db.Column(db.Float, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transactions = db.relationship('Transaction', backref='wallet', lazy=True, cascade='all, delete-orphan')
    # Relasi ke SharedWallet (dompet yang dibagikan ke orang lain)
    shared_with = db.relationship('SharedWallet', back_populates='wallet', lazy=True, cascade='all, delete-orphan')

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    type = db.Column(db.String(10))  # 'income' atau 'expense'
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.relationship('Category')

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.Integer)
    year = db.Column(db.Integer)
    amount = db.Column(db.Float)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.relationship('Category')

class SharedWallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'), nullable=False)
    shared_with_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    permission = db.Column(db.String(10))  # 'view' atau 'add'
    # Relasi ke Wallet
    wallet = db.relationship('Wallet', back_populates='shared_with')
    # Relasi ke User penerima
    shared_with_user = db.relationship('User', foreign_keys=[shared_with_id], back_populates='shared_wallets')
