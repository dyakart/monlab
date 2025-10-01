#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
mkdir -p ca server web1 web2

# CA
openssl genrsa -out ca/ca.key 4096
openssl req -x509 -new -nodes -key ca/ca.key -sha256 -days 3650 \
  -subj "/CN=monlab-ca" -out ca/ca.crt

# server (log-srv)
openssl genrsa -out server/log-srv.key 2048
openssl req -new -key server/log-srv.key -subj "/CN=log-srv" -out server/log-srv.csr
openssl x509 -req -in server/log-srv.csr -CA ca/ca.crt -CAkey ca/ca.key -CAcreateserial \
  -out server/log-srv.crt -days 1825 -sha256

# webserver1
openssl genrsa -out web1/client.key 2048
openssl req -new -key web1/client.key -subj "/CN=webserver1" -out web1/client.csr
openssl x509 -req -in web1/client.csr -CA ca/ca.crt -CAkey ca/ca.key -CAcreateserial \
  -out web1/client.crt -days 1825 -sha256

# webserver2
openssl genrsa -out web2/client.key 2048
openssl req -new -key web2/client.key -subj "/CN=webserver2" -out web2/client.csr
openssl x509 -req -in web2/client.csr -CA ca/ca.crt -CAkey ca/ca.key -CAcreateserial \
  -out web2/client.crt -days 1825 -sha256

echo "CA: ca/ca.crt"
echo "Server: server/log-srv.crt, server/log-srv.key"
echo "Clients: web1/client.crt,key  web2/client.crt,key"
