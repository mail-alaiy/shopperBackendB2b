FROM redis:7-alpine

# Copy custom config (to set data dir)
COPY redis.conf /usr/local/etc/redis/redis.conf

# Run redis with config
CMD ["redis-server", "/usr/local/etc/redis/redis.conf"]
