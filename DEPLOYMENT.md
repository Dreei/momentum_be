# 🚀 Secure Deployment Guide for Render

This guide covers secure deployment of the Momentum Backend API to Render with production-ready security practices.

## 🔒 Security Features Implemented

### ✅ Fixed Security Issues
- **Removed hardcoded API keys** from `crud.py`
- **Removed hardcoded Supabase credentials**
- **Pinned all dependency versions** in `requirements.txt`
- **Added security-focused packages**
- **Implemented environment variable management**

### 🛡️ Security Measures
- All sensitive data moved to environment variables
- Production-ready Dockerfile with non-root user
- Comprehensive `.dockerignore` for security
- Pinned dependency versions to prevent supply chain attacks
- Separate development and production requirements

## 📋 Pre-Deployment Checklist

### 1. Environment Variables Required
```bash
# Core Application
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=your-super-secret-jwt-key-change-this-in-production

# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_JWT_SECRET=your-supabase-jwt-secret

# AI Services
GEMINI_API_KEY=your-gemini-api-key

# Email
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=your-email@gmail.com

# OAuth
GOOGLE_CLIENT_ID=your-google-client-id
ZOOM_CLIENT_ID=your-zoom-client-id
ZOOM_CLIENT_SECRET=your-zoom-client-secret

# Recall.ai
RECALL_API_TOKEN=your-recall-api-token
RECALL_WEBHOOK_SECRET=your-webhook-secret
```

### 2. Security Best Practices

#### 🔐 API Keys & Secrets
- **Never commit `.env` files** to version control
- **Use strong, unique secrets** for production
- **Rotate API keys regularly**
- **Use Render's secret management** for sensitive data

#### 🌐 Network Security
- **Enable HTTPS only** in production
- **Configure CORS properly** for your frontend domain
- **Use secure webhook URLs** with HTTPS

#### 🔍 Monitoring
- **Enable Render's logging** and monitoring
- **Set up health checks** (`/health` endpoint)
- **Monitor for security vulnerabilities**

## 🚀 Deployment Steps

### Option 1: Using Render Dashboard (Recommended)

1. **Connect Repository**
   ```bash
   # Connect your GitHub repository to Render
   # Repository: your-username/momentum-backend
   ```

2. **Configure Service**
   - **Name**: `momentum-backend`
   - **Environment**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

3. **Set Environment Variables**
   - Go to Environment tab in Render Dashboard
   - Add all required environment variables (see checklist above)
   - Use "Generate Value" for `SECRET_KEY`

4. **Deploy**
   - Click "Deploy Latest Commit"
   - Monitor deployment logs

### Option 2: Using render.yaml (Blueprint)

1. **Update render.yaml**
   ```yaml
   # Update the service name and URLs in render.yaml
   # Replace 'momentum-backend' with your preferred name
   ```

2. **Deploy with Blueprint**
   ```bash
   # Render will automatically detect render.yaml
   # and configure your service accordingly
   ```

## 🔧 Post-Deployment Configuration

### 1. Update External Services

#### Zoom OAuth
```bash
# Update redirect URI in Zoom App settings
Redirect URI: https://your-app.onrender.com/zoom/callback
```

#### Recall.ai Webhooks
```bash
# Update webhook URL in Recall.ai settings
Webhook URL: https://your-app.onrender.com/api/recall/webhook
```

### 2. Test Deployment
```bash
# Health check
curl https://your-app.onrender.com/health

# API documentation
https://your-app.onrender.com/docs
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Import Errors
```bash
# If you see ML library import errors
# Check that all dependencies are installed
pip install -r requirements.txt
```

#### 2. Environment Variables
```bash
# Verify all required env vars are set
# Check Render Dashboard > Environment tab
```

#### 3. Database Connection
```bash
# Verify Supabase credentials
# Check Supabase project settings
```

### 4. API Key Issues
```bash
# Ensure API keys are valid and not expired
# Check service provider dashboards
```

## 📊 Monitoring & Maintenance

### 1. Regular Updates
- **Update dependencies** monthly
- **Monitor security advisories**
- **Rotate API keys** quarterly

### 2. Performance Monitoring
- **Monitor response times** in Render Dashboard
- **Check error rates** and logs
- **Scale resources** as needed

### 3. Security Monitoring
- **Review access logs** regularly
- **Monitor for unusual activity**
- **Keep dependencies updated**

## 🆘 Support

If you encounter issues:
1. Check Render deployment logs
2. Verify all environment variables are set
3. Test API endpoints individually
4. Check external service configurations

## 📚 Additional Resources

- [Render Documentation](https://render.com/docs)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
- [Supabase Security Guide](https://supabase.com/docs/guides/auth/security)
- [Python Security Best Practices](https://python.org/dev/security/)

---

**⚠️ Important**: Always test your deployment in a staging environment before going to production! 