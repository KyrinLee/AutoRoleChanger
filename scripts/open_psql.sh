#!/bin/sh

#Opens a PSQL shell on the dockered postgres database

#docker command with file doc-comp.yml
#			 execute under user postgress
#						in container db
#							run psql [database name]
docker-compose -f ../docker-compose.yml exec -u postgres db psql postgres
