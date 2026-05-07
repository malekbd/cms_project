# Automatic Deployment: GitHub to Main Server

## How It Works

When you push code to GitHub, it automatically deploys to your main server through this process:

### 1. **Push to GitHub**
```bash
git add .
git commit -m "Update feature"
git push origin main
```

### 2. **GitHub Actions Triggers**
- The `deploy.yml` workflow automatically runs because of:
  ```yaml
  on:
    push:
      branches: [main]
  ```

### 3. **Deployment Process**
The workflow will:
1. ✅ Check out your code
2. ✅ Connect to your server via SSH (using your secrets)
3. ✅ Create a backup of current deployment
4. ✅ Pull the latest code from GitHub
5. ✅ Install/update dependencies
6. ✅ Run database migrations
7. ✅ Collect static files
8. ✅ Restart services (Gunicorn, Nginx, CMS)
9. ✅ Perform health check
10. ✅ Clean up old backups

### 4. **Result**
Your changes are live on your main server within 2-3 minutes.

## Setup Required

### On GitHub (One-time setup):
1. Go to your repository → Settings → Secrets and variables → Actions
2. Add these secrets:
   - `SERVER_IP`: Your server's IP address (e.g., `192.168.1.100`)
   - `SERVER_USER`: SSH username (e.g., `cmsuser`)
   - `SSH_PRIVATE_KEY`: Your SSH private key

### On Your Server (One-time setup):
1. Ensure SSH is running on port 2111
2. Add GitHub Actions public key to `~/.ssh/authorized_keys`
3. Install required software (Python, Git, etc.)
4. Set up project directory at `/home/cmsuser/cms_project/`

## Testing the Setup

### 1. Test SSH Connection
```bash
# From your local machine, test connection
ssh -p 2111 cmsuser@your-server-ip
```

### 2. Test Deployment Script
```bash
# Run a dry run
./deploy.sh --dry-run
```

### 3. Make a Test Push
```bash
# Make a small change
echo "# Test" >> README.md
git add README.md
git commit -m "Test automatic deployment"
git push origin main
```

### 4. Monitor Deployment
1. Go to GitHub → Actions tab
2. Watch the "Deploy to Server" workflow
3. Check logs for any errors

## Troubleshooting

### If deployment fails:
1. **Check GitHub Actions logs** for error messages
2. **Verify SSH connection** works manually
3. **Check server permissions** for the deployment user
4. **Review server logs**:
   ```bash
   journalctl -u gunicorn -f
   journalctl -u nginx -f
   ```

### Common issues:
- **SSH connection refused**: Check firewall and port 2111
- **Permission denied**: Verify SSH key is correctly set up
- **Database migration failed**: Check database credentials in `.env`

## Manual Deployment (Alternative)

If you need to deploy without pushing to main:
1. Go to GitHub → Actions → "Deploy to Server"
2. Click "Run workflow"
3. Select environment (production)
4. Click "Run workflow"

## Rollback

If something goes wrong:
1. **Automatic**: The workflow includes automatic rollback on health check failure
2. **Manual**: SSH into server and run:
   ```bash
   cd /home/cmsuser/cms_project
   ./deploy.sh --rollback
   ```

## Security Notes

- GitHub Secrets are encrypted and never exposed in logs
- SSH keys are specific to GitHub Actions
- Backups are created before each deployment
- Health checks ensure service is running

## Monitoring

After deployment:
1. Check your website is accessible
2. Verify new features are working
3. Monitor server resources
4. Review deployment logs in `/home/cmsuser/cms_project/logs/`

## Success Message

When everything works, you'll see in GitHub Actions:
```
✅ Deployment completed successfully!
🎉 PRODUCTION deployment completed successfully!
```

Your code is now live on your main server! 🚀