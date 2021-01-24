#!/usr/bin/env python
import os
import sys

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')

    try:
        from django.core.management import execute_from_command_line
    except ImportError:
        # The above import may fail for some other reason. Ensure that the
        # issue is really that Django is missing to avoid masking other
        # exceptions on Python 2.
        try:
            import django  # noqa
        except ImportError:
            raise ImportError(
                "Couldn't import Django. Are you sure it's installed and "
                "available on your PYTHONPATH environment variable? Did you "
                "forget to activate a virtual environment?"
            )
        raise

    # This allows easy placement of apps within the interior
    # lexpredict_openedgar directory.
    current_path = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(os.path.join(current_path, 'lexpredict_openedgar'))

    from django.db import connection
    if 'openedgar_company' not in connection.introspection.table_names():
        execute_from_command_line(['manage.py', 'migrate'])

    from openedgar.clients.s3 import S3Client
    s3 = S3Client()
    try:
        s3.get_bucket().create()
    except:
        pass

    execute_from_command_line(sys.argv)
