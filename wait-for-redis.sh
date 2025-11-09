#!/bin/sh
# wait-for-redis.sh

set -e

host="$1"
shift
cmd="$@"

until python -c "import redis; r = redis.Redis(host='$host', port=6379); r.ping()"; do
  >&2 echo "Redis is unavailable - sleeping"
  sleep 1
done

>&2 echo "Redis is up - executing command"
exec $cmd
