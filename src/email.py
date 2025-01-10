import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def script_handler(event, context):
    """
    The entry point for the SSM document execution.
    :param event: Dictionary containing input parameters from the SSM document.
    :param context: Contextual information provided by AWS Lambda/SSM.
    """
    # Retrieve parameters from the event
    relay_server = event.get('SMTPRelayServer', 'smtp-dummy:25')  # Replace with your SMTP server
    sender_email = event.get('SenderEmail', 'vinod.sms@dummy.com')  # Replace with sender email
    receiver_email = event.get('ReceiverEmail', 'vinod.dmd@dummy.com')  # Replace with recipient email
    cc_email = event.get('CCEmail', 'vinod.dmd@dummy.com')  # Replace with CC email if needed

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
        return {"status": "Email sent successfully"}
    except Exception as error:
        return {"status": "Error sending email", "error": str(error)}








try:
    account_id = job.get("AccountId", None)  # Default to None if AccountId is missing
    if not account_id:
        raise ValueError("AccountId is missing in the job data")
    if account_id != TARGET_ACCOUNT_ID:
        raise ValueError(f"Unexpected AccountId: {account_id}. Expected: {TARGET_ACCOUNT_ID}")
except Exception as e:
    logging.error(f"Error processing AccountId: {str(e)}\nJob Data: {job}\n{traceback.format_exc()}")
    raise  # Re-raise the exception to stop execution and propagate the error
