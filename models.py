from extensions import db
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from slugify import slugify
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime


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
     image_path = db.Column(db.String(255))  # or 'image_filename'
     slug = db.Column(db.String(255), unique=True, nullable=False)
     instagram_handle = db.Column(db.String(255))  # Instagram username
     phone = db.Column(db.String(20))  # Adjust the length as needed
     address_1 = db.Column(db.String(255))  # Adjust the length as needed
     address_2 = db.Column(db.String(255))  # Adjust the length as needed
     user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
     user = db.relationship('User', backref='venue')
     description = db.Column(db.Text, nullable=True)  # Add this line

     def generate_slug(self):
         self.slug = slugify(self.name)

class Event(db.Model):
     id = db.Column(db.Integer, primary_key=True)
     venue_id = db.Column(db.Integer, db.ForeignKey('venue.id'), nullable=False)
     time_date = db.Column(db.DateTime, nullable=False)
     type = db.Column(db.String(50), nullable=True)
     description = db.Column(db.Text, nullable=False)
     user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
     image_path = db.Column(db.String(255))  # Field to store the image path
     slug = db.Column(db.String(255), unique=True, nullable=False)
     name = db.Column(db.String(255), nullable=False)
     
     def generate_slug(self):
          self.slug = slugify(self.name)
          
class InstagramPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    venue_id = db.Column(db.Integer, db.ForeignKey('venue.id'), nullable=False)
    caption = db.Column(db.Text)
    date = db.Column(db.DateTime, nullable=False)
    image_path = db.Column(db.String(255), nullable=False)

class Email(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)

class FeaturedEvent(db.Model):
    __tablename__ = 'featured_events'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'))
    is_themove = db.Column(db.Boolean, default=False, nullable=False)
    newsletter_created = db.Column(db.Boolean, default=False)
    event = db.relationship('Event', backref='featured_events')
    newsletter_id = db.Column(db.Integer, db.ForeignKey('newsletters.id'))
    newsletter = db.relationship('Newsletter', backref='featured_event')# Add this line

    # ... other fields ...

class Sponsor(db.Model):
    __tablename__ = 'sponsors'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(255))
    # ... other fields ...

class FeaturedImage(db.Model):
    __tablename__ = 'featured_images'
    id = db.Column(db.Integer, primary_key=True)
    image_path = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    # ... other fields ...

class Newsletter(db.Model):
    __tablename__ = 'newsletters'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent = db.Column(db.Boolean, default=False)  # Add this line
    subject = db.Column(db.String(255), nullable=False)
    html_content = db.Column(db.Text, nullable=False)


    # ... other fields you might need, like status, send_date, etc. ...
