# S3 Backup Integration Examples

The memory system now supports full S3 backup and restore functionality, allowing you to backup your memory to cloud storage and restore it anywhere.

## Quick Start

### 1. Configure S3 Access

Set up your S3 credentials and configuration:

```bash
# Environment variables
export HDEV_S3_BUCKET=my-memory-backups
export HDEV_S3_REGION=us-east-1
export HDEV_S3_ACCESS_KEY_ID=your-access-key
export HDEV_S3_SECRET_ACCESS_KEY=your-secret-key

# For S3-compatible services (MinIO, etc.)
export HDEV_S3_ENDPOINT_URL=https://minio.example.com
```

Or via configuration file (`~/.hdev/config.yaml`):

```yaml
memory:
  s3:
    bucket: my-memory-backups
    region: us-east-1
    access_key_id: your-access-key
    secret_access_key: your-secret-key
    endpoint_url: https://minio.example.com  # Optional
```

### 2. Backup Your Memory

```bash
# Backup with automatic timestamp name
hdev backup-memory --s3-bucket my-memory-backups

# Backup with custom name
hdev backup-memory --s3-bucket my-memory-backups --backup-name project-milestone

# Interactive backup in hdev session
!backup_memory_s3 backup_name="daily-backup"
```

### 3. Restore Memory

```bash
# List available backups
hdev memory-server --s3-bucket my-memory-backups

# Restore a specific backup
hdev restore-memory backup_20231201_120000 --s3-bucket my-memory-backups

# Restore with overwrite (replace existing entries)
hdev restore-memory backup_20231201_120000 --s3-bucket my-memory-backups --overwrite

# Interactive restore
!restore_memory_s3 backup_key="backup_20231201_120000" overwrite=false
```

## Use Cases

### Team Collaboration

Share memory between team members:

```bash
# Team member A creates backup
hdev backup-memory --s3-bucket team-shared-memory --backup-name onboarding-docs

# Team member B restores shared knowledge  
hdev restore-memory onboarding-docs --s3-bucket team-shared-memory
```

### Environment Migration

Move memory between development, staging, and production:

```bash
# Backup from development
hdev backup-memory --s3-bucket dev-memory --backup-name dev-to-staging

# Restore in staging
hdev restore-memory dev-to-staging --s3-bucket dev-memory --memory-backend filesystem
```

### Disaster Recovery

Create regular backups for disaster recovery:

```bash
# Daily backup script
#!/bin/bash
BACKUP_NAME="daily-$(date +%Y%m%d)"
hdev backup-memory --s3-bucket disaster-recovery --backup-name $BACKUP_NAME

# Keep only last 30 days (use S3 lifecycle policies or script cleanup)
```

### Remote Memory Server

Run a memory server with S3 backup support:

```bash
# Start server with S3 integration
hdev memory-server --port 8080 --api-key secret --s3-bucket production-memory

# Server now has backup/restore endpoints:
# POST /api/memory/backup
# POST /api/memory/restore  
# GET /api/memory/backups
# DELETE /api/memory/backup/{backup_key}
```

## Storage Structure

S3 backups are stored in a structured format:

```
s3://your-bucket/hdev-memory-backups/
├── backup_20231201_120000/
│   ├── metadata.json              # Backup information
│   └── entries/
│       ├── global.json.gz         # Compressed memory entries
│       ├── projects/
│       │   └── project1.json.gz
│       └── personal/
│           └── notes.json.gz
└── project-milestone/
    ├── metadata.json
    └── entries/
        └── ...
```

### Metadata Format

Each backup includes metadata with information:

```json
{
  "backup_name": "backup_20231201_120000",
  "timestamp": "2023-12-01T12:00:00Z",
  "total_entries": 15,
  "backend_type": "FilesystemMemoryBackend",
  "version": "1.0"
}
```

### Entry Format

Memory entries are stored as compressed JSON:

```json
{
  "content": "Memory entry content here...",
  "metadata": {
    "type": "project",
    "created": "2023-12-01T10:00:00Z",
    "updated": "2023-12-01T11:30:00Z"
  }
}
```

## Interactive Tools

Within an hdev session, you can use these slash commands:

### Backup Memory

```bash
# Simple backup
!backup_memory_s3

# Custom backup name
!backup_memory_s3 backup_name="before-refactor"
```

### Restore Memory

