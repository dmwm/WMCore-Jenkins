#!/bin/bash

export MY_HOSTNAME=$(hostname -f)
export MY_ID=$(id -u)
export MY_GROUP=$(id -g)
export WORKSPACE=/home/cmsbld/workspace
export HOST_MOUNT_DIR=$WORKSPACE
export WMA_TAG=2.3.3
export COUCH_TAG=3.2.2
export MDB_TAG=11.8.2

