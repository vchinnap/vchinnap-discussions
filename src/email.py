import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_email():
    # SMTP configuration
    relay_server = 'smtp-dummy:25'  # Replace with your SMTP server
    sender_email = 'vinod.sms@dumm.com'  # Replace with your sender email
    receiver_email = 'vinod.dmd@dummy.com'  # Replace with the recipient email
    cc_email = 'vinod.dmd@dummy.com'  # Replace with CC email if needed

    # Email subject and body
    SUBJECT = "Test Email Notification from SMTP"
    BODY_TEXT = (
        "This is a test email sent via SMTP.\r\n"
        "If you received this email, the SMTP server is working properly.\r\n"
        "Regards,\r\n"
        "Test System"
    )

    # Create email message
    email_message = MIMEMultipart()
    email_message['From'] = sender_email
    email_message['To'] = receiver_email
    email_message['Cc'] = cc_email
    email_message['Subject'] = SUBJECT
    email_message.attach(MIMEText(BODY_TEXT, 'plain'))

    try:
        # Connect to SMTP server and send the email
        with smtplib.SMTP(relay_server) as server:
            server.sendmail(
                sender_email,
                [receiver_email, cc_email],
                email_message.as_string()
            )
        print("Email sent successfully")
    except Exception as error:
        print("Error sending email")
        print(error)

# Run the function for testing
if __name__ == "__main__":
    send_email()
