import os
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, login_required, login_user, logout_user
from flask_migrate import Migrate
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from forms import RegistrationForm
from models import User

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace("postgres://", "postgresql://", 1)
    app.secret_key = 'your_secret_key'

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    migrate = Migrate(app, db)

    @app.route('/')
    def home():
        return render_template('home.html')

    @app.route('/add-event', methods=['GET', 'POST'])
    def add_event():
        if request.method == 'POST':
            # Logic to add event to the database
            pass
        return render_template('add_event.html')

    @app.route('/venues')
    def venue_list():
        return render_template('venue_list.html')

    @app.route('/venues/<int:venue_id>')
    def venue_detail(venue_id):
        return render_template('venue_detail.html')

    @app.route('/admin')
    def admin():
        return render_template('admin.html')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        form = RegistrationForm()
        if form.validate_on_submit():
            existing_user = User.query.filter_by(email=form.email.data).first()
            if existing_user:
                flash('Email already registered. Please login or use a different email.', 'danger')
                return redirect(url_for('register'))

            hashed_password = generate_password_hash(form.password.data)
            new_user = User(name=form.name.data, email=form.email.data, password_hash=hashed_password)
            db.session.add(new_user)
            db.session.commit()

            flash('Your account has been created! You are now able to log in.', 'success')
            return redirect(url_for('login'))
        return render_template('register.html', title='Register', form=form)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')
            user = User.query.filter_by(email=email).first()
            if user and check_password_hash(user.password_hash, password):
                login_user(user)
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid login credentials')
        return render_template('login.html')

    @app.route('/logout')
    def logout():
        logout_user()
        return redirect(url_for('home'))

    @app.route('/dashboard')
    @login_required
    def dashboard():
        return render_template('dashboard.html')

    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
