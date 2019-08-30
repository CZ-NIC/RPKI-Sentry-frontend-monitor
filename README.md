


## Deployment

* certificate realised by Let's Encrypt https://blog.miguelgrinberg.com/post/running-your-flask-application-over-https
* root crontab: 

```bash
43 6 * * * certbot renew --post-hook "systemctl reload nginx"
```

### MojeID

```
Xcurl --data '{"redirect_uris": "https://rpki-sentry.csirt.cz", "client_name": "RPKI Sentry"}' https://mojeid.cz/oidc/
```