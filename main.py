import os
from datetime import datetime

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, current_app, flash, redirect, render_template, request, url_for
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

jobstores = {
    'default': SQLAlchemyJobStore(url=os.environ.get('DATABASE_URL').replace("postgres://", "postgresql://", 1))
}

AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_S3_BUCKET_NAME = os.environ.get('AWS_S3_BUCKET_NAME')


def create_app():
     app = Flask(__name__)
     
     app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace("postgres://", "postgresql://", 1)
     app.secret_key = 'your_secret_key'
     app.config['SQLALCHEMY_POOL_RECYCLE'] = 600

     db.init_app(app)
     
     login_manager = LoginManager()
     login_manager.init_app(app)
     login_manager.login_view = 'login'

     
     @login_manager.user_loader
     def load_user(user_id):
        return User.query.get(int(user_id))
     
     migrate = Migrate(app, db)

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
         message = Mail(
             from_email='events@themovenashville.com',
             to_emails='blakeurmos@gmail.com',
             subject=newsletter.subject,
             html_content=newsletter.html_content)
         try:
             sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
             response = sg.send(message)
             print(response.status_code)
             print(response.body)
             print(response.headers)
         except Exception as e:
             print(e.message)

     def create_newsletter_content(base_url="https://themove.admin270.repl.co"):
         # Query to get the nearest future 'themove_event' that hasn't had a newsletter created
         current_date = datetime.utcnow()
         featured_event_record = FeaturedEvent.query.join(Event, FeaturedEvent.event_id == Event.id)\
                                                     .filter(Event.time_date >= current_date, FeaturedEvent.newsletter_created == False)\
                                                     .order_by(Event.time_date)\
                                                     .first()
    
         themove_event = None
         venue_slug = 'default'
         event_name = None
         event_date = None
    
         if featured_event_record:
             themove_event = Event.query.get(featured_event_record.event_id)
             if themove_event:
                 event_name = themove_event.name
                 event_date = themove_event.time_date.strftime('%Y-%m-%d')
                 if themove_event.venue:
                     venue_slug = themove_event.venue.slug
    
         # Query for upcoming events, sponsors, and featured images
         upcoming_events = Event.query.filter(Event.time_date >= datetime.utcnow()).order_by(Event.time_date).all()
         sponsors = Sponsor.query.all()
         featured_images = FeaturedImage.query.all()
    
         # Render the template
         html_content = render_template('newsletter_content.html',
                                        base_url=base_url,
                                        themove_event=themove_event,
                                        venue_slug=venue_slug,
                                        upcoming_events=upcoming_events,
                                        sponsors=sponsors,
                                        featured_images=featured_images)
    
         return html_content, event_name, event_date
     
     def store_weekly_newsletter(app):
         with app.app_context():
             # Get the nearest future 'themove_event' that hasn't had a newsletter created
             current_date = datetime.utcnow()
             featured_event = FeaturedEvent.query.join(Event, FeaturedEvent.event_id == Event.id)\
                                                 .filter(Event.time_date >= current_date, FeaturedEvent.newsletter_created == False)\
                                                 .order_by(Event.time_date)\
                                                 .first()

             if featured_event:
                 html_content, event_name, event_date = create_newsletter_content()

                 # Format the subject line
                 if event_name and event_date:
                     formatted_event_date = datetime.strptime(event_date, '%Y-%m-%d').strftime('%m/%d/%Y')
                     subject = f"The Move: {event_name} {formatted_event_date}"
                 else:
                     subject = "Weekly Newsletter - {}".format(datetime.utcnow().strftime('%Y-%m-%d'))

                 new_newsletter = Newsletter(subject=subject, html_content=html_content)
                 db.session.add(new_newsletter)
                 try:
                     db.session.commit()
                     # Update featured_event's newsletter_created flag
                     featured_event.newsletter_created = True
                     db.session.commit()
                 except SQLAlchemyError as e:
                     db.session.rollback()
                     print("Failed to add newsletter to database.", e)


     def send_daily_newsletter(app):
         with app.app_context():
             newsletter = Newsletter.query.filter_by(sent=False).order_by(Newsletter.created_at.desc()).first()
             if newsletter:
                 send_newsletter_email(newsletter)
                 newsletter.sent = True  # Mark as sent
                 db.session.commit()
                 
     @app.route('/')
     def home():
         events = db.session.query(Event, Venue).join(Venue, Event.venue_id == Venue.id).all()
         form = EmailCaptureForm()
         return render_template('home.html', events=events, form=form)

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
                 filename = secure_filename(form.image.data.filename)
                 directory_path = os.path.join(current_app.static_folder, 'images/venues', venue_slug)
                 if not os.path.exists(directory_path):
                     os.makedirs(directory_path)

                 filepath = os.path.join(directory_path, filename)
                 form.image.data.save(filepath)

                 # Process the image
                 process_image(filepath)

                 image_path = filename
             else:
                 image_path = None

             new_event = Event(
                 name=form.name.data,
                 slug=event_slug,
                 description=form.description.data,
                 time_date=form.time_date.data,
                 venue_id=form.venue_id.data,
                 user_id=current_user.id,
                 image_path=image_path  # Save the filename here
             )
             new_event.generate_slug()
             db.session.add(new_event)
             try:
                 db.session.commit()
                 flash('Event has been created successfully!', 'success')
                 return redirect(url_for('home'))
             except SQLAlchemyError as e:
                 db.session.rollback()
                 flash('An error occurred. Event could not be added.', 'danger')
                 print(e)

         return render_template('add_event.html', form=form)
     
     @app.route('/venues/<string:venue_slug>')
     def venue_detail(venue_slug):
         venue = Venue.query.filter_by(slug=venue_slug).first_or_404()
         upcoming_events = Event.query.filter(Event.venue_id == venue.id, Event.time_date > datetime.utcnow()).order_by(Event.time_date).all()
         print("Upcoming Events:", upcoming_events)  # Debugging print statement
         return render_template('venue_detail.html', venue=venue, venue_slug=venue_slug, upcoming_events=upcoming_events)

     @app.route('/edit-venue/<int:venue_id>', methods=['GET', 'POST'])
     @login_required
     def edit_venue(venue_id):
         venue = Venue.query.get_or_404(venue_id)

         if request.method == 'POST':
             venue.name = request.form['name']
             # Update other venue fields as needed
             db.session.commit()
             flash('Venue updated successfully.', 'success')
             return redirect(url_for('admin'))

         return render_template('edit_venue.html', venue=venue)

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
         venue = Venue.query.get(event.venue_id)

         if current_user.id != event.user_id and current_user.role != 'admin':
             flash('You are not authorized to edit this event.', 'danger')
             return redirect(url_for('account_my_events'))

         form = EventForm(obj=event)
         if form.validate_on_submit():
             venue = Venue.query.get(form.venue_id.data)
             venue_slug = slugify(venue.name)
             event_slug = slugify(form.name.data)

             if form.image.data:
                 filename = secure_filename(form.image.data.filename)
                 directory_path = os.path.join(current_app.static_folder, 'images/venues', venue_slug)
                 if not os.path.exists(directory_path):
                     os.makedirs(directory_path)

                 filepath = os.path.join(directory_path, filename)
                 form.image.data.save(filepath)

                 # Process the image
                 process_image(filepath)

                 # Update the image path correctly
                 event.image_path = os.path.join(filename)

             # Update other event details
             event.name = form.name.data
             event.description = form.description.data
             event.time_date = form.time_date.data
             event.venue_id = form.venue_id.data
             event.slug = event_slug

             db.session.commit()
             flash('Event updated successfully!', 'success')
             return redirect(url_for('account_my_events'))

         return render_template('account/edit_event.html', form=form, event=event, venue=venue)

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
                 address_2=form.address_2.data
             )

             if form.image.data:
                 filename = secure_filename(form.image.data.filename)
                 venue_slug = slugify(venue.name)
                 filepath = os.path.join(current_app.static_folder, 'images/venues', venue_slug, filename)
                 form.image.data.save(filepath)
                 venue.image_path = os.path.join('images/venues', venue_slug, filename)

                 # Process the image
                 process_image(filepath)

             venue.generate_slug()
             db.session.add(venue)
             try:
                 db.session.commit()
                 flash('Venue has been added successfully!', 'success')
                 return redirect(url_for('add_venue'))
             except SQLAlchemyError as e:
                 db.session.rollback()
                 flash('An error occurred. Venue could not be added.', 'danger')
                 print(e)

         return render_template('add_venue.html', form=form)

     scheduler = APScheduler()
     scheduler.init_app(app)
     scheduler.start()
     #scheduler.add_job(func=lambda: store_weekly_newsletter(app), trigger='interval', minutes=1, id='newsletter_job')
     scheduler.add_job(func=lambda: store_weekly_newsletter(app), trigger='cron', day='*', id='newsletter_job')
     #scheduler.add_job(func=lambda: send_daily_newsletter(app), trigger='interval', minutes=1, id='daily_newsletter_job')
     scheduler.add_job(func=lambda: send_daily_newsletter(app), trigger='cron', day='*', id='daily_newsletter_job')

     return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', debug=True)