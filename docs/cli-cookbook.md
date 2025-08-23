# CLI Cookbook

## Monitor stats continuously

```bash
yokedcache stats --watch
```

## Export config

```bash
yokedcache export-config --output config.yaml
```

## List keys by prefix

```bash
yokedcache list --prefix users:
```

## Delete by pattern

```bash
yokedcache flush --pattern "users:*" --force
```

## Invalidate by tags

```bash
yokedcache flush --tags "user_data" --force
```
