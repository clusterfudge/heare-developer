# Remote Memory System Deployment Guide

The heare-developer remote memory system enables team collaboration, multi-environment workflows, and cloud-native operations. This guide covers deployment patterns and best practices.

## Quick Start

### 1. Local Development Server

```bash
# Start a local memory server for testing
hdev memory-server --port 8080 --api-key dev-secret

# Configure client to use local server
export HDEV_MEMORY_BACKEND=http
export HDEV_MEMORY_HTTP_URL=http://localhost:8080
export HDEV_MEMORY_HTTP_API_KEY=dev-secret
```

### 2. Production Server with S3 Backup

```bash
# Start production server with S3 integration
hdev memory-server \
  --port 8080 \
  --api-key $PRODUCTION_API_KEY \
  --s3-bucket production-memory-backups \
  --s3-region us-east-1
```

## Configuration

### Environment Variables

```bash
# Memory backend selection
export HDEV_MEMORY_BACKEND=http  # or "filesystem"

# HTTP backend configuration
export HDEV_MEMORY_HTTP_URL=https://memory.example.com
export HDEV_MEMORY_HTTP_API_KEY=secure-api-key
export HDEV_MEMORY_HTTP_TIMEOUT=30

# S3 backup configuration
export HDEV_S3_BUCKET=team-memory-backups
export HDEV_S3_REGION=us-east-1
export HDEV_S3_ACCESS_KEY_ID=your-access-key
export HDEV_S3_SECRET_ACCESS_KEY=your-secret-key

# For S3-compatible services (MinIO, etc.)
export HDEV_S3_ENDPOINT_URL=https://minio.example.com
```

### Configuration File

Create `~/.hdev/config.yaml`:

```yaml
memory:
  backend: http
  http:
    url: https://memory.example.com
    api_key: secure-api-key
    timeout: 30
  s3:
    bucket: team-memory-backups
    region: us-east-1
    access_key_id: your-access-key
    secret_access_key: your-secret-key
    endpoint_url: https://minio.example.com  # Optional
```

## Deployment Patterns

### 1. Single Team Server

**Use Case**: Small team with shared knowledge base

```bash
# Server (on dedicated machine or cloud instance)
hdev memory-server \
  --host 0.0.0.0 \
  --port 8080 \
  --api-key $TEAM_API_KEY \
  --storage-path /data/memory \
  --s3-bucket team-backups

# Team members configure clients
export HDEV_MEMORY_BACKEND=http
export HDEV_MEMORY_HTTP_URL=https://team-memory.example.com
export HDEV_MEMORY_HTTP_API_KEY=$TEAM_API_KEY
```

### 2. Multi-Environment Setup

**Use Case**: Development, staging, and production environments

```bash
# Development server
hdev memory-server --port 8080 --api-key dev-key --s3-bucket dev-memory

# Staging server  
hdev memory-server --port 8080 --api-key staging-key --s3-bucket staging-memory

# Production server
hdev memory-server --port 8080 --api-key prod-key --s3-bucket prod-memory

# Environment-specific client configuration
# Development
export HDEV_MEMORY_HTTP_URL=https://dev-memory.example.com
export HDEV_MEMORY_HTTP_API_KEY=dev-key

# Staging  
export HDEV_MEMORY_HTTP_URL=https://staging-memory.example.com
export HDEV_MEMORY_HTTP_API_KEY=staging-key

# Production
export HDEV_MEMORY_HTTP_URL=https://prod-memory.example.com
export HDEV_MEMORY_HTTP_API_KEY=prod-key
```

### 3. High Availability Setup

**Use Case**: Production deployment with redundancy

```bash
# Multiple server instances behind load balancer
# Instance 1
hdev memory-server --port 8080 --api-key $API_KEY --storage-path /shared/memory

# Instance 2  
hdev memory-server --port 8080 --api-key $API_KEY --storage-path /shared/memory

# Load balancer configuration (nginx example)
upstream memory_servers {
    server memory-1.internal:8080;
    server memory-2.internal:8080;
}

server {
    listen 443 ssl;
    server_name memory.example.com;
    
    location / {
        proxy_pass http://memory_servers;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.12-slim

# Install heare-developer
COPY . /app
WORKDIR /app
RUN pip install -e .

# Create storage directory
RUN mkdir -p /data/memory

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/api/health || exit 1

# Run server
CMD ["hdev", "memory-server", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--storage-path", "/data/memory"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  memory-server:
    build: .
    ports:
      - "8080:8080"
    environment:
      - HDEV_MEMORY_SERVER_API_KEY=${API_KEY}
      - HDEV_S3_BUCKET=${S3_BUCKET}
      - HDEV_S3_REGION=${S3_REGION}
      - HDEV_S3_ACCESS_KEY_ID=${S3_ACCESS_KEY_ID}
      - HDEV_S3_SECRET_ACCESS_KEY=${S3_SECRET_ACCESS_KEY}
    volumes:
      - memory_data:/data/memory
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  memory_data:
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: memory-server
spec:
  replicas: 2
  selector:
    matchLabels:
      app: memory-server
  template:
    metadata:
      labels:
        app: memory-server
    spec:
      containers:
      - name: memory-server
        image: heare-developer:latest
        ports:
        - containerPort: 8080
        env:
        - name: HDEV_MEMORY_SERVER_API_KEY
          valueFrom:
            secretKeyRef:
              name: memory-secrets
              key: api-key
        - name: HDEV_S3_BUCKET
          value: "k8s-memory-backups"
        volumeMounts:
        - name: memory-storage
          mountPath: /data/memory
        livenessProbe:
          httpGet:
            path: /api/health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: memory-storage
        persistentVolumeClaim:
          claimName: memory-pvc

---
apiVersion: v1
kind: Service
metadata:
  name: memory-server-service
spec:
  selector:
    app: memory-server
  ports:
  - port: 80
    targetPort: 8080
  type: LoadBalancer

---
apiVersion: v1
kind: Secret
metadata:
  name: memory-secrets
type: Opaque
data:
  api-key: <base64-encoded-api-key>
```

