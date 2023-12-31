import os
from datetime import datetime

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, current_app, make_response, flash, redirect, render_template, request, url_for
from flask_apscheduler import APScheduler
from flask_login import (
     LoginManager,
     current_user,
     login_required,
     login_user,
     logout_user,
)
from flask_migrate import Migrate
from PIL import Image
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from slugify import slugify
from sqlalchemy.exc import SQLAlchemyError

from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from extensions import db
from forms import EmailCaptureForm, EventForm, LoginForm, RegistrationForm, ProfileForm, ChangePasswordForm, VenueForm
from models import (
     Email,
     Event,
     FeaturedEvent,
     FeaturedImage,
     Newsletter,
     Sponsor,
     User,
     Venue,
)

import boto3

jobstores = {
    'default': SQLAlchemyJobStore(url=os.environ.get('DATABASE_URL').replace("postgres://", "postgresql://", 1))
}

AWS_ACCESS_KEY_ID = os.environ.get('AWS_KEY')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET')
AWS_S3_BUCKET_NAME = os.environ.get('AWS_BUCKET')

s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name='us-east-1'
)



def create_app():
     app = Flask(__name__)
     
     app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('RDS_DATABASE_URL').replace("postgres://", "postgresql://", 1)
     app.secret_key = 'your_secret_key'
     app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
     app.config['SQLALCHEMY_POOL_RECYCLE'] = 300
     app.config['SQLALCHEMY_POOL_TIMEOUT'] = 30
     app.config['SQLALCHEMY_POOL_SIZE'] = 10
     app.config['SQLALCHEMY_MAX_OVERFLOW'] = 5

     db.init_app(app)
     
     login_manager = LoginManager()
     login_manager.init_app(app)
     login_manager.login_view = 'login'

     
     @login_manager.user_loader
     def load_user(user_id):
        return User.query.get(int(user_id))
     
     migrate = Migrate(app, db)

     def is_admin(user):
         return user.is_authenticated and user.role == 'admin'

     def get_user_events(user_id):
         """
         Retrieves events associated with the given user.
         :param user_id: ID of the user whose events are to be retrieved.
         :return: List of event objects associated with the user.
         """
         events = Event.query.filter_by(user_id=user_id).all()
         return events

     def get_user_profile(user_id):
         """
         Retrieves profile information for the given user.
         :param user_id: ID of the user whose profile information is to be retrieved.
         :return: A user object containing the profile information.
         """
         user_profile = User.query.get(user_id)
         return user_profile



     def process_image(file_path, output_width=600, quality=85):
         """
         Resize an image based on a fixed width, maintaining aspect ratio.
         :param file_path: The path to the image.
         :param output_width: Desired width of the output image.
         :param quality: Quality of the output image (1-100).
         """
         with Image.open(file_path) as img:
             # Calculate new height to maintain aspect ratio
             aspect_ratio = img.height / img.width
             new_height = int(output_width * aspect_ratio)

             # Resize the image
             img = img.resize((output_width, new_height), Image.Resampling.LANCZOS)

             # Save the image with reduced quality
             img.save(file_path, optimize=True, quality=quality)

     
     def send_newsletter_email(newsletter):
         recipients = Email.query.with_entities(Email.email).all()  # Query all email addresses
         emails = [email[0] for email in recipients]  # Extract email addresses from query result
    
         # Define the sender with a name and email address
    
         for recipient in emails:
             message = Mail(
                 from_email=('events@themovenashville.com', 'The Move Nashville'),
                 to_emails=recipient,
                 subject=newsletter.subject,
                 html_content=newsletter.html_content)
             try:
                 sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
                 response = sg.send(message)
                 print(f"Sent to {recipient}: Status {response.status_code}")
             except Exception as e:
                 print(f"Error sending to {recipient}: {str(e)}")
    
         print("All emails sent.")

     def create_newsletter_content(base_url="https://themovenashville.com", event_id=None):
         # Fetch all upcoming events
         upcoming_events = Event.query.filter(Event.time_date >= datetime.utcnow()).order_by(Event.time_date).all()
         sponsors = Sponsor.query.all()
         featured_images = FeaturedImage.query.all()

         # Initialize themove_event
         themove_event = None

         # If a specific event_id is provided, find that event
         if event_id:
             themove_event = Event.query.get(event_id)
             if not themove_event:
                 raise ValueError("Event not found")

         # Render the newsletter template with all data
         html_content = render_template('newsletter_content.html',
                                        base_url=base_url,
                                        themove_event=themove_event,
                                        upcoming_events=upcoming_events,
                                        sponsors=sponsors,
                                        featured_images=featured_images)

         # Return HTML content along with event name and date, if applicable
         event_name = themove_event.name if themove_event else None
         event_date = themove_event.time_date.strftime('%Y-%m-%d') if themove_event else None

         return html_content, event_name, event_date

     def store_weekly_newsletter(app, event_id=None):
         with app.app_context():
             # Check if a specific event_id is provided
             if event_id:
                 featured_event = FeaturedEvent.query.filter_by(event_id=event_id, newsletter_created=False).first()
                 if not featured_event:
                     # Handle the case where the event is not found or already has a newsletter
                     print(f"No eligible event found for event_id {event_id}")
                     return
             else:
                 # Logic to find the next upcoming event that hasn't had a newsletter created
                 current_date = datetime.utcnow()
                 featured_event = FeaturedEvent.query.join(Event, FeaturedEvent.event_id == Event.id) \
                                                     .filter(Event.time_date >= current_date, FeaturedEvent.newsletter_created == False) \
                                                     .order_by(Event.time_date) \
                                                     .first()

             # Proceed if a suitable event is found
             if featured_event:
                 event = Event.query.get(featured_event.event_id)
                 if event:
                     html_content, event_name, event_date = create_newsletter_content(event_id=event.id)

                     # Format the subject line
                     if event_name and event_date:
                         formatted_event_date = datetime.strptime(event_date, '%Y-%m-%d').strftime('%m/%d/%Y')
                         subject = f"The Move: {event_name} {formatted_event_date}"
                     else:
                         subject = "Weekly Newsletter - {}".format(datetime.utcnow().strftime('%Y-%m-%d'))

                     # Create and add the new newsletter
                     new_newsletter = Newsletter(subject=subject, html_content=html_content)
                     db.session.add(new_newsletter)

                     try:
                         db.session.commit()
                         # Update featured_event's newsletter_created flag and link the newsletter
                         featured_event.newsletter_created = True
                         featured_event.newsletter_id = new_newsletter.id
                         db.session.commit()
                         print("Newsletter created and stored successfully.")
                     except SQLAlchemyError as e:
                         db.session.rollback()
                         print(f"Failed to add newsletter to database: {e}")
                 else:
                     print(f"No event found for the given featured_event {featured_event.id}")
             else:
                 print("No eligible upcoming event found for newsletter creation.")


     def send_daily_newsletter(app, newsletter_id=None):
         with app.app_context():
             if newsletter_id:
                 newsletter = Newsletter.query.get(newsletter_id)
             else:
                 newsletter = Newsletter.query.filter_by(sent=False).order_by(Newsletter.created_at.desc()).first()

             if newsletter:
                 send_newsletter_email(newsletter)
                 newsletter.sent = True
                 db.session.commit()

     @app.route('/account/newsletter', methods=['GET', 'POST'])
     @login_required
     def account_newsletter():
         if current_user.role != 'admin':
             flash('Access denied: Admins only.', 'danger')
             return redirect(url_for('account_profile'))

          # Fetch all featured events
         featured_events = FeaturedEvent.query.join(Event, FeaturedEvent.event_id == Event.id).all()

         return render_template('account/newsletter.html', section='newsletter', featured_events=featured_events)


     @app.route('/create-newsletter/<int:event_id>', methods=['POST'])
     @login_required
     def create_specific_newsletter(event_id):
         if not is_admin(current_user):
             flash('Access denied: Admins only.', 'danger')
             return redirect(url_for('account_profile'))

         try:
             store_weekly_newsletter(current_app._get_current_object(), event_id)
             flash('Newsletter created successfully for the event.', 'success')
         except Exception as e:
             flash('Error creating newsletter: ' + str(e), 'danger')

         return redirect(url_for('account_newsletter'))

     @app.route('/send-newsletter/<int:newsletter_id>', methods=['POST'])
     @login_required
     def send_specific_newsletter(newsletter_id):
         if not is_admin(current_user):
             flash('Access denied: Admins only.', 'danger')
             return redirect(url_for('account_profile'))

         try:
             send_daily_newsletter(current_app._get_current_object(), newsletter_id)
             flash('Newsletter sent successfully.', 'success')
         except Exception as e:
             flash('Error sending newsletter: ' + str(e), 'danger')

         return redirect(url_for('account_newsletter'))

     @app.route('/')
     def home():
         # Get the current date and time
         current_time = datetime.utcnow()

         # Query upcoming events that are in the future
         events = db.session.query(Event, Venue)\
                                     .join(Venue, Event.venue_id == Venue.id)\
                                     .filter(Event.time_date > current_time)\
                                     .order_by(Event.time_date)\
                                     .all()

         # Fetch featured events that are in the future and have the is_themove flag
         featured_events = FeaturedEvent.query\
                                         .join(Event, FeaturedEvent.event_id == Event.id)\
                                         .filter(Event.time_date > current_time, FeaturedEvent.is_themove == True)\
                                         .order_by(Event.time_date)\
                                         .all()

         form = EmailCaptureForm()
         return render_template('home.html', events=events, featured_events=featured_events, form=form)

     @app.route('/events/<slug>')
     def event_detail(slug):
         event = Event.query.filter_by(slug=slug).first_or_404()
         venue = Venue.query.get(event.venue_id)
         venue_slug = event.venue.slug  # Assuming that 'venue' is a backref from the Event model to a Venue model
         return render_template('event_detail.html', event=event, venue_slug=venue_slug, venue=venue)
    
     @app.route('/venues')
     def venue_list():
         venues = Venue.query.all()
         return render_template('venue_list.html', venues=venues)
     
     @app.route('/admin')
     @login_required
     def admin():
         # Ensure the user has the 'admin' role
         if current_user.role != 'admin':
             flash('You must be an admin to access this page.', 'danger')
             return redirect(url_for('home'))

         # Query to get all users, events, and venues for the admin dashboard
         users = User.query.all()
         events = Event.query.all()
         venues = Venue.query.all()

         return render_template('admin.html', users=users, events=events, venues=venues)
     
     @app.route('/register', methods=['GET', 'POST'])
     def register():
         email = request.args.get('email', None)
         form = RegistrationForm(email=email)
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
         form = LoginForm()
         if form.validate_on_submit():
             user = User.query.filter_by(email=form.email.data).first()
             if user and check_password_hash(user.password_hash, form.password.data):
                 login_user(user)

                 next_page = request.args.get('next')
                 # Check if next_page is relative and not an absolute URL
                 if not next_page or not next_page.startswith('/'):
                     next_page = url_for('home')
                 return redirect(next_page)
             else:
                 flash('Login Unsuccessful. Please check email and password', 'danger')

         return render_template('login.html', form=form)
    

     @app.route('/logout')
     def logout():
        logout_user()
        return redirect(url_for('home'))
     
     @app.route('/dashboard')
     @login_required
     def dashboard():
        return render_template('dashboard.html')

     @app.route('/edit-user/<int:user_id>', methods=['GET', 'POST'])
     @login_required  # Optional: if you want to restrict access
     def edit_user(user_id):
        user = User.query.get_or_404(user_id)

        if request.method == 'POST':
            user.name = request.form['name']
            user.email = request.form['email']
            # Add other fields as necessary
            db.session.commit()
            flash('User updated successfully.', 'success')
            return redirect(url_for('admin'))

        return render_template('edit_user.html', user=user)

     @app.route('/delete-user/<int:user_id>', methods=['POST'])
     @login_required  # Optional: if you want to restrict access
     def delete_user(user_id):
         user = User.query.get_or_404(user_id)
         db.session.delete(user)
         db.session.commit()
         flash('User deleted successfully.', 'success')
         return redirect(url_for('admin'))


     @app.route('/add-event', methods=['GET', 'POST'])
     @login_required
     def add_event():
         form = EventForm()
         if form.validate_on_submit():
             venue = Venue.query.get(form.venue_id.data)
             venue_slug = slugify(venue.name)
             event_slug = slugify(form.name.data)

             if form.image.data:
                 file = form.image.data
                 filename = secure_filename(file.filename)
                 s3_filepath = f'images/venues/{venue_slug}/{filename}'

                 # Ensure the temp directory exists
                 temp_dir = os.path.join(current_app.root_path, 'static/temp')
                 os.makedirs(temp_dir, exist_ok=True)

                 temp_path = os.path.join(temp_dir, filename)
                 file.save(temp_path)

                 # Optimize the image
                 process_image(temp_path, output_width=600, quality=85)

                 # Upload the optimized image to S3
                 with open(temp_path, 'rb') as optimized_img:
                     s3_client.upload_fileobj(
                         optimized_img,
                         AWS_S3_BUCKET_NAME,
                         s3_filepath
                
                     )

                 image_path = f'https://{AWS_S3_BUCKET_NAME}.s3.amazonaws.com/{s3_filepath}'

                 # Remove the temporary file
                 os.remove(temp_path)
             else:
                 image_path = None

             new_event = Event(
                 name=form.name.data,
                 slug=event_slug,
                 description=form.description.data,
                 time_date=form.time_date.data,
                 venue_id=form.venue_id.data,
                 user_id=current_user.id,
                 image_path=image_path
             )
             new_event.generate_slug()
             db.session.add(new_event)
             try:
                 db.session.commit()
                 flash('Event has been created successfully!', 'success')
             except SQLAlchemyError as e:
                 db.session.rollback()
                 flash('An error occurred. Event could not be added.', 'danger')
                 print(e)

             return redirect(url_for('home'))

         return render_template('add_event.html', form=form)

     @app.route('/venues/<string:venue_slug>')
     def venue_detail(venue_slug):
         venue = Venue.query.filter_by(slug=venue_slug).first_or_404()
         upcoming_events = Event.query.filter(Event.venue_id == venue.id, Event.time_date > datetime.utcnow()).order_by(Event.time_date).all()
         print("Upcoming Events:", upcoming_events)  # Debugging print statement
         return render_template('venue_detail.html', venue=venue, venue_slug=venue_slug, upcoming_events=upcoming_events)

 

     @app.route('/delete-venue/<int:venue_id>', methods=['POST'])
     @login_required
     def delete_venue(venue_id):
         venue = Venue.query.get_or_404(venue_id)
         db.session.delete(venue)
         db.session.commit()
         flash('Venue deleted successfully.', 'success')
         return redirect(url_for('admin'))



     @app.route('/capture-email', methods=['POST'])
     def capture_email():
         form = EmailCaptureForm()
         if form.validate_on_submit():
             email = Email(email=form.email.data)
             db.session.add(email)
             try:
                 db.session.commit()
                 flash('You have been successfully added to the list!', 'success')
             except SQLAlchemyError as e:
                 db.session.rollback()
                 flash('An error occurred. Email not added.', 'danger')
                 print(e)
             return redirect(url_for('register', email=form.email.data))
         return redirect(url_for('home'))

     @app.route('/newsletters')
     def list_newsletters():
         newsletters = Newsletter.query.order_by(Newsletter.created_at.desc()).all()
         return render_template('list_newsletters.html', newsletters=newsletters)

     @app.route('/newsletters/<int:newsletter_id>')
     def view_newsletter(newsletter_id):
         newsletter = Newsletter.query.get_or_404(newsletter_id)
         return render_template('view_newsletter.html', newsletter=newsletter)
     @app.route('/generate-newsletter', methods=['POST'])
     @login_required

     def generate_newsletter():
         # Ensure the user has the 'admin' role
         if current_user.role != 'admin':
             flash('You must be an admin to access this feature.', 'danger')
             return redirect(url_for('admin'))

         newsletter_content = create_newsletter_content()
         return render_template('display_newsletter.html', newsletter_content=newsletter_content)
     
     @app.route('/account', methods=['GET', 'POST'])
     @app.route('/account/profile', methods=['GET', 'POST'])
     @login_required
     def account_profile():
         profile_form = ProfileForm(obj=current_user)

         if profile_form.validate_on_submit():
             current_user.name = profile_form.name.data
             current_user.email = profile_form.email.data

             # Check if the updated email already exists
             existing_user = User.query.filter(User.email == profile_form.email.data, User.id != current_user.id).first()
             if existing_user:
                 flash('Email already in use by another account.', 'danger')
                 return redirect(url_for('account_profile'))

             # Commit changes to the database
             db.session.commit()
             flash('Your profile has been updated.', 'success')
             return redirect(url_for('account_profile'))

         return render_template('account/account.html', section='profile', profile_form=profile_form)

     @app.route('/account/my-events', methods=['GET'])
     @login_required
     def account_my_events():
         user_events = get_user_events(current_user.id)
         return render_template('account/account.html', section='my-events', events=user_events)


     @app.route('/edit-event/<int:event_id>', methods=['GET', 'POST'])
     @login_required
     def edit_event(event_id):
         event = Event.query.get_or_404(event_id)
         featured_event = FeaturedEvent.query.filter_by(event_id=event_id).first()
         venue = Venue.query.get(event.venue_id)

         if current_user.id != event.user_id and current_user.role != 'admin':
             flash('You are not authorized to edit this event.', 'danger')
             return redirect(url_for('account_my_events'))

         form = EventForm(obj=event)
         is_themove = featured_event.is_themove if featured_event else False

         if form.validate_on_submit():
             venue = Venue.query.get(form.venue_id.data)
             venue_slug = slugify(venue.name)
             event_slug = slugify(form.name.data)

             if form.image.data:
                 file = form.image.data
                 filename = secure_filename(file.filename)
                 s3_filepath = f'images/venues/{venue_slug}/{filename}'

                 # Ensure the temp directory exists
                 temp_dir = os.path.join(current_app.root_path, 'static/temp')
                 os.makedirs(temp_dir, exist_ok=True)

                 temp_path = os.path.join(temp_dir, filename)
                 file.save(temp_path)

                 # Optimize the image
                 process_image(temp_path, output_width=600, quality=85)

                 # Upload the optimized image to S3
                 with open(temp_path, 'rb') as optimized_img:
                     s3_client.upload_fileobj(
                         optimized_img,
                         AWS_S3_BUCKET_NAME,
                         s3_filepath
                     )

                 image_path = f'https://{AWS_S3_BUCKET_NAME}.s3.amazonaws.com/{s3_filepath}'

                 # Remove the temporary file
                 os.remove(temp_path)

                 # Update the image path in the database
                 event.image_path = image_path

             # Update other event details
             event.name = form.name.data
             event.description = form.description.data
             event.time_date = form.time_date.data
             event.venue_id = form.venue_id.data
             event.slug = event_slug

             # Admin-only: Update the 'is_themove' status for the featured event
             if current_user.role == 'admin':
                 is_themove_status = 'is_themove' in request.form and request.form.get('is_themove') == 'on'
                 if is_themove_status:
                     if featured_event:
                         featured_event.is_themove = True
                     else:
                         new_featured_event = FeaturedEvent(event_id=event.id, is_themove=True)
                         db.session.add(new_featured_event)
                 elif featured_event:
                     featured_event.is_themove = False

             db.session.commit()
             flash('Event updated successfully!', 'success')
             return redirect(url_for('account_my_events'))

         return render_template('account/edit_event.html', form=form, event=event, venue=venue, is_themove=is_themove)


     


     @app.route('/delete-event/<int:event_id>', methods=['POST'])
     @login_required
     def delete_event(event_id):
         event = Event.query.get_or_404(event_id)

         # Check if the event is featured and delete the reference
         FeaturedEvent.query.filter_by(event_id=event_id).delete()

         # Now delete the event
         db.session.delete(event)

         try:
             db.session.commit()
             flash('Event deleted successfully.', 'success')
         except SQLAlchemyError as e:
             db.session.rollback()
             flash('An error occurred. Event could not be deleted.', 'danger')
             print(e)

         return redirect(url_for('account_my_events'))  # or appropriate redirection

     @app.route('/account/change-password', methods=['GET', 'POST'])
     @login_required
     def change_password():
         form = ChangePasswordForm()
         if form.validate_on_submit():
             if check_password_hash(current_user.password_hash, form.old_password.data):
                 current_user.password_hash = generate_password_hash(form.new_password.data)
                 db.session.commit()
                 flash('Your password has been updated.', 'success')
                 return redirect(url_for('account_profile'))  # Redirect to a different page as needed
             else:
                 flash('Current password is incorrect.', 'danger')

         return render_template('account/change_password.html', form=form)

     @app.route('/add-venue', methods=['GET', 'POST'])
     @login_required
     def add_venue():
         form = VenueForm()
         if form.validate_on_submit():
             venue = Venue(
                 name=form.name.data,
                 city=form.city.data,
                 state=form.state.data,
                 zip=form.zip.data,
                 website=form.website.data,
                 instagram_handle=form.instagram_handle.data,
                 phone=form.phone.data,
                 address_1=form.address_1.data,
                 address_2=form.address_2.data,
                 user_id=current_user.id,
                 description=form.description.data

             )

             if form.image.data:
                 file = form.image.data
                 filename = secure_filename(file.filename)
                 venue_slug = slugify(venue.name)
                 s3_filepath = f'images/venues/{venue_slug}/{filename}'

                 # Save image temporarily for optimization
                 temp_path = os.path.join(current_app.static_folder, 'temp', filename)
                 file.save(temp_path)

                 # Process the image
                 process_image(temp_path)

                 # Upload the optimized file to S3
                 with open(temp_path, 'rb') as optimized_file:
                     s3_client.upload_fileobj(
                         optimized_file,
                         AWS_S3_BUCKET_NAME,
                         s3_filepath
                     )

                 # Set the S3 URL as the image path
                 venue.image_path = f'https://{AWS_S3_BUCKET_NAME}.s3.amazonaws.com/{s3_filepath}'

                 # Remove the temporary file
                 os.remove(temp_path)
             else:
                 venue.image_path = None

             venue.generate_slug()
             db.session.add(venue)
             try:
                 db.session.commit()
                 flash('Venue has been added successfully!', 'success')
             except SQLAlchemyError as e:
                 db.session.rollback()
                 flash('An error occurred. Venue could not be added.', 'danger')
                 print(e)

             return redirect(url_for('add_venue'))

         return render_template('add_venue.html', form=form)

     @app.route('/account/my-venues', methods=['GET'])
     @login_required
     def account_my_venues():
         user_venues = Venue.query.filter_by(user_id=current_user.id).all()
         return render_template('account/my_venues.html', venues=user_venues)
         
     @app.route('/edit-venue/<int:venue_id>', methods=['GET', 'POST'])
     @login_required
     def edit_venue(venue_id):
         venue = Venue.query.get_or_404(venue_id)
         if venue.user_id != current_user.id:
             flash('You are not authorized to edit this venue.', 'danger')
             return redirect(url_for('account_my_venues'))

         form = VenueForm(obj=venue)
         if form.validate_on_submit():
             # Process the image if it's updated
             if form.image.data:
                 file = form.image.data
                 filename = secure_filename(file.filename)
                 s3_filepath = f'images/venues/{venue.slug}/{filename}'

                 # Process the image
                 temp_path = os.path.join(current_app.static_folder, 'temp', filename)
                 file.save(temp_path)
                 process_image(temp_path)

                 # Upload the optimized image to S3
                 with open(temp_path, 'rb') as data:
                     s3_client.upload_fileobj(
                         data,
                         AWS_S3_BUCKET_NAME,
                         s3_filepath
                         )

                 # Remove the temporary file
                 os.remove(temp_path)

                 # Update the image path
                 venue.image_path = f'https://{AWS_S3_BUCKET_NAME}.s3.amazonaws.com/{s3_filepath}'

             # Update other venue details
             venue.name = form.name.data
             venue.address_1 = form.address_1.data
             venue.address_2 = form.address_2.data
             venue.city = form.city.data
             venue.state = form.state.data
             venue.zip = form.zip.data
             venue.phone = form.phone.data
             venue.website = form.website.data
             venue.instagram_handle = form.instagram_handle.data
             venue.description = form.description.data
             # ... update other fields as necessary ...

             db.session.commit()
             flash('Venue updated successfully!', 'success')
             return redirect(url_for('account_my_venues'))

         return render_template('account/edit_venue.html', form=form, venue=venue)

     @app.route('/account/all-events')
     @login_required
     def account_all_events():
         if not is_admin(current_user):
             flash('You must be an admin to access this page.', 'danger')
             return redirect(url_for('account_profile'))

         events = Event.query.all()
         return render_template('account/all_events.html', events=events)

     @app.route('/account/all-venues')
     @login_required
     def account_all_venues():
         if not is_admin(current_user):
             flash('You must be an admin to access this page.', 'danger')
             return redirect(url_for('account_profile'))

         venues = Venue.query.all()
         return render_template('account/all_venues.html', venues=venues)

     @app.route('/sitemap.xml')
     def sitemap():
         host_components = request.host.split('.')
         base_url = request.host_url
         if "localhost" not in host_components:
             base_url = "https://themovenashville.com"

         # Collect all URLs
         urls = []

         # Static routes
         urls.append(["/", "monthly", 1.0])
         urls.append(["/about", "yearly", 0.8])
         # Add more static URLs as needed

         # Dynamic routes (e.g., events, venues)
         events = Event.query.all()
         for event in events:
             url = f"/events/{event.slug}"
             urls.append([url, "weekly", 0.8])
         # Add other dynamic content like venues, etc.

         for venue in Venue.query.all():
             url = f"/venues/{venue.slug}"
             urls.append([url, "weekly", 0.8])

         xml_sitemap = render_template('sitemap_template.xml', base_url=base_url, urls=urls)
         response = make_response(xml_sitemap)
         response.headers["Content-Type"] = "application/xml"

         return response


     scheduler = APScheduler()
     scheduler.init_app(app)
     scheduler.start()
     scheduler.add_job(func=lambda: store_weekly_newsletter(app), trigger='interval', minutes=60, id='newsletter_job')
     #scheduler.add_job(func=lambda: store_weekly_newsletter(app), trigger='cron', day='*', id='newsletter_job')
     scheduler.add_job(func=lambda: send_daily_newsletter(app), trigger='interval', minutes=60, id='daily_newsletter_job')
     #scheduler.add_job(func=lambda: send_daily_newsletter(app), trigger='cron', day='*', id='daily_newsletter_job')

     return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', debug=True)