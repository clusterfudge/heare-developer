# Memory Migration Examples

The memory migration tool allows you to copy memory entries between different backends (filesystem and HTTP). This is useful for migrating from local memory to a remote server or vice versa.

## Usage

### As a Slash Command (in hdev session)

```bash
# Migrate local memory to remote server (dry run)
!migrate_memory target_config="http:https://memory.example.com" dry_run=true

# Migrate local memory to remote server (actual migration)  
!migrate_memory target_config="http:https://memory.example.com" overwrite=false

# Migrate from remote to local with overwrite
!migrate_memory source_config="http:https://memory.example.com" target_config="filesystem" overwrite=true
```

### As a CLI Command

```bash
# Migrate from local filesystem to remote HTTP server
hdev migrate-memory --target http --target-url https://memory.example.com --api-key your-api-key --dry-run

# Migrate from remote server to local filesystem  
hdev migrate-memory --source http --source-url https://memory.example.com --target filesystem --api-key your-api-key

# Migrate between different filesystem paths
hdev migrate-memory --source filesystem --source-path /old/memory --target filesystem --target-path /new/memory

# Migrate with overwrite enabled
hdev migrate-memory --target http --target-url https://memory.example.com --api-key your-api-key --overwrite
```

## Common Use Cases

### 1. Initial Migration to Remote Server

When setting up a remote memory server, migrate your existing local memory:

```bash
# First, start your memory server
hdev memory-server --port 8080 --api-key your-secret-key

# Then migrate your local memory (dry run first)
hdev migrate-memory --target http --target-url http://localhost:8080 --api-key your-secret-key --dry-run

# If dry run looks good, run actual migration
hdev migrate-memory --target http --target-url http://localhost:8080 --api-key your-secret-key
```

### 2. Backup Remote Memory to Local

Create a local backup of your remote memory:

```bash
hdev migrate-memory --source http --source-url https://memory.example.com --target filesystem --target-path ./backup --api-key your-api-key
```

### 3. Sync Between Team Members

Share memory between team members:

```bash
# Person A exports their memory
hdev migrate-memory --target http --target-url https://shared-memory.example.com --api-key team-key

# Person B imports from shared memory
hdev migrate-memory --source http --source-url https://shared-memory.example.com --target filesystem --api-key team-key
```

### 4. Environment Migration

Move memory between development, staging, and production:

```bash
# Export from development
hdev migrate-memory --target http --target-url https://staging-memory.example.com --api-key staging-key

# Import to production (with careful review)
hdev migrate-memory --source http --source-url https://staging-memory.example.com --target http --target-url https://prod-memory.example.com --api-key prod-key --dry-run
```

## Configuration

### Using Environment Variables

Set up your API keys and URLs in environment variables:

```bash
export HDEV_MEMORY_HTTP_API_KEY=your-secret-key
export HDEV_MEMORY_HTTP_URL=https://memory.example.com

# Now you can migrate without specifying these each time
hdev migrate-memory --target http --target-url $HDEV_MEMORY_HTTP_URL
```

### Using Configuration Files

Set up your ~/.hdev/config.yaml:

```yaml
memory:
  backend: http
  http:
    url: https://memory.example.com
    api_key: your-secret-key
```

Then use simplified commands:

```bash
# Migrate to your configured remote server
hdev migrate-memory --target http --target-url https://memory.example.com
```

## Safety Features

### Dry Run Mode

Always test your migration with `--dry-run` first:

```bash
hdev migrate-memory --target http --target-url https://memory.example.com --api-key your-key --dry-run
```

This will show you:
- How many entries would be migrated
- Which entries would be skipped (already exist)
- Any potential errors

### Overwrite Protection

By default, existing entries in the target are skipped. Use `--overwrite` only when you want to replace existing entries:

```bash
# Safe - skips existing entries
hdev migrate-memory --target http --target-url https://memory.example.com --api-key your-key

# Caution - overwrites existing entries  
hdev migrate-memory --target http --target-url https://memory.example.com --api-key your-key --overwrite
```

## Migration Statistics

The tool provides detailed statistics:

```
Migration completed. 15 entries were copied, 3 skipped, 0 failed.

Migration Statistics:
  Total entries found: 18
  Entries copied: 15
  Entries skipped: 3
  Entries failed: 0
```

- **Total entries found**: Number of entries discovered in source
- **Entries copied**: Successfully migrated entries
- **Entries skipped**: Entries that already existed in target (when overwrite=false)
- **Entries failed**: Entries that failed to migrate (with error details)

## Error Handling

If some entries fail to migrate, you'll see detailed error information:

```
Migration completed with errors. 12 entries were copied, 3 skipped, 2 failed.

Errors:
  projects/large-file: Content too large for target backend
  personal/encrypted: Permission denied on target
```

You can then investigate and fix these issues before retrying the migration.

## Best Practices

1. **Always use dry run first** to verify the migration plan
2. **Backup your target** before running migrations with overwrite
3. **Use specific paths** rather than broad migrations when possible
4. **Monitor the migration** for large datasets
5. **Verify critical entries** after migration
6. **Use appropriate authentication** for remote servers

## Troubleshooting

### "No entries found to migrate"

- Verify your source backend is accessible
- Check that your source path contains memory entries
- Ensure proper authentication for HTTP backends

### "HTTP request failed" errors

- Verify the target server is running and accessible
- Check your API key is correct
- Ensure the server accepts the content you're migrating

### "Permission denied" errors

- Verify your API key has write permissions
- Check filesystem permissions for local backends
- Ensure the target directory exists and is writable