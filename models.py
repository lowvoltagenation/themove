from extensions import db
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

class User(UserMixin, db.Model):
     id = db.Column(db.Integer, primary_key=True)
     name = db.Column(db.String(100), nullable=False)
     email = db.Column(db.String(120), unique=True, nullable=False)
     password_hash = db.Column(db.String(256))
     role = db.Column(db.String(10), nullable=True)
     events = db.relationship('Event', backref='author', lazy=True)

     def set_password(self, password):
          self.password_hash = generate_password_hash(password)

     def check_password(self, password):
          return check_password_hash(self.password_hash, password)

class Venue(db.Model):
     id = db.Column(db.Integer, primary_key=True)
     name = db.Column(db.String(100), nullable=False)
     city = db.Column(db.String(100), nullable=False)
     state = db.Column(db.String(50), nullable=False)
     zip = db.Column(db.String(20), nullable=False)
     website = db.Column(db.String(200))
     events = db.relationship('Event', backref='venue', lazy=True)

class Event(db.Model):
     id = db.Column(db.Integer, primary_key=True)
     name = db.Column(db.String(100), nullable=False)
     venue_id = db.Column(db.Integer, db.ForeignKey('venue.id'), nullable=False)
     time_date = db.Column(db.DateTime, nullable=False)
     type = db.Column(db.String(50), nullable=False)
     description = db.Column(db.Text, nullable=False)
     user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
