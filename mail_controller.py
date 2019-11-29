# def get_notification_text(user):
#     return tabulate((n.prefix, n.asn) for n in user.get_notifications())
#
#
# def send_verification(user):
#     subject = "RPKI Sentry confirmation"
#     text = """Somebody has just asked to send updates of current configs:
#             If that was you confirm
#
#             You can edit here: XXX
#
#             You can ignore if that was you.
#
#             """
#     s = get_notification_text(user)
#     if s:
#         text += f"In the past you've confirmed also following notifications: {s}"
#         # XX unsubscribe
#     msg_to = user.email
#     _send_email(msg_to, subject, text)
