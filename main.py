#!/usr/bin/env python3
import datetime
import logging
import smtplib
import sys
from collections import defaultdict
from itertools import zip_longest

import requests
from envelope import envelope
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory, flash, session
from flask_debugtoolbar import DebugToolbarExtension
from flask_oidc import OpenIDConnect
from flask_paginate import Pagination
from flask_session import Session  # new style
from flask_wtf import FlaskForm
from sqlalchemy import or_, and_
from sqlalchemy.exc import DataError
from wtforms import StringField, SelectMultipleField

from models import PrefixAsn, Conflict, Notification, User, db, MailHistory

# setup logging
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(message)s'))
console_handler.setLevel(logging.INFO)
file_handler = logging.FileHandler("rpki_chronicle.log")
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
file_handler.setLevel(logging.INFO)  # XX CHANGE to WARNING
logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler])
logger = logging.getLogger(__name__)


app = Flask(__name__)

HOSTNAME = "https://rpki-chronicle.csirt.cz/"
# App config.
# DEBUG = True
SESSION_TYPE = 'sqlalchemy'
SECRET_KEY = '7d441f27d441f27567d441f2b6176a'
SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg2://rpki_chronicle:ze29dnxE5sCuV39@localhost/rpki_chronicle'
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ECHO = True

# DEBUG = True
# OIDC_CLIENT_SECRETS = '/var/www/html/client_secrets_debug.json'
OIDC_CLIENT_SECRETS = '/var/www/html/client_secrets.json'
OIDC_ID_TOKEN_COOKIE_SECURE = False
OIDC_REQUIRE_VERIFIED_EMAIL = False
#OIDC_OPENID_REALM = 'https://rpki-chronicle.csirt.cz:5002/oidc_callback' # XX why is here port 5002?
OIDC_OPENID_REALM = 'https://rpki-chronicle.csirt.cz/oidc_callback' # XX why is here port 5002?

DEBUG_TB_INTERCEPT_REDIRECTS = False

app.config.from_object(__name__)

oidc = OpenIDConnect(app)


@app.context_processor
def inject_user():
    return dict(is_logged=oidc.user_loggedin, user=User.himself)


""":type: sqlalchemy.orm"""
toolbar = DebugToolbarExtension(app)
Session(app)
db.init_app(app)


class SearchForm(FlaskForm):
    asn = StringField('ASN')
    cidr = StringField('CIDR')
    cc = SelectMultipleField('Country')
    cc_not = SelectMultipleField('Exclude')


# @app.route('/oidc_callback')
# @oidc.custom_callback
# def callback(data):
#     return 'Hello. You submitted %s' % data


@app.route('/test')
def index():
    if oidc.user_loggedin:
        import ipdb;
        ipdb.set_trace()
        return 'Welcome %s' % oidc.user_getfield('email')
    else:
        return 'Not logged in <a href="login">login</a>'


@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico', mimetype='image/x-icon')


@app.route('/login')
@oidc.require_login
def login():
    User.pairing(oidc.user_getfield('email'), oidc.user_getfield('sub'))
    print("*************** login", oidc.user_getfield('email'), oidc.user_getfield('sub'))  # #15
    return redirect(url_for('notifications'))


@app.route('/logout')
def logout():
    try:
        del session["user_id"]
    except KeyError:
        pass
    oidc.logout()
    return redirect(url_for('search'))


@app.route("/charts")
def charts():
    o_lab, o_1 = zip(*db.engine.execute('select status,count(*) from conflict where "end" is null group by status'))
    o_lab = (status_2_word(x) for x in o_lab)
    h_lab, h_1, h_2 = zip(*db.engine.execute(
        'select ts,sum(case when status = 16 then 1 else 0 end) asnconflict, sum(case when status = 17 then 1 else 0 end) pfxlenconflict from seen_tables inner join conflict on (ts > start and (ts < "end" or "end" is null)) group by ts order by ts asc'))
    h_lab = (str(x.date()) for x in h_lab)
    return render_template('charts.html', h_lab=h_lab, h_1=h_1, h_2=h_2, o_lab=o_lab, o_1=o_1)


