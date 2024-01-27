#!/bin/bash

set +ex

git clone https://github.com/adrianreber/ohpc-infrastructure.git
cd ohpc-infrastructure/ansible/roles/test/files/
./run-ci.sh almalinux9.2 3.1
