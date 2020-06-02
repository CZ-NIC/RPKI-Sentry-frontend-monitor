# coding: utf-8
import datetime
import logging

from flask import session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import BigInteger, Integer, PrimaryKeyConstraint, MetaData, ForeignKey, SmallInteger, DateTime, \
    TIMESTAMP, Boolean, Text, func, CHAR
from sqlalchemy.dialects.postgresql.base import CIDR
from sqlalchemy.schema import FetchedValue

db = SQLAlchemy()
logger = logging.getLogger(__name__)

metadata = MetaData()


# Conflict = Table(
#     'conflict', metadata,
#     Column('prefix_asn_id', ForeignKey('prefix_asn.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False, index=True),
#     Column('status', SmallInteger, nullable=False)
#     # db.Column('start', db.DateTime, nullable=False),
#     # db.Column('end', db.DateTime)
# )

# prefixAsn = db.Table(
#     'prefix_asn', metadata,
#     db.Column(Integer, primary_key=True, server_default=FetchedValue()),
#     db.Column(PREFIX, nullable=False),
#     db.Column(BigInteger, nullable=False)
# )


# t_conflict = db.Table(
#     'conflict',
#     db.Column('prefix_asn_id', db.ForeignKey('prefix_asn.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False, index=True),
#     db.Column('status', db.SmallInteger, nullable=False),
#     db.Column('start', db.DateTime, nullable=False),
#     db.Column('end', db.DateTime)
# )
#
# prefixAsn = db.Table(
#     'prefix_asn',
#     db.Column(Integer, primary_key=True, server_default=FetchedValue()),
#     db.Column(PREFIX, nullable=False),
#     db.Column(BigInteger, nullable=False)
# )

# db.Model = Base= declarative_base()


class User(db.Model):
    __tablename__ = 'user'
    __table_args__ = {'sqlite_autoincrement': True}
    id = db.Column('id', Integer, primary_key=True)
    # , autoincrement=True, server_default=FetchedValue()
    email = db.Column(Text)
    confirmed_time = db.Column(TIMESTAMP)
    created_time = db.Column(TIMESTAMP, server_default=func.now())
    token = db.Column(db.VARCHAR)
    token_time = db.Column(TIMESTAMP, comment="Token will expire")
    sub = db.Column(db.VARCHAR)

    @staticmethod
    def himself(orm=True):
        """ Returns ID or whole user object.
        :rtype: sqlalchemy.orm
        """
        u = None
        if "user_id" in session:
            u = db.session.query(User).filter(User.id == session["user_id"]).first() if orm else session["user_id"]

        if not u:  # session not set or pointing to a deleted user-row
            since = datetime.datetime.now() - datetime.timedelta(minutes=7)
            wastable_user = db.session.query(User).filter(User.created_time < since).filter(User.email.is_(None)).first()
            id_ = None
            if wastable_user:
                id_ = wastable_user.id
                db.session.delete(wastable_user)
                db.session.commit()

            u = User()
            if id_:
                u.id = id_
            db.session.add(u)
            db.session.commit()
            session["user_id"] = u.id
            if not orm:
                u = u.id
        return u

    @staticmethod
    def pairing(email, sub):
        user = db.session.query(User).filter(User.sub == sub).first()
        if user:
            session["user_id"] = user.id
            # XX here we should merge old non-logged session user to the new one if case of some settings
        else:
            user = User.himself()
            user.sub = sub
        if email:
            user.email = email
        else:  # all this statement should disappear - see #15
            user.email = email
            print("*"*100)
            print("************ No e-mail got from MojeID!")  # I couldn't debug why this happens on production server
            logger.error("************ No e-mail got from MojeID!")
            logger.error(user.id)
            # import ipdb; ipdb.set_trace()
            if not user.email:
                print("!!!!!!!!!!!! No user e-mail at all :(")
                logger.error("!!!!!!!!!!!! No user e-mail at all :(")
        db.session.commit()

    def get_notifications(self):
        return db.session.query(Notification).filter(Notification.user_id == self.id)

    def get_email(self):
        return self.email


class Notification(db.Model):
    __tablename__ = 'notification'
    id = db.Column('id', Integer, primary_key=True)
    user_id = db.Column('user_id', ForeignKey('user.id', ondelete='CASCADE', onupdate='CASCADE'))
    prefix = db.Column('prefix', CIDR, nullable=True)
    asn = db.Column('asn', BigInteger, nullable=True)
    ccs = db.Column('ccs', Text, nullable=True)
    enabled = db.Column('enabled', Boolean, nullable=False, server_default='0')




class MailHistory(db.Model):
    __tablename__ = 'mail_history'
    user_id = db.Column('user_id', ForeignKey('user.id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True)
    timestamp = db.Column('timestamp', TIMESTAMP)
    conflict_count = db.Column('conflict_count', Integer)




class Conflict(db.Model):
    __tablename__ = 'conflict'
    __table_args__ = (
        PrimaryKeyConstraint('prefix_asn_id', 'status', 'start', 'end'),
    )
    prefix_asn_id = db.Column('prefix_asn_id', db.ForeignKey('prefix_asn.id', ondelete='CASCADE', onupdate='CASCADE'),
                              nullable=False, index=True)
    status = db.Column('status', SmallInteger, nullable=False)
    start = db.Column('start', DateTime, nullable=False, default=None)
    end = db.Column('end', DateTime)


class PrefixAsn(db.Model):
    __tablename__ = 'prefix_asn'
    id = db.Column(Integer, primary_key=True, server_default=FetchedValue())
    prefix = db.Column(CIDR, nullable=False)
    asn = db.Column(BigInteger, nullable=False)
    cc = db.Column(CHAR, nullable=True)
    conflicts = db.relationship('Conflict', backref=__tablename__, lazy=True)

# engine = create_engine("postgresql+psycopg2://rpki_chronicle:fjife76fHFDj8@localhost/rpki_chronicle", echo=True)
# Base.metadata.create_all(engine)
# import ipdb; ipdb.set_trace()
