# [OpenEDGAR](openedgar.io) by [LexPredict](https://lexpredict.com)
## Setup and Installation Guide

OpenEDGAR is designed to be run on Amazon Web Services to provide high-quality, reliable 
Internet access and intra-DC access to Amazon S3 for storage.  While users can run OpenEDGAR from outside of AWS, 
an AWS account is required for S3 usage and performance will be substantially reduced. 

#### Server Setup

1. Launch an EC2 instance

2. Update all packages

    a. `$ sudo apt update`
  
    b. `$ sudo apt upgrade`
  
5. Reboot
  
6. Format and mount disks (optional)

    a. `$ mkfs.ext4 /dev/nvme1n1`
    
    b. add to `/etc/fstab`
    
    c. Reboot to test mount


### Required Software Setup
7. Install Python: `$ sudo apt install build-essential python3-dev python3-pip virtualenv`

8. Install Postgres: `$ sudo apt install postgresql-9.5 postgresql-client-common libpq-dev`

9. Install Oracle Java

    a. `$ sudo add-apt-repository ppa:webupd8team/java`
    
    b. `$ sudo apt-get update`
    
    c. `$ sudo apt-get install oracle-java8-installer oracle-java8-set-default oracle-java8-unlimited-jce-policy`
    
    d. `$ java -version`


### OpenEDGAR Setup
10. Clone repo (you may need to ensure you have permissions to create a directory under /opt)

    a. `$ cd /opt`
    
    b. `$ git clone https://github.com/LexPredict/openedgar.git`

11. Setup virtual environment

    a. `$ cd /opt/openedgar`
    
    b. `$ virtualenv -p /usr/bin/python3 env`
    
    c. `$ ./env/bin/pip install -r lexpredict_openedgar/requirements/full.txt`
    
12. Setup database. Note that the password chosen for openegar must be set as DJANGO_PASSWORD in the .env later

    a. `$ sudo -u postgres createuser -l -P -s openedgar`
    
    b. `$ sudo -u postgres createdb -O openedgar openedgar`
    
    c. Move PG data folder (optional)
    ```
    $ sudo systemctl stop postgresql
    $ sudo systemctl status postgresql
    $ sudo  mv /var/lib/postgresql /data
    $ sudo ln -s /data/postgresql /var/lib/postgresql
    $ sudo chown -R postgres:postgres /var/lib/postgresql
    $ sudo systemctl start postgresql
    $ sudo systemctl status postgresql
    $ sudo -u postgres psql
    ```
    
13. Install and configure RabbitMQ

    a. `$ wget https://packages.erlang-solutions.com/erlang-solutions_1.0_all.deb`
    
    b. `$ sudo dpkg -i erlang-solutions_1.0_all.deb`
    
    c. `$ sudo apt update`
    
    d. `$ sudo apt install rabbitmq-server`
    
    e. `$ sudo rabbitmqctl add_user openedgar openedgar`
    
    f. `$ sudo rabbitmqctl add_vhost openedgar`
    
    g. `$ sudo rabbitmqctl set_permissions -p openedgar openedgar ".*" ".*" ".*"`

    h. Move rabbitmq data folder (optional)
    ```
    $ sudo systemctl stop rabbitmq-server.service
    $ sudo mv /var/lib/rabbitmq /data/
    $ sudo ln -s /data/rabbitmq /var/lib/rabbitmq
    $ sudo chown -R rabbitmq:rabbitmq /var/lib/rabbitmq
    $ sudo systemctl start rabbitmq-server.service
    $ sudo systemctl status rabbitmq-server.service
    ```

14. Update .env file. For local testing (downloading files locally, instead of to S3), set CLIENT_TYPE to LOCAL and DOWNLOAD_PATH to a local path

    a. `$ cp lexpredict_openedgar/sample.env lexpredict_openedgar/.env`
    
    b. Update DATABASE_URL
    
    c. Update CELERY_BROKER_URL
    
    d. Setup AWS S3 bucket
    
    e. Setup IAM policy
    ```
    {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "[REPLACE:unique ID]",
            "Effect": "Allow",
            "Action": [
                "s3:*"
            ],
            "Resource": [
                "arn:aws:s3:::[REPLACE:your bucket]"
            ]
        },
        {
            "Sid": "[REPLACE:unique ID]",
            "Effect": "Allow",
            "Action": [
                "s3:*"
            ],
            "Resource": [
                "arn:aws:s3:::[REPLACE:your bucket]/*"
            ]
        }
    ]
    }
    ```
    
    f. Update `S3_ACCESS_KEY`, `S3_SECRET_KEY`, and `S3_BUCKET`
    
15. Initial database migration

    a. `$ cd /opt/openedgar/lexpredict_openedgar`
    
    b. `$ source ../env/bin/activate`
    
    c. `$ source .env`
    
    d. `$ python manage.py migrate`

16. Setup Apache Tika and run

    a. `$ cd /opt/openedgar/tika`
    
    b. `$ bash download_tika.sh`
    
    c. `$ bash run_tika.sh` (run with `&`, `nohup`, or as service)
    
17. Setup Celery

    a. `$ cd /opt/openedgar/lexpredict_openedgar`
    
    b. `$ source ../env/bin/activate`
    
    c. `$ source .env`
    
    d. `$ bash scripts/run_celery.sh` (run with `&`, `nohup`, or as service)


### Sample Database Construction

18. Build database of 10-Ks from 2018 from latest SEC EDGAR data

    a. `$ cd /opt/openedgar/lexpredict_openedgar`
    
    b. `$ source ../env/bin/activate`
    
    c. `$ source .env`
    
    d. `$ python manage.py shell_plus`
    
    e. Retrieve all 10-Ks from 2018
    ```
    >>> from openedgar.processes.edgar import download_filing_index_data, process_all_filing_index
    >>> download_filing_index_data(year=2018)
    >>> process_all_filing_index(year=2018, form_type_list=["10-K"])
    ```
    
    f. Sample timing on `m5.large` (2 core, 8GB RAM): ~24 hours to retrieve and parse all 2018 10-Ks
    
    g. Sample statistics for 2018 10-Ks as of May
    ```
    # Data on S3
    Size of edgar/ on S3:
    Objects: 1645
    Size: 2.4 GB
    Size of documents/raw/ on S3:
    Objects: 135497
    Size: 2.1 GB
    Size of documents/text/ on S3:
    Object: 130469
    Size: 1000.4 MB
    
    # Data in Postgres
    In [7]: Filing.objects.count()
    Out[7]: 1521
    In [8]: FilingDocument.objects.count()
    Out[8]: 147598
    In [9]: Company.objects.count()
    Out[9]: 1451
    ``` 
