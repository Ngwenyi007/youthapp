from flask_mail import Mail, Message
from threading import Thread
import os

# Initialize mail extension
mail = Mail()

def init_mail(app):
    """Initialize email service with app configuration"""
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    mail.init_app(app)

def send_welcome_email(recipient, name, code):
    """Send welcome email with member code"""
    msg = Message(
        "Your Membership Details",
        sender=os.getenv('MAIL_USERNAME'),
        recipients=[recipient]
    )
    msg.body = f"""
    Hello {name},
    
    Welcome to our community!
    
    Your member code: {code}
    Login at: http://yourdomain.org/login
    """
    
    # Send in background thread
    Thread(target=async_send_email, args=(msg,)).start()

def async_send_email(message):
    """Send email with proper app context"""
    with mail.app.app_context():
        mail.send(message)