## Security Considerations

### API Key Management

```bash
# Generate secure API keys
openssl rand -hex 32

# Use environment variables (recommended)
export HDEV_MEMORY_SERVER_API_KEY=$(openssl rand -hex 32)

# Rotate keys regularly
# 1. Generate new key
NEW_KEY=$(openssl rand -hex 32)

# 2. Update server configuration
hdev memory-server --api-key $NEW_KEY

# 3. Update client configurations
export HDEV_MEMORY_HTTP_API_KEY=$NEW_KEY
```

### HTTPS/TLS Setup

Use a reverse proxy (nginx, traefik, etc.) for TLS termination:

```nginx
server {
    listen 443 ssl http2;
    server_name memory.example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### S3 Security

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-memory-bucket",
        "arn:aws:s3:::your-memory-bucket/*"
      ]
    }
  ]
}
```

## Monitoring and Observability

### Health Checks

```bash
# Server health check
curl -f http://localhost:8080/api/health

# Example response
{
  "status": "healthy",
  "backend": "FilesystemMemoryBackend",
  "s3_configured": true,
  "timestamp": "2023-12-01T12:00:00Z"
}
```

### Metrics Collection

The memory server exposes metrics for monitoring:

- **Request count**: Total API requests
- **Response times**: API endpoint latency
- **Error rates**: Failed requests by endpoint
- **Backup status**: S3 backup success/failure rates
- **Storage metrics**: Memory entries count, size

### Logging

Configure structured logging:

```bash
# Enable debug logging
export HDEV_LOG_LEVEL=DEBUG

# JSON logging for structured collection
export HDEV_LOG_FORMAT=json

# Log to file
export HDEV_LOG_FILE=/var/log/hdev-memory.log
```

## Backup and Recovery

### Automated S3 Backups

```bash
# Create daily backup script
#!/bin/bash
BACKUP_NAME="daily-$(date +%Y%m%d)"
hdev backup-memory --s3-bucket prod-backups --backup-name $BACKUP_NAME

# Log results
echo "$(date): Backup $BACKUP_NAME completed" >> /var/log/memory-backup.log
```

### Backup Scheduling

```bash
# Add to crontab
0 2 * * * /path/to/backup-script.sh  # Daily at 2 AM
0 2 * * 0 /path/to/weekly-backup.sh  # Weekly on Sunday
```

### Disaster Recovery

```bash
# List available backups
hdev memory-server --s3-bucket prod-backups --list-backups

# Restore from backup
hdev restore-memory backup_20231201_020000 \
  --s3-bucket prod-backups \
  --overwrite
```

## Migration Strategies

### Filesystem to HTTP

```bash
# 1. Start new HTTP server
hdev memory-server --port 8080 --api-key new-server-key

# 2. Migrate existing memory
hdev migrate-memory \
  --target http \
  --target-url http://localhost:8080 \
  --api-key new-server-key \
  --dry-run  # Test first

# 3. Run actual migration
hdev migrate-memory \
  --target http \
  --target-url http://localhost:8080 \
  --api-key new-server-key

# 4. Update client configuration
export HDEV_MEMORY_BACKEND=http
export HDEV_MEMORY_HTTP_URL=http://localhost:8080
export HDEV_MEMORY_HTTP_API_KEY=new-server-key
```

### Cross-Environment Migration

```bash
# Development to staging
hdev backup-memory --s3-bucket dev-backups --backup-name dev-to-staging
hdev restore-memory dev-to-staging --s3-bucket dev-backups --memory-backend http --target-url https://staging-memory.example.com
```

## Performance Tuning

### Server Configuration

```bash
# High-performance server settings
hdev memory-server \
  --workers 4 \
  --max-connections 1000 \
  --keepalive-timeout 5 \
  --access-log-enabled false  # Disable for performance
```

### Client Configuration

```yaml
memory:
  http:
    timeout: 30
    max_retries: 3
    retry_delay: 1.0
    connection_pool_size: 10
```

### S3 Optimization

```bash
# Use appropriate S3 storage class
export HDEV_S3_STORAGE_CLASS=STANDARD_IA  # For backups

# Enable transfer acceleration
export HDEV_S3_TRANSFER_ACCELERATION=true
```

## Troubleshooting

### Common Issues

**Connection Refused**
```bash
# Check server is running
curl -f http://localhost:8080/api/health

# Check firewall/networking
telnet localhost 8080
```

**Authentication Errors**
```bash
# Verify API key
curl -H "Authorization: Bearer your-api-key" http://localhost:8080/api/health
```

**S3 Access Errors**
```bash
# Test S3 credentials
aws s3 ls s3://your-bucket/

# Check IAM permissions
aws iam simulate-principal-policy --policy-source-arn arn:aws:iam::account:user/username --action-names s3:GetObject --resource-arns arn:aws:s3:::your-bucket/*
```

### Debug Mode

```bash
# Enable debug logging
export HDEV_LOG_LEVEL=DEBUG
hdev memory-server --port 8080

# Check server logs
tail -f /var/log/hdev-memory.log
```

This deployment guide provides comprehensive coverage for production deployment of the remote memory system with various deployment patterns, security considerations, and operational best practices.