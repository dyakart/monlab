#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
mkdir -p ca server web1 web2 web3 web4

# Если уже есть и не просили FORCE=1 — просто выходим
if [ -z "$FORCE" ] \
  && [ -f ca/ca.crt ] && [ -f server/log-srv.crt ] \
  && [ -f web1/client.crt ] && [ -f web2/client.crt ] \
  && [ -f web3/client.crt ] && [ -f web4/client.crt ]; then
  echo "[certs] already exist, skipping (set FORCE=1 to regenerate)"
  exit 0
fi

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

# webserver3
openssl genrsa -out web3/client.key 2048
openssl req -new -key web3/client.key -subj "/CN=webserver3" -out web3/client.csr
openssl x509 -req -in web3/client.csr -CA ca/ca.crt -CAkey ca/ca.key -CAcreateserial \
  -out web3/client.crt -days 1825 -sha256

# webserver4
openssl genrsa -out web4/client.key 2048
openssl req -new -key web4/client.key -subj "/CN=webserver4" -out web4/client.csr
openssl x509 -req -in web4/client.csr -CA ca/ca.crt -CAkey ca/ca.key -CAcreateserial \
  -out web4/client.crt -days 1825 -sha256

echo "CA: ca/ca.crt"
echo "Server: server/log-srv.crt, server/log-srv.key"
echo "Clients: web1/client.crt,key  web2/client.crt,key web3/client.crt,key web4/client.crt,key"
