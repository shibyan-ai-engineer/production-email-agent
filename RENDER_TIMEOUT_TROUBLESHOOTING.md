# Render Deployment Timeout Troubleshooting Guide

## Issue: Manual and Automated Deployments Timing Out

This guide helps resolve timeout issues when deploying to Render.

## Root Causes of Deployment Timeouts

### 1. **Docker Build Issues**
- **Large Docker Image**: Base images or dependencies causing slow builds
- **Network Issues**: Slow package downloads during build
- **Build Command Problems**: Incorrect or inefficient build processes

### 2. **Render Service Configuration**
- **Insufficient Resources**: Free tier limitations (512MB RAM, 0.1 CPU)
- **Health Check Failures**: Application not responding on health endpoint
- **Environment Variables**: Missing or incorrect configuration

### 3. **Application Startup Issues**
- **Slow Application Boot**: Dependencies taking too long to initialize
- **Port Binding Problems**: Application not binding to correct port
- **Database Connection Issues**: Redis connection timeouts

## Immediate Troubleshooting Steps

### Step 1: Check Render Service Logs
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Navigate to your service
3. Check **Logs** tab for error messages
4. Look for specific error patterns:
   ```
   - "Build failed"
   - "Health check failed"
   - "Port binding error"
   - "Connection timeout"
   ```

### Step 2: Verify Docker Configuration Locally
```bash
# Test Docker build locally
docker build -t test-email-assistant .

# Test Docker run locally
docker run -p 8000:8000 --env-file .env test-email-assistant

# Check if health endpoint works
curl http://localhost:8000/health
```

### Step 3: Check Environment Variables
Ensure these are properly set in Render:
- `OPENAI_API_KEY`
- `REDIS_URL`
- `PORT` (should be auto-set by Render)

### Step 4: Optimize Docker Build

If your Dockerfile is causing timeouts, here's an optimized version:

```dockerfile
# Use Python 3.11 slim for smaller image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install UV package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files first (for better caching)
COPY pyproject.toml uv.lock ./

# Install dependencies in virtual environment
RUN uv sync --frozen --no-cache

# Copy source code
COPY src/ ./src/

# Install the package
RUN uv pip install -e .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Start command
CMD ["uv", "run", "uvicorn", "src.email_assistant.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Solution Implemented

### 1. **Switched to Direct API Calls**
- Removed third-party GitHub Action that was causing issues
- Using Render's official REST API for deployment
- Added comprehensive error handling and debugging

### 2. **Async Deployment Approach**
- GitHub Actions triggers deployment and exits
- Deployment continues in background on Render
- No more timeout issues in GitHub Actions

### 3. **Enhanced Debugging**
- Added service ID validation
- API key length verification
- Detailed HTTP response logging

## Testing the New Approach

### Step 1: Verify GitHub Secrets
Make sure these secrets are correctly set:
```
RENDER_SERVICE_ID = srv-xxxxxxxxxxxxxxx
RENDER_API_KEY = your-api-key-here
```

### Step 2: Push Changes and Monitor
```bash
git push origin main
```

### Step 3: Check GitHub Actions Logs
Look for:
- ✅ Service ID validation
- ✅ API call success (HTTP 201)
- ✅ Deploy ID returned

### Step 4: Monitor Render Dashboard
- Check Events tab for deployment progress
- Monitor Logs tab for build/deployment logs
- Verify service comes online after deployment

## Common Issues and Solutions

### Issue: 404 Error from Render API
**Cause**: Incorrect Service ID or API key doesn't have permissions
**Solution**: 
1. Double-check Service ID format: `srv-xxxxxxxxxxxxxxx`
2. Regenerate API key in Render Dashboard
3. Ensure API key has deployment permissions

### Issue: Build Timeout on Render
**Cause**: Docker build taking too long
**Solution**:
1. Optimize Dockerfile for faster builds
2. Use smaller base images
3. Implement multi-stage builds if needed

### Issue: Health Check Failures
**Cause**: Application not responding on `/health` endpoint
**Solution**:
1. Verify health endpoint implementation
2. Check application startup logs
3. Ensure correct port binding

### Issue: Redis Connection Timeout
**Cause**: Incorrect Redis URL or network issues
**Solution**:
1. Verify Upstash Redis URL format
2. Check Redis service status
3. Test connection locally

## Alternative Deployment Methods

If issues persist, try these alternatives:

### 1. **Deploy Hook Method**
```yaml
- name: Deploy via Webhook
  run: |
    curl -X POST "${{ secrets.RENDER_DEPLOY_HOOK_URL }}"
```

### 2. **Manual Deployment**
- Push code to GitHub
- Manually trigger deployment in Render Dashboard
- Monitor deployment progress

### 3. **Local Docker Registry**
- Build image locally
- Push to Docker Hub
- Deploy from registry on Render

## Monitoring and Alerts

### Set Up Monitoring
1. Enable email notifications in Render
2. Set up Slack/Discord webhooks
3. Monitor application metrics

### Health Check Best Practices
```python
@app.get("/health")
async def health_check():
    try:
        # Test Redis connection
        await redis_client.ping()
        return {"status": "healthy", "timestamp": datetime.now()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Unhealthy: {str(e)}")
```

## Next Steps

1. **Test the new API-based deployment**
2. **Monitor deployment logs carefully**
3. **Optimize Docker build if timeouts persist**
4. **Consider upgrading to paid tier for more resources**

The new approach should resolve the timeout issues by making GitHub Actions just trigger the deployment and exit, rather than waiting for the entire deployment process to complete.
