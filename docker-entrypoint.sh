#!/bin/sh
set -e

# Ensure persistent directories exist and have proper permissions for botzilla user
if [ "$(id -u)" = '0' ]; then
    mkdir -p /app/data /app/logs /app/assets/logos
    chown -R botzilla:botzilla /app/data /app/logs /app/assets/logos 2>/dev/null || true
    chmod -R 775 /app/data /app/logs /app/assets/logos 2>/dev/null || true
    exec gosu botzilla "$@"
fi

exec "$@"
