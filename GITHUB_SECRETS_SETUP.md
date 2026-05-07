# GitHub Secrets Configuration Guide

This guide explains how to configure the required secrets for the CI/CD pipeline to work properly.

## Overview

GitHub Secrets are encrypted environment variables that you can use in your GitHub Actions workflows. They are essential for secure deployment and should never be committed to your repository.

## Required Secrets

### 1. **SERVER_IP** (Required)
The IP address or hostname of your production server.

**How to get it:**
```bash
# On your server, run:
hostname -I
# or check your hosting provider's dashboard
```

**Example:** `192.168.1.100` or `cms.example.com`

### 2. **SERVER_USER** (Required)
The SSH username for connecting to your server.

**Common values:**
- `ubuntu` (for Ubuntu servers)
- `root` (for root access, not recommended)
- `cmsuser` (custom user you created)

**Example:** `cmsuser`

### 3. **SSH_PRIVATE_KEY** (Required)
The private SSH key for authentication. This should be the **private** key that matches the public key installed on your server.

**How to generate (if you don't have one):**
```bash
# On your local machine
ssh-keygen -t rsa -b 4096 -C "github-actions@cms-project" -f ~/.ssh/cms_github_actions

# Copy the public key to your server
ssh-copy-id -i ~/.ssh/cms_github_actions.pub cmsuser@your-server-ip
```

**How to get the private key content:**
```bash
# On your local machine
cat ~/.ssh/cms_github_actions
```

The content should look like:
```
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA3Vz8w9Lk4V7v8w9Lk4V7v8w9Lk4V7v8w9Lk4V7v8w9Lk4V7v
...
-----END RSA PRIVATE KEY-----
```

**⚠️ Important:** Copy the ENTIRE content including the `-----BEGIN` and `-----END` lines.

### 4. **STAGING_SERVER_IP** (Optional)
If you have a separate staging environment, provide its IP address.

**Example:** `192.168.1.101`

### 5. **SLACK_WEBHOOK_URL** (Optional)
For deployment notifications to Slack.

**How to get it:**
1. Go to your Slack workspace
2. Add "Incoming Webhooks" app
3. Create a webhook for your channel
4. Copy the webhook URL

**Example:** `https://hooks.slack.com/services/...` (replace with your actual webhook)

## Setting Up Secrets in GitHub

### Method 1: Web Interface (Recommended)
1. Go to your GitHub repository
2. Click **Settings** (gear icon)
3. In the left sidebar, click **Secrets and variables** → **Actions**
4. Click **New repository secret**
5. Enter the secret name and value
6. Click **Add secret**

### Method 2: GitHub CLI
```bash
# Install GitHub CLI first
gh secret set SERVER_IP --body "192.168.1.100"
gh secret set SERVER_USER --body "cmsuser"
gh secret set SSH_PRIVATE_KEY < ~/.ssh/cms_github_actions
```

### Method 3: GitHub API
```bash
curl -X POST -H "Authorization: token YOUR_GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/OWNER/REPO/actions/secrets/SERVER_IP \
  -d '{"encrypted_value":"ENCRYPTED_VALUE", "key_id":"KEY_ID"}'
```

## Verifying Secrets

### 1. Test SSH Connection
```bash
# Test manually from your local machine
ssh -i ~/.ssh/cms_github_actions -p 2111 cmsuser@your-server-ip
```

### 2. Create a Test Workflow
Create a test workflow file `.github/workflows/test-secrets.yml`:

```yaml
name: Test Secrets

on:
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Test SSH Connection
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.SERVER_IP }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          port: 2111
          script: |
            echo "Connected successfully!"
            whoami
            pwd
```

### 3. Check Secret Availability
GitHub Actions will show an error if a required secret is missing when the workflow runs.

## Security Best Practices

### 1. **Principle of Least Privilege**
- Create a dedicated deployment user on your server
- Limit permissions to only what's necessary
- Don't use root user for deployments

### 2. **Key Management**
- Generate a unique SSH key pair for GitHub Actions
- Don't reuse personal SSH keys
- Rotate keys periodically (every 90 days recommended)

### 3. **Access Control**
- Restrict who can modify secrets in GitHub
- Use GitHub environments for additional protection
- Audit secret usage regularly

### 4. **Monitoring**
- Enable audit logs in GitHub
- Monitor failed deployment attempts
- Set up alerts for suspicious activity

## Troubleshooting

### Common Issues

#### 1. "Permission denied (publickey)"
- Verify the SSH private key is correctly copied (no extra spaces/lines)
- Check if the public key is in `~/.ssh/authorized_keys` on the server
- Ensure the server allows SSH key authentication

#### 2. "Connection timed out"
- Check firewall settings on the server
- Verify the server is running and accessible
- Ensure port 2111 (or your SSH port) is open

#### 3. "Secret not found"
- Verify the secret name matches exactly what's in the workflow
- Check if you're in the correct repository
- Ensure you have permission to access secrets

#### 4. "Host key verification failed"
Add to your workflow:
```yaml
with:
  ...
  script: |
    mkdir -p ~/.ssh
    ssh-keyscan -H ${{ secrets.SERVER_IP }} >> ~/.ssh/known_hosts
    # rest of your script
```

## Server Configuration Checklist

Before setting up secrets, ensure your server is properly configured:

- [ ] SSH server is running on port 2111 (or your chosen port)
- [ ] Firewall allows incoming connections on port 2111
- [ ] Deployment user exists (`cmsuser` or similar)
- [ ] User has write permissions to project directory
- [ ] SSH public key is in `~/.ssh/authorized_keys`
- [ ] Python and required dependencies are installed
- [ ] Database is set up and accessible
- [ ] Nginx and Gunicorn are configured

## Advanced: Using GitHub Environments

For better security and organization, use GitHub Environments:

1. **Create environments** in repository settings:
   - `production`
   - `staging`

2. **Assign secrets to specific environments**
3. **Add protection rules** (required reviewers, wait timer)

4. **Update workflow to use environments:**
```yaml
deploy-production:
  environment: production
  ...
```

## Maintenance

### Regular Tasks
1. **Rotate SSH keys** every 90 days
2. **Review secret access** monthly
3. **Update documentation** when changes are made
4. **Test backup and restore** procedures

### Emergency Procedures
If a secret is compromised:
1. Immediately rotate the affected secret
2. Revoke old SSH keys from the server
3. Generate new key pair
4. Update all workflows using the secret
5. Investigate potential unauthorized access

## Support

For issues with secret configuration:
1. Check GitHub Actions logs for specific error messages
2. Test SSH connection manually from your local machine
3. Review server SSH configuration (`/etc/ssh/sshd_config`)
4. Consult the deployment guide for server setup details

## Related Documentation
- `CD_CI_SETUP.md` - Complete CI/CD setup guide
- `DEPLOYMENT_GUIDE.md` - Server deployment instructions
- `SECURITY_CHECKLIST.md` - Security best practices