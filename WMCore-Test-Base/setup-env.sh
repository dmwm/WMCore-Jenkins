#!/bin/bash

# clean workspace
rm -rf $WORKSPACE/admin $WORKSPACE/certs $WORKSPACE/artifacts
rm -rf $WORKSPACE/srv/{couchdb,mariadb,wmagent}  

# make directories
mkdir -p $WORKSPACE/admin/wmagent $WORKSPACE/admin/mariadb $WORKSPACE/certs $WORKSPACE/artifacts
mkdir -p $WORKSPACE/srv/couchdb/${COUCH_TAG}/install
mkdir -p $WORKSPACE/srv/couchdb/${COUCH_TAG}/logs
mkdir -p $WORKSPACE/srv/couchdb/${COUCH_TAG}/state
mkdir -p $WORKSPACE/srv/couchdb/${COUCH_TAG}/config
mkdir -p $WORKSPACE/srv/mariadb/${MDB_TAG}/install/database
mkdir -p $WORKSPACE/srv/mariadb/${MDB_TAG}/logs
mkdir -p $WORKSPACE/srv/wmagent/${WMA_TAG}/install
mkdir -p $WORKSPACE/srv/wmagent/${WMA_TAG}/logs
mkdir -p $WORKSPACE/srv/wmagent/${WMA_TAG}/state
mkdir -p $WORKSPACE/srv/wmagent/${WMA_TAG}/config

# secrets
cp /home/cmsbld/.globus/dmwm-config.tmpl $WORKSPACE/admin/wmagent/WMAgent.secrets
cp /home/cmsbld/.globus/dmwm-mariadb.tmpl $WORKSPACE/admin/mariadb/MariaDB.secrets
cp /home/cmsbld/.globus/*.pem $WORKSPACE/certs
mv $WORKSPACE/certs/usercert.pem $WORKSPACE/certs/servicecert.pem
mv $WORKSPACE/certs/userkey.pem $WORKSPACE/certs/servicekey.pem
chmod 600 $WORKSPACE/certs/servicecert.pem
chmod 400 $WORKSPACE/certs/servicekey.pem

# fix some incorrect information in secrets files
# change to correct CouchDB port
sed -i 's/6994/5984/g' $WORKSPACE/admin/wmagent/WMAgent.secrets
sed -i 's/THISHOSTNAME/localhost/g' $WORKSPACE/admin/wmagent/WMAgent.secrets

# replace mysql with mariadb
sed -i 's/MYSQL/MDB/g' $WORKSPACE/admin/wmagent/WMAgent.secrets
# docker compose up -d wmagent-dev