@app.route("/notifications", methods=['GET', 'POST'])
def notifications():
    user = User.himself()
    if request.method == 'POST':
        # user.email = request.form.get("email")
        db.session.add(user)
        for n_id, prefix, asn, ccs in zip_longest(request.form.getlist("id[]"),
                                                  request.form.getlist("prefix[]"),
                                                  request.form.getlist("asn[]"),
                                                  request.form.getlist("ccs[]")):
            if n_id:
                notification = db.session.query(Notification).filter(Notification.id == n_id,
                                                                     Notification.user_id == user.id).first()
                if not notification:
                    print("not found", n_id)
                    return jsonify({"success": False, "message": f"Couldn't find notification {n_id}"})
                if not prefix and not asn and not ccs:  # remove or update
                    db.session.delete(notification)
                    continue
                print("found", notification.id)
            else:  # create new
                print("creating new")
                notification = Notification()
                notification.user_id = user.id
            notification.prefix = prefix or None
            notification.asn = asn or None
            notification.ccs = ccs or None
            db.session.add(notification)
        try:
            db.session.commit()
        except DataError:
            flash("Invalid data", "error")
        else:
            flash("Saved", "success")

        # if not user.confirmed_time:
        #     send_verification(user)

    #     return jsonify({"success": True, "message": "Message sent"})
    # else:
    query = user.get_notifications()
    return render_template('notifications.html', data=query.all(), user=user)


@app.route("/add", methods=['GET', 'POST'])
def add():
    asn = request.args.get('asn')
    prefix = request.args.get('cidr')
    ccs = request.args.getlist('ccs')
    n = Notification()
    if asn and asn != 'None':
        n.asn = asn
    if prefix and prefix != 'None':
        n.prefix = prefix
    if ccs and ccs != 'None':
        n.ccs = ",".join(ccs)
    n.user_id = User.himself(False)
    db.session.add(n)
    try:
        db.session.commit()
    except DataError:
        return jsonify({"success": False, "message": "Invalid data"})
    return jsonify({"success": True})


@app.route("/", methods=['GET', 'POST'])
@app.route("/search", methods=['GET', 'POST'])
@app.route("/search/<int:page>", methods=['GET'])
def search(page=1):
    if "bgpsec.labs.nic.cz" in request.headers['Host']:  # service should not be available through bgpsec anymore
        return redirect(HOSTNAME)

    asn = request.args.get('asn')
    cidr = request.args.get('cidr')
    cc = request.args.getlist('cc')
    cc_not = request.args.getlist('cc_not')

    form = SearchForm(asn=asn, cidr=cidr, cc=cc, cc_not=cc_not)
    data = pagination = None

    per_page = 10

    query = db.session.query(PrefixAsn, Conflict) \
        .join(Conflict, Conflict.prefix_asn_id == PrefixAsn.id)
    if asn:
        query = query.filter(PrefixAsn.asn == asn)
    if cidr:
        query = query.filter(PrefixAsn.prefix.op("<<=")(cidr))
    if cc:
        query = query.filter(PrefixAsn.cc.in_(cc))
    if cc_not:
        query = query.filter(PrefixAsn.cc.notin_(cc_not))
    try:
        query = query.paginate(page, per_page, error_out=False)
    except DataError:
        flash("Data error. Has CIDR correct form?", "warning")
    else:
        pagination = Pagination(**query.__dict__, css_framework="bootstrap4")
        data = query.items  # .all()

    date_from = db.engine.execute("select min(ts) from seen_tables").fetchone()[0]
    date_to = db.engine.execute("select max(ts) from seen_tables").fetchone()[0]
    form.cc_not.choices = form.cc.choices = [(x[0], x[0].upper()) for x in
                                             db.engine.execute("select cc from prefix_asn where cc is not null group by cc")]

    return render_template('search.html', form=form, data=data, date_from=date_from, date_to=date_to,
                           pagination=pagination)


@app.template_filter('split')
def split(value, char=','):
    if not value:
        return []
    return value.split(char)


@app.template_filter('status')
def status_2_word(s):
    try:
        key = {0: "ROA missing",
               1: "ROA valid",
               # 2: "ROA invalid but passing",
               # 16: "prefix/ROA conflict (origin)",
               # 17: "prefix/ROA conflict (prefix length)"}[s]
               2: "origin",
               3: "prefix length"}[s]
    except KeyError:
        key = "N/A"
    return key


