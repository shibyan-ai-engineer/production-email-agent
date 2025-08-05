# Complete Render Deployment Guide for FastAPI Email Assistant

This guide provides step-by-step instructions for deploying the FastAPI Email Assistant to Render's free tier using Docker and Upstash Redis Stack.

## Prerequisites

1. **GitHub Account**: Your code repository
2. **Render Account**: Sign up at [render.com](https://render.com)
3. **Upstash Account**: Sign up at [upstash.com](https://upstash.com) for free Redis Stack
4. **OpenAI API Key**: Required for the email assistant functionality
5. **LangSmith API Key**: Optional, for tracing and monitoring

## Architecture Overview

- **FastAPI Web Service**: Deployed on Render (free tier)
- **Redis Stack**: Hosted on Upstash (free tier with Redis Stack modules)
- **CI/CD**: GitHub Actions for automated deployment

## Step 1: Set Up Upstash Redis Stack

1. **Create Upstash account** at [upstash.com](https://upstash.com)
2. **Create a new Redis database**:
   - Click "Create Database"
   - Name: `email-assistant-redis`
   - Region: Choose closest to `Oregon` (where Render free tier runs)
   - Type: Regional (free tier)
   - Click "Create"
3. **Get connection details**:
   - From database dashboard, copy the `UPSTASH_REDIS_REST_URL`
   - Format will be: `redis://default:password@region.upstash.io:port`
   - Note: Upstash provides Redis Stack modules by default

## Step 2: Prepare Your Repository

1. **Ensure all deployment files are committed:**
   ```bash
   git add .
   git commit -m "Add deployment configuration"
   git push origin main
   ```

2. **Verify your GitHub repository** contains all deployment files

## Step 3: Create Render Web Service

1. In Render Dashboard, click **"New"** → **"Web Service"**
2. Choose **"Build and deploy from a Git repository"**
3. Connect your GitHub repository: `https://github.com/shibyan-ai-engineer/production-email-agent`
4. Configure the service:

   **Basic Settings:**
   - **Name**: `email-assistant`
   - **Region**: `Oregon` (free tier)
   - **Branch**: `main`
   - **Language**: `Docker`
   
   **Build Settings:**
   - **Dockerfile Path**: `Dockerfile` (default)
   - **Build Command**: Leave empty (Docker handles this)
   - **Start Command**: Leave empty (Docker CMD handles this)

   **Instance Settings:**
   - **Plan**: `Free`

   **Advanced Settings:**
   - **Health Check Path**: `/health`
   - **Environment Variables**:
     ```
     OPENAI_API_KEY = your-openai-api-key-here
     REDIS_URL = redis://default:password@region.upstash.io:port
     LANGSMITH_API_KEY = your-langsmith-key-here (optional)
     LANGSMITH_TRACING = true
     LANGSMITH_ENDPOINT = https://api.smith.langchain.com
     LANGSMITH_PROJECT = LangGraph-Production-Agent
     ```

5. Click **"Create Web Service"**

## Step 4: Configure CI/CD (Optional)

To enable automatic deployments:

1. **Get Render API Key:**
   - Go to Render Dashboard → Account Settings → API Keys
   - Create a new API key

2. **Get Service ID:**
   - Go to your web service page
   - Copy the service ID from the URL

3. **Configure GitHub Secrets:**
   - Go to your GitHub repository → Settings → Secrets and variables → Actions
   - Add these repository secrets:
     ```
     RENDER_API_KEY = your-render-api-key
     RENDER_SERVICE_ID = srv-xxxxxxxxxxxxx
     OPENAI_API_KEY = your-openai-api-key
     ```

## Step 5: Test Local Development (Optional)

Test the Docker setup locally before deployment:

1. **Create local .env file:**
   ```bash
   cp .env.example .env
   # Edit .env with your actual API keys and Upstash Redis URL
   ```

2. **Run with Docker:**
   ```bash
   docker build -t email-assistant .
   docker run -p 8000:8000 --env-file .env email-assistant
   ```

3. **Test the application:**
   - Open http://localhost:8000/docs
   - Verify the health check: http://localhost:8000/health

## Step 6: Deploy and Verify

1. **Automatic Deployment:**
   - Push to main branch triggers automatic deployment (if CI/CD is configured)
   - Or manually deploy from Render Dashboard

2. **Manual Deployment:**
   - Go to your web service in Render Dashboard
   - Click **"Manual Deploy"** → **"Deploy latest commit"**

3. **Monitor Deployment:**
   - Watch the build logs in Render Dashboard
   - Deployment typically takes 5-10 minutes

4. **Verify Deployment:**
   - Check your service URL: `https://your-service-name.onrender.com`
   - Test health endpoint: `https://your-service-name.onrender.com/health`
   - Test API documentation: `https://your-service-name.onrender.com/docs`

## Step 6: Test Email Processing

Test your deployed application:

```bash
curl -X POST "https://your-service-name.onrender.com/process-email" \
  -H "Content-Type: application/json" \
  -d '{
    "author": "test@example.com",
    "subject": "Test Email",
    "thread": "This is a test email to verify the deployment."
  }'
```

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for GPT-4 |
| `REDIS_URL` | Yes | Redis Stack connection URL (auto-set by Render) |
| `PORT` | No | Application port (auto-set by Render) |
| `LANGSMITH_API_KEY` | No | LangSmith API key for tracing |
| `LANGSMITH_TRACING` | No | Enable LangSmith tracing (`true`/`false`) |
| `LANGSMITH_ENDPOINT` | No | LangSmith endpoint URL |
| `LANGSMITH_PROJECT` | No | LangSmith project name |

## Troubleshooting

### Common Issues

1. **Build Fails:**
   - Check Dockerfile syntax
   - Verify all dependencies in pyproject.toml
   - Check build logs in Render Dashboard

2. **Redis Connection Errors:**
   - Verify Redis service is running
   - Check REDIS_URL environment variable
   - Ensure both services are in the same region

3. **Application Won't Start:**
   - Check application logs in Render Dashboard
   - Verify PORT environment variable usage
   - Check health check endpoint

4. **API Errors:**
   - Verify OPENAI_API_KEY is set correctly
   - Check OpenAI API quota and billing
   - Review application logs

### Debugging Commands

```bash
# View application logs
# Go to Render Dashboard → Your Service → Logs

# Connect to Redis CLI (if needed)
# Use Render Dashboard → Redis Service → Connect

# Test local Docker build
docker build -t email-assistant .
docker run -p 8000:8000 --env-file .env email-assistant

# Check Docker image size
docker images email-assistant
```

## Free Tier Limitations

**Render Free Tier includes:**
- Web services go to sleep after 15 minutes of inactivity
- 512 MB RAM, 0.1 CPU
- 750 hours/month of runtime
- Free Redis instances don't persist data (restart = data loss)

**Recommendations:**
- For production, consider upgrading to paid tiers for reliability
- Free tier is perfect for testing and development

## Security Best Practices

1. **Never commit API keys** to Git
2. **Use environment variables** for all secrets
3. **Enable internal authentication** for Redis in production
4. **Regularly rotate API keys**
5. **Monitor API usage** and costs

## Next Steps

1. **Custom Domain**: Add your domain in Render Dashboard
2. **Monitoring**: Set up alerts and monitoring
3. **Scaling**: Upgrade plans for higher traffic
4. **Backups**: Consider Redis data persistence on paid plans

Your FastAPI Email Assistant is now deployed and accessible at:
`https://your-service-name.onrender.com`
