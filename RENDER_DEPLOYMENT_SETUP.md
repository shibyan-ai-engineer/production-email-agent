# Render Deployment Setup with GitHub Actions

This document tracks the setup process for deploying to Render using GitHub Actions instead of auto-deploy.

## Completed Tasks

- [x] Updated GitHub Actions workflow to use Render Deploy Action
- [x] Disabled auto-deploy in render.yaml
- [x] Configured deployment to trigger only on main branch pushes

## In Progress Tasks

- [ ] Configure GitHub Secrets for Render API integration
- [ ] Update Render service settings to disable auto-deploy
- [ ] Test the new deployment workflow

## Future Tasks

- [ ] Add deployment status notifications
- [ ] Configure environment-specific deployments
- [ ] Add rollback capabilities

## Setup Instructions

### 1. Get Render API Key and Service ID

#### Get Render API Key:
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click on your profile → Account Settings
3. Go to "API Keys" section
4. Click "Create API Key"
5. Copy the generated API key

#### Get Service ID:
1. Go to your web service page in Render Dashboard
2. Copy the service ID from the URL (format: `srv-xxxxxxxxxxxxx`)
   - Example: If URL is `https://dashboard.render.com/web/srv-abc123def456`, then Service ID is `srv-abc123def456`

### 2. Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add these repository secrets:
```
RENDER_API_KEY = your-render-api-key-here
RENDER_SERVICE_ID = srv-xxxxxxxxxxxxx
OPENAI_API_KEY = your-openai-api-key-here (if not already added)
REDIS_URL = your-upstash-redis-url-here (if not already added)
```

### 3. Update Render Service Settings

1. Go to your Render service → Settings
2. Under "Auto-Deploy", select **"Off"**
3. Save the changes

### 4. Test the Deployment

1. Push changes to the main branch
2. GitHub Actions will run and automatically deploy to Render
3. Monitor the deployment in both GitHub Actions and Render Dashboard

## Benefits of This Approach

- **More Reliable**: Direct API calls are more reliable than waiting for GitHub status checks
- **Better Control**: Full control over when and how deployments happen
- **Clear Feedback**: Deployment status is clearly visible in GitHub Actions
- **Faster**: No waiting for Render to detect GitHub status changes

## Troubleshooting

If deployment fails:
1. Check GitHub Actions logs for error messages
2. Verify API key and Service ID are correct
3. Ensure Render service has auto-deploy disabled
4. Check Render service logs for build/deployment errors

## Relevant Files

- `.github/workflows/deploy.yml` - GitHub Actions workflow with Render deployment
- `render.yaml` - Render configuration with auto-deploy disabled
- `Dockerfile` - Docker configuration for the application
