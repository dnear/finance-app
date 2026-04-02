from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, FloatField, SelectField, TextAreaField, IntegerField
from wtforms.fields.datetime import DateTimeLocalField
from wtforms.validators import DataRequired, Length, EqualTo, NumberRange, Optional

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=80)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Konfirmasi Password', validators=[DataRequired(), EqualTo('password')])


class TransactionForm(FlaskForm):
    amount = FloatField('Jumlah', validators=[DataRequired(), NumberRange(min=1)])
    description = TextAreaField('Deskripsi', validators=[Optional(), Length(max=200)])
    type = SelectField('Tipe', choices=[('income', 'Pemasukan'), ('expense', 'Pengeluaran')], validators=[DataRequired()])
    category_id = IntegerField('Kategori', validators=[DataRequired()])
    wallet_id = IntegerField('Dompet', validators=[DataRequired()])
    date = DateTimeLocalField('Tanggal & Waktu', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])


class TransferForm(FlaskForm):
    from_wallet = IntegerField('Dari Dompet', validators=[DataRequired()])
    to_wallet = IntegerField('Ke Dompet', validators=[DataRequired()])
    amount = FloatField('Jumlah Transfer', validators=[DataRequired(), NumberRange(min=1)])
    fee = FloatField('Biaya Transfer', validators=[Optional(), NumberRange(min=0)])
    description = TextAreaField('Deskripsi', validators=[Optional(), Length(max=200)])
