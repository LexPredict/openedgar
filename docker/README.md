# Dockerisation
The image will take as default parameters [default.env](docker/default.env)

All the variable can be substitute at runtime as environment variables

## Download tika
run in `/tika` the script `download_tika.sh` it will download in the `/tika'
folder tika version 1.20

## Docker
Run the follow from the repository root for creating the image:

    docker build -t dslcr.azurecr.io/openedgar:1.1 .
    
# Run container
It is wise to mount a local folder to the container for being able to access to the 
downloaded documents. 
Example:

    docker run --env-file vars.txt -v /Users/mirko/Projects/research-openedgar/data:/data dslcr.azurecr.io/openedgar:1.1

Contents of vars.txt
    
    EDGAR_YEAR=2015
    EDGAR_QUARTER=1
    EDGAR_MONTH=1
    CLIENT_TYPE=Local
    S3_DOCUMENT_PATH=/data
    DOWNLOAD_PATH=/data
 
After the download is terimated you have to stop the container:

    $ docker ps
    
    CONTAINER ID        IMAGE                            COMMAND              CREATED             STATUS              PORTS               NAMES
    9e0ae247b61f        dslcr.azurecr.io/openedgar:1.1   "oe-entrypoint.sh"   2 minutes ago       Up 2 minutes                            priceless_bardeen
    
    $ docker kill 9e
