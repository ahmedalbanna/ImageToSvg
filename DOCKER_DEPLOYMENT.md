# Docker Deployment Guide for im2svg

## Quick Start

### Development Mode

```bash
# Build and run in development mode (with hot-reload)
docker-compose -f docker-compose.dev.yml up --build

# Access at: http://localhost:8000
```

### Production Mode (Simple)

```bash
# Build and run in production mode
docker-compose up -d --build

# Access at: http://localhost:8000
```

### Production Mode (with Nginx)

```bash
# Build and run with Nginx reverse proxy
docker-compose -f docker-compose.prod.yml up -d --build

# Access at: http://localhost (port 80)
```

---

## Docker Commands

### Build

```bash
# Build the image
docker-compose build

# Build without cache
docker-compose build --no-cache
```

### Run

```bash
# Start services
docker-compose up

# Start in background
docker-compose up -d

# Start specific service
docker-compose up im2svg
```

### Stop

```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Stop and remove images
docker-compose down --rmi all
```

### Logs

```bash
# View logs
docker-compose logs

# Follow logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f im2svg
```

### Shell Access

```bash
# Execute shell in running container
docker-compose exec im2svg /bin/bash

# Run one-off command
docker-compose run im2svg python -c "print('Hello')"
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Application
HOST=0.0.0.0
PORT=8000
DEBUG=0

# Workers (production)
WORKERS=4

# Cache settings
CACHE_SIZE=1000
CACHE_TTL=3600
```

### Custom Port

```bash
# Run on custom port
docker-compose up -e PORT=9000 -p 9000:9000
```

---

## Production Deployment

### 1. Prerequisites

```bash
# Install Docker and Docker Compose
sudo apt-get update
sudo apt-get install docker.io docker-compose

# Add user to docker group (optional)
sudo usermod -aG docker $USER
```

### 2. Deploy with Nginx

```bash
# Clone repository
git clone <your-repo-url>
cd im2svg

# Build and run
docker-compose -f docker-compose.prod.yml up -d --build

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### 3. SSL/HTTPS (Optional)

```bash
# Create SSL directory
mkdir ssl

# Copy certificates
cp /path/to/cert.pem ssl/cert.pem
cp /path/to/key.pem ssl/key.pem

# Update nginx.conf (uncomment HTTPS section)
# Then restart
docker-compose restart nginx
```

### 4. Monitoring

```bash
# Check resource usage
docker stats

# Check health
docker-compose ps
curl http://localhost/health
```

---

## Scaling

### Horizontal Scaling

```bash
# Run multiple instances
docker-compose up -d --scale im2svg=3

# With load balancer
docker-compose -f docker-compose.prod.yml up -d --scale im2svg=3
```

### Resource Limits

Edit `docker-compose.prod.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs im2svg

# Inspect container
docker inspect im2svg

# Rebuild from scratch
docker-compose down -v
docker-compose build --no-cache
docker-compose up
```

### Port Already in Use

```bash
# Find process using port
sudo lsof -i :8000

# Or use different port
docker-compose up -p 8001:8000
```

### Out of Memory

```bash
# Increase memory limit in docker-compose.prod.yml
# Or clear Docker cache
docker system prune -a
```

### Permissions Issues

```bash
# Fix file permissions
sudo chown -R $USER:$USER .

# Or run with sudo
sudo docker-compose up
```

---

## Backup & Restore

### Backup

```bash
# Backup volumes
docker run --rm -v im2svg_cache:/data -v $(pwd):/backup \
  alpine tar czf /backup/im2svg_backup.tar.gz /data

# Export image
docker save im2svg:latest | gzip > im2svg_image.tar.gz
```

### Restore

```bash
# Restore volumes
docker run --rm -v im2svg_cache:/data -v $(pwd):/backup \
  alpine tar xzf /backup/im2svg_backup.tar.gz -C /

# Import image
docker load < im2svg_image.tar.gz
```

---

## Updates & Maintenance

### Update Application

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose down
docker-compose up -d --build

# Or zero-downtime update
docker-compose up -d --no-deps --build im2svg
```

### Clean Up

```bash
# Remove unused images
docker image prune

# Remove all unused resources
docker system prune -a

# View disk usage
docker system df
```

---

## Security Best Practices

1. **Use SSL/TLS in production**
   - Configure HTTPS in nginx.conf
   - Use Let's Encrypt for free certificates

2. **Limit resource usage**
   - Set CPU and memory limits
   - Configure rate limiting in Nginx

3. **Keep images updated**
   ```bash
   docker pull python:3.9-slim
   docker-compose build --no-cache
   ```

4. **Use secrets for sensitive data**
   - Don't commit .env files
   - Use Docker secrets in production

5. **Run as non-root user**
   - Add USER directive in Dockerfile

---

## Performance Optimization

### 1. Enable Caching

```bash
# Use Redis for shared cache (optional)
docker-compose -f docker-compose.redis.yml up -d
```

### 2. Optimize Image Size

```bash
# Check image size
docker images im2svg

# Use multi-stage build (add to Dockerfile)
```

### 3. Connection Pooling

- Configure Nginx upstream
- Use multiple workers in production

---

## Monitoring & Logging

### Health Checks

```bash
# Manual health check
curl http://localhost:8000/

# Automatic health check (configured in Dockerfile)
docker inspect --format='{{.State.Health.Status}}' im2svg
```

### Centralized Logging

```bash
# View all logs
docker-compose logs -f --tail=100

# Export logs
docker-compose logs > im2svg.log
```

---

## Example Deployment Scenarios

### Scenario 1: Local Development

```bash
docker-compose -f docker-compose.dev.yml up
# Hot-reload enabled, port 8000
```

### Scenario 2: Staging Server

```bash
docker-compose up -d
# Simple setup, port 8000
```

### Scenario 3: Production Server

```bash
docker-compose -f docker-compose.prod.yml up -d
# Nginx + Gunicorn, port 80/443
```

### Scenario 4: Cloud Deployment (AWS ECS, etc.)

```bash
# Build and push to registry
docker build -t your-registry/im2svg:latest .
docker push your-registry/im2svg:latest

# Deploy using platform-specific tools
```

---

## Support

For issues or questions:
1. Check logs: `docker-compose logs -f`
2. Verify configuration
3. Review documentation
4. Check GitHub issues

---

**Last Updated**: 2026-01-28
**Docker Version**: 20.10+
**Docker Compose Version**: 1.29+
