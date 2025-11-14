# Fly.io Commands

## Initial Setup
```bash
# 1. Create volume for model cache (2 GB)
fly volume create model_cache --size 2 --region ams -a ortos-bot

# 2. Deploy application
fly deploy -a ortos-bot

# 3. Enable scale to zero (min=0, max=1)
fly autoscale set min=0 max=1 --app ortos-bot
```

## Monitoring & Logs
```bash
# View logs in real-time
fly logs -a ortos-bot -f

# Check status
fly status -a ortos-bot

# List volumes
fly volumes list -a ortos-bot

# List machines
fly machines list -a ortos-bot

# Check autoscale settings
fly autoscale show -a ortos-bot
```

## Troubleshooting
```bash
# SSH into machine
fly ssh console -a ortos-bot

# Check free memory
free -h

# Rebuild if needed
fly deploy -a ortos-bot --force
```

## Cleanup (if needed)
```bash
# Delete volume
fly volume delete model_cache -a ortos-bot

# Remove app
fly apps destroy ortos-bot
```
