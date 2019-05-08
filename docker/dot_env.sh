#!/bin/bash

cat >/opt/openedgar/lexpredict_openedgar/.env << EOF
DATABASE_URL=$DATABASE_URL
CELERY_BROKER_URL=$CELERY_BROKER_URL
CELERY_RESULT_BACKEND=$CELERY_RESULT_BACKEND
CELERY_RESULT_PERSISTENT=$CELERY_RESULT_PERSISTENT
DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY

# Domain name, used by caddy
#DOMAIN_NAME=domain.com

# General settings
# DJANGO_READ_DOT_ENV_FILE=True
# CLIENT_TYPE: AKS, ADLAKE, Local
CLIENT_TYPE=$CLIENT_TYPE


DJANGO_ADMIN_URL=$DJANGO_ADMIN_URL
DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE
DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY
DJANGO_ALLOWED_HOSTS=$DJANGO_ALLOWED_HOSTS

# AWS Settings
DJANGO_AWS_ACCESS_KEY_ID=$DJANGO_AWS_ACCESS_KEY_ID
DJANGO_AWS_SECRET_ACCESS_KEY=$DJANGO_AWS_SECRET_ACCESS_KEY
DJANGO_AWS_STORAGE_BUCKET_NAME=$DJANGO_AWS_STORAGE_BUCKET_NAME

# Used with email
DJANGO_MAILGUN_API_KEY=$DJANGO_MAILGUN_API_KEY
DJANGO_SERVER_EMAIL=$DJANGO_SERVER_EMAIL
MAILGUN_SENDER_DOMAIN=$MAILGUN_SENDER_DOMAIN
EMAIL_BACKEND=$EMAIL_BACKEND

# Security! Better to use DNS for this task, but you can use redirect
DJANGO_SECURE_SSL_REDIRECT=$DJANGO_SECURE_SSL_REDIRECT

# django-allauth
DJANGO_ACCOUNT_ALLOW_REGISTRATION=$DJANGO_ACCOUNT_ALLOW_REGISTRATION

# AWS setup
S3_ACCESS_KEY=$S3_ACCESS_KEY
S3_SECRET_KEY=$S3_SECRET_KEY
S3_BUCKET=$S3_BUCKET

S3_PREFIX=$S3_PREFIX
S3_COMPRESSION_LEVEL=$S3_COMPRESSION_LEVEL

# Download path
DOWNLOAD_PATH=$DOWNLOAD_PATH
S3_DOCUMENT_PATH=$S3_DOCUMENT_PATH

# EDGAR PARAMETERS
EDGAR_YEAR=$EDGAR_YEAR
FORM_TYPES=$FORM_TYPES
EOF