if __name__ == "__main__":
    if "process" in sys.argv:
        #  * load country codes for new prefixes
        #  * loop all notification and search for conflicts/asn subprefix relates to notification/asn superprefix
        #  * send notification e-mails
        #  * todo: XXregenerate chart sources (for chartjs)
        #  * todo: XXremove older than six months from DB?
        no_countries = "mails" in sys.argv  # for debug

        app.app_context().push()
        db.engine.echo = False  # turn off default stdout logging
        last_check = db.session.execute("select progress_time from state where id = '1'").fetchone()[0]
        if not last_check:
            # fallback is the oldest date we know
            last_check = db.engine.execute("select min(ts) from seen_tables").fetchone()[0]
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # add missing country codes
        prefix_asn_newly_fetched = []
        if not no_countries:
            CONVEY_URL = "http://127.0.0.1:26683/?q={}&field=country"

            # not having country code set, start with new ID (don't get stuck with an erroneous whois-records from last time)
            # XX what if an IP change its country after few months?
            q = db.session.query(PrefixAsn) \
                .filter(PrefixAsn.cc == None) \
                .order_by(PrefixAsn.id.desc())
            for i, prefix_asn_ in enumerate(q.all()):
                url = CONVEY_URL.format(prefix_asn_.prefix)
                r = requests.get(url=url, timeout=310)
                cc = r.json()["country"]
                if cc:
                    if len(cc) == 2:
                        prefix_asn_.cc = cc
                        prefix_asn_newly_fetched.append(prefix_asn_.id)
                    else:
                        print("Wrong cc length:", prefix_asn_.prefix, cc)
                print(url, prefix_asn_.cc)
                if i % 10 == 9:
                    print("Comitting")
                    db.session.commit()
            db.session.commit()

        # build the query that checks if there exists a new conflicts we should be told about
        conflicts = defaultdict(list)  # [email] => [conflicts...]

        # condition
        conditions = [Conflict.end > last_check, Conflict.start > last_check]  # must be new
        if prefix_asn_newly_fetched:  # some old conflicts might be updated
            # This prefixes could be processed in the past and skipped because country code has not been known
            # Since it is known now, notify about it eve if it was processed before than last check.
            conditions.append(and_(PrefixAsn.id.in_(prefix_asn_newly_fetched), Notification.ccs.isnot(None)))
        query = (db.session.query(PrefixAsn, Conflict, Notification, User)
                 .join(Conflict, Conflict.prefix_asn_id == PrefixAsn.id)
                 .join(Notification, and_(
            # map conflicts to notification if all conditions are met
            or_(Notification.prefix.is_(None), PrefixAsn.prefix.op("<<=")(Notification.prefix)),
            or_(Notification.asn.is_(None), PrefixAsn.asn == Notification.asn),
            or_(Notification.ccs.is_(None), PrefixAsn.cc.contains(Notification.ccs))
        ))
                 .join(User, User.id == Notification.user_id)
                 .filter(User.email.isnot(None))  # there must be an e-mail to send it to
                 .filter(or_(*conditions))  # conflict must be new or country-updated
                 )
        for row in query.all():
            conflicts[row.User.id].append((row.Notification, row.PrefixAsn, row.Conflict, row.User))

        # send e-mails
        smtp_server = "localhost"
        if conflicts:  # notify user
            with smtplib.SMTP(smtp_server) as smtp:
                for items in conflicts.values():
                    # notify(user_id, conflicts)
                    res = []
                    for notification, prefix_asn, conflict, user in items:
                        l = []
                        if notification.asn:
                            l.append(f"Watched ASN: {notification.asn}<br>")
                        if notification.prefix:
                            l.append(f"Watched prefix: {notification.prefix}<br>")
                        if notification.ccs:
                            l.append(f"Watched countries: {notification.ccs}<br>")
                        l.append(f"Matched prefix: {prefix_asn.prefix}<br>"
                                 f"Conflict start: {conflict.start}<br>"
                                 f"Conflict end: {conflict.end}<br>")
                        res.append("".join(l))

                    body = "<br>----<br>".join(res)
                    body += f"<br><br>Go to <a href={HOSTNAME}/notifications>notification</a> page to edit notification."

                    mail = (envelope()
                            .sender("rpki-chronicle@csirt.cz")
                            .to(user.email)
                            #.to("edvard.rejthar+test@nic.cz")
                            .subject("RPKI Chronicle notification")
                            .smtp("smtp.ini")
                            .message(body)
                            .signature()
                            .send(True))
                    # XX add unsubscribe link
                    logger.info(str(mail))  # XX maybe remove this logging and add a some statistics year-mail-count+1

                    if mail:
                        # make a note to the DB that we've sent this mail
                        db.session.merge(MailHistory(user_id=user.id, timestamp=now))
                    else:
                        logger.error(f"Mail not sent {user.email}, body: {body}")

        logger.info("done") # XXX remove this
        db.session.execute("update state SET progress_time = '" + now + "' where id = '1' ")
        db.session.commit()
    else:
        app.run()
