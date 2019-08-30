import smtplib
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid, formatdate

from tabulate import tabulate


# def _send_email(msg_to, subject, text, send=False):
#     msg = MIMEText(text)
#     msg_from = "rpki-sentry@csirt.cz"
#     msg["To"] = msg_to
#     msg["From"] = msg_from
#     msg["Subject"] = subject
#     msg["Message-ID"] = make_msgid()
#     s = smtplib.SMTP("mailer")
#     s.sendmail(msg_from, msg_to, msg.as_string())

def _sign(self, s):
    try:
        return str(self.parameters.gpg.sign(s, default_key=self.parameters.gpgkey, detach=True, clearsign=False,
                                            passphrase=self.parameters.gpgpass))
    except:
        return ""


def build_mail(email_to, subject, text, smtp=None, send=False):
    """ creates a MIME message
    :param mail: Mail object
    :param send: True to send through SMTP, False for just printing the information
    :param override_to: Use this e-mail instead of the one specified in the Mail object
    :return: True if successfully sent.

    """
    email_from = "rpki-sentry@csirt.cz"
    recipients = [email_to]

    if send is True:
        base_msg = MIMEMultipart()
        base_msg.attach(MIMEText(text, "html", "utf-8"))
        gpg = None  # XX
        if gpg:
            msg = MIMEMultipart(_subtype="signed", micalg="pgp-sha1", protocol="application/pgp-signature")
            s = base_msg.as_string().replace('\n', '\r\n')
            signature = _sign(s)

            if not signature:
                print("Failed to sign the message for {}".format(email_to))
                return False
            signature_msg = Message()
            signature_msg['Content-Type'] = 'application/pgp-signature; name="signature.asc"'
            signature_msg['Content-Description'] = 'OpenPGP digital signature'
            signature_msg.set_payload(signature)
            msg.attach(base_msg)
            msg.attach(signature_msg)
        else:
            msg = base_msg

        msg["From"] = email_from
        msg["Subject"] = subject
        msg["To"] = email_to
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()
        smtp.sendmail(email_from, recipients, msg.as_string().encode('ascii'))
        return True
    else:
        print('To: {}; Subject: {}; Body: {} '.format(email_to, subject, text))
        return None


# def notify(user, conflicts):
#
#
#     import ipdb;
#     ipdb.set_trace()
    # XX
    # Celkem sledujete tyto radky:
    # + get_notification_text
    # unsubscribe nebo změna proběhne tam
    # ... _send_email()
    # mail history uloz radek s current_btimestamp
    # pass

# def get_notification_text(user):
#     return tabulate((n.prefix, n.asn) for n in user.get_notifications())
#
#
# def send_verification(user):
#     subject = "RPKI Sentry confirmation"
#     text = """Somebody has just asked to send updates of current configs:
#
#             XXX
#
#             If that was you confirm
#
#             XXX
#
#             (From z dřívějška, máte výpis i na tyhle
#
#             Editovat můžete zde: XXX
#
#             You can ignore if that wasn't you.
#
#             """
#
#     s = get_notification_text(user)
#     if s:
#         text += f"In the past you've confirmed also following notifications: {s}"
#         # XX unsubscribe
#     msg_to = user.email
#     _send_email(msg_to, subject, text)
