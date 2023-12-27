from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, DateTimeField, SelectField, PasswordField, validators
from wtforms.validators import DataRequired, Email, Length, EqualTo
from models import Venue
from flask_wtf.file import FileField, FileAllowed

class RegistrationForm(FlaskForm):
	 name = StringField('Name', validators=[DataRequired()])
	 email = StringField('Email', validators=[DataRequired(), Email()])
	 password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
	 submit = SubmitField('Sign Up')

class LoginForm(FlaskForm):
	 email = StringField('Email', validators=[DataRequired()])
	 password = PasswordField('Password', validators=[DataRequired()])
	 submit = SubmitField('Login')

class EventForm(FlaskForm):
	 name = StringField('Event Name', validators=[DataRequired()])
	 description = TextAreaField('Event Description', validators=[DataRequired()])
	 time_date = DateTimeField('Event Date and Time', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
	 image = FileField('Event Image', validators=[FileAllowed(['jpg', 'png','jpeg'], 'Images only!')])

	 venue_id = SelectField('Venue', coerce=int, validators=[DataRequired()])

	 def __init__(self, *args, **kwargs):
		  super(EventForm, self).__init__(*args, **kwargs)
		  self.venue_id.choices = [(v.id, v.name) for v in Venue.query.order_by(Venue.name).all()]

	 submit = SubmitField('Create Event')

class EmailCaptureForm(FlaskForm):
	 email = StringField('Email', validators=[DataRequired(), Email()])
	 submit = SubmitField('Get on The List')

class ProfileForm(FlaskForm):
	 name = StringField('Name', validators=[DataRequired(), Length(min=2, max=100)])
	 email = StringField('Email', validators=[DataRequired(), Email(), Length(min=6, max=120)])

class ChangePasswordForm(FlaskForm):
	 old_password = PasswordField('Old Password', validators=[DataRequired()])
	 new_password = PasswordField('New Password', validators=[
		  DataRequired(),
		  EqualTo('confirm_new_password', message='Passwords must match.')
	 ])
	 confirm_new_password = PasswordField('Confirm New Password', validators=[DataRequired()])
	 submit = SubmitField('Change Password')

	 def validate_old_password(self, old_password):
		  # Check if the old password is correct
		  if not check_password_hash(current_user.password_hash, old_password.data):
			  raise ValidationError('The old password is incorrect.')

class ChangePasswordForm(FlaskForm):
 old_password = PasswordField('Current Password', validators=[DataRequired()])
 new_password = PasswordField('New Password', validators=[DataRequired()])
 confirm_new_password = PasswordField('Confirm New Password',
												  validators=[DataRequired(), EqualTo('new_password', message='Passwords must match.')])
 submit = SubmitField('Change Password')

class VenueForm(FlaskForm):
	 name = StringField('Name', validators=[DataRequired()])
	 address_1 = StringField('Address 1', validators=[DataRequired()])
	 address_2 = StringField('Address 2')
	 city = StringField('City', validators=[DataRequired()])
	 state = StringField('State', validators=[DataRequired()])
	 zip = StringField('Postal Code', validators=[DataRequired()])
	 phone = StringField('Phone Number', validators=[validators.Optional()])
	 website = StringField('Website')
	 instagram_handle = StringField('Instagram')
	 image = FileField('Image', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
	 description = TextAreaField('Description')
	 submit = SubmitField('Add Venue')
	
