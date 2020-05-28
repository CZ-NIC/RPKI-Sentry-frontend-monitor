# RPKI-Chronicle-frontend-monitor

Copyright (C) 2019-2020 CZ.NIC, z.s.p.o.

This module is part of RPKI-chronicle project -- web-based history keeper for
RPKI and BGP.

## Requirements/dependencies

* tabulate
* flask
* wtforms
* psycopg2
* flask-paginate
* sqlalchemy
* Flask-SQLAlchemy
* flask_session
* redis
* flask-debugtoolbar
* envelope

## Deployment

* DB engine is needed, preferrably PostgreSQL 12.1
* WSGI can be deployed and exposed by various methods, peferrably with NGINX 1.16.1
* The local RIPE NCC RPKI Validator or remotely-accessed validator is needed. See
readme file for RIPE NCC RPKI Validator connector.