```bash
# Safe restore (skip existing entries)
!restore_memory_s3 backup_key="backup_20231201_120000"

# Overwrite existing entries
!restore_memory_s3 backup_key="backup_20231201_120000" overwrite=true
```

### List Backups

```bash
!list_memory_backups
```

Example output:
```
Found 3 backups:

• backup_20231201_130000
  Timestamp: 2023-12-01T13:00:00Z
  Entries: 18
  Backend: FilesystemMemoryBackend

• project-milestone  
  Timestamp: 2023-12-01T12:00:00Z
  Entries: 15
  Backend: FilesystemMemoryBackend

• backup_20231201_120000
  Timestamp: 2023-12-01T12:00:00Z
  Entries: 12
  Backend: HTTPMemoryBackend
```

## Advanced Configuration

### S3-Compatible Services

Use with MinIO, DigitalOcean Spaces, or other S3-compatible services:

```bash
# MinIO example
export HDEV_S3_ENDPOINT_URL=https://minio.example.com
export HDEV_S3_BUCKET=hdev-memory
export HDEV_S3_ACCESS_KEY_ID=minio-access-key
export HDEV_S3_SECRET_ACCESS_KEY=minio-secret-key

hdev backup-memory
```

### Custom Regions

Use different AWS regions or configurations:

```bash
export HDEV_S3_REGION=eu-west-1
export HDEV_S3_BUCKET=eu-memory-backups

hdev backup-memory --s3-region eu-west-1
```

### Memory Server with S3

Run the memory server with S3 backup integration:

```bash
# Start server with S3 support
hdev memory-server \
  --port 8080 \
  --api-key your-secret-key \
  --s3-bucket production-backups \
  --s3-region us-east-1

# Disable S3 backup functionality
hdev memory-server --disable-s3-backup --port 8080
```

## Error Handling

The S3 integration includes comprehensive error handling:

### Common Errors

**S3 not configured:**
```
Error: S3 backup is not configured. Please set s3_bucket in config or environment variables.
```

**Missing credentials:**
```
Error during backup: Unable to locate credentials
```

**Network issues:**
```
Backup completed with errors. 10 entries were backed up, 0 skipped, 2 failed.

Errors:
  large-project/data: Request timeout - retry limit exceeded
```

### Troubleshooting

1. **Verify credentials:** `aws s3 ls s3://your-bucket/` (if using AWS CLI)
2. **Check bucket permissions:** Ensure read/write access
3. **Network connectivity:** Test endpoint reachability
4. **Bucket exists:** Create bucket if it doesn't exist

## Best Practices

### Security

- Use IAM roles instead of access keys when possible
- Limit S3 permissions to specific bucket/prefix
- Use S3 bucket policies for additional security
- Rotate access keys regularly

### Performance

- Use compression (enabled by default)
- Choose appropriate S3 region for your location
- Consider S3 storage classes for long-term backups
- Use S3 lifecycle policies for automatic cleanup

### Monitoring

- Monitor backup success/failure rates
- Set up S3 CloudWatch metrics
- Use backup timestamps to verify regular backups
- Monitor storage costs and usage

### Automation

Create scripts for regular backups:

```bash
#!/bin/bash
# backup-memory.sh
BACKUP_NAME="auto-$(date +%Y%m%d_%H%M%S)"
hdev backup-memory --backup-name "$BACKUP_NAME"

# Log results
echo "$(date): Backup $BACKUP_NAME completed" >> /var/log/hdev-backup.log
```

Set up cron job:
```bash
# Daily backup at 2 AM
0 2 * * * /path/to/backup-memory.sh
```

## Migration Examples

### Local to Remote Server

```bash
# 1. Backup local memory
hdev backup-memory --s3-bucket migration-bucket --backup-name local-to-remote

# 2. Start remote server
ssh remote-server "hdev memory-server --s3-bucket migration-bucket --api-key secret"

# 3. Restore to remote server
curl -X POST https://remote-server:8080/api/memory/restore \
  -H "Authorization: Bearer secret" \
  -H "Content-Type: application/json" \
  -d '{"backup_key": "local-to-remote", "overwrite": true}'
```

### Cross-Platform Migration

```bash
# From Windows to Linux
hdev backup-memory --s3-bucket cross-platform --backup-name windows-backup

# On Linux machine
hdev restore-memory windows-backup --s3-bucket cross-platform
```

This completes the S3 integration documentation. The system now provides enterprise-ready backup and restore capabilities with full cloud storage support!