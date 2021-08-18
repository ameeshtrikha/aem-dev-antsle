#!/bin/bash
#
# Install Apache 2.4 by from source.
#

APR_VERSION=1.6.3
APR_UTIL_VERSION=1.6.1
HTTP_VERSION=2.4.32

OPTIND=1
while getopts "h:a:u:" opt; do
	case "$opt" in
	h)	HTTP_VERSION = $OPTARG
			;;
	a)	APR_VERSION = $OPTARG
			;;
	u)	APR_UTIL_VERSION = $OPTARG
			;;
	esac
done

#
# Get and extract sources packages
#

cd /usr/src
wget https://archive.apache.org/dist/apr/apr-$APR_VERSION.tar.gz
wget https://archive.apache.org/dist/apr/apr-util-$APR_UTIL_VERSION.tar.gz
wget https://archive.apache.org/dist/httpd/httpd-$HTTP_VERSION.tar.gz
tar xvfz apr-$APR_VERSION.tar.gz
tar xvfz apr-util-$APR_UTIL_VERSION.tar.gz
tar xvfz httpd-$HTTP_VERSION.tar.gz

cp -r apr-$APR_VERSION httpd-$HTTP_VERSION/srclib/apr
cp -r apr-util-$APR_UTIL_VERSION httpd-$HTTP_VERSION/srclib/apr-util

#
# Build and install apache httpd
#

cd httpd-$HTTP_VERSION

[ -d /etc/httpd ] || mkdir /etc/httpd

./configure --enable-ssl --enable-so --with-mpm=worker --with-included-apr --enable-layout=RedHat
make
make install

ln -s /usr/lib/libapr-1.so.0 /lib64/libapr-1.so.0
ln -s /usr/lib/libaprutil-1.so.0 /lib64/libaprutil-1.so.0

#
# Clean installation files
#

cd /usr/src
rm -f apr-$APR_VERSION.tar.gz apr-util-$APR_UTIL_VERSION.tar.gz httpd-$HTTP_VERSION.tar.gz
rm -rf apr-$APR_VERSION apr-util-$APR_UTIL_VERSION httpd-$HTTP_VERSION
