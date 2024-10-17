#!/bin/bash

DATE=$(date +%Y%m%d)

#docker tag wmcore-dev registry.cern.ch/cmsweb/wmcore-dev:latest
#docker push registry.cern.ch/cmsweb/wmcore-dev:latest

docker tag wmcore-dev registry.cern.ch/cmsweb/wmcore-dev:$DATE
docker push registry.cern.ch/cmsweb/wmcore-dev:$DATE
