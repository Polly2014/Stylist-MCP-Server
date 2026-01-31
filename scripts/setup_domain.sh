#!/bin/bash
# Setup script for stylist.polly.wang domain
# Run with: sudo ./setup_domain.sh

set -e

DOMAIN="stylist.polly.wang"
NGINX_CONF="/home/azureuser/GitHub_Workspace/Stylist-MCP-Server/config/nginx_stylist.polly.wang.conf"

echo "🌐 Setting up domain: $DOMAIN"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (sudo ./setup_domain.sh)"
    exit 1
fi

# Step 1: Check DNS resolution
echo ""
echo "📡 Step 1: Checking DNS resolution..."
DNS_IP=$(dig +short $DOMAIN 2>/dev/null || echo "")
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "unknown")

if [ -z "$DNS_IP" ]; then
    echo "⚠️  WARNING: DNS record for $DOMAIN not found!"
    echo ""
    echo "   Please add an A record in your DNS provider:"
    echo "   ┌────────────────────────────────────────┐"
    echo "   │ Type: A                                │"
    echo "   │ Name: stylist                          │"
    echo "   │ Value: $SERVER_IP                      │"
    echo "   └────────────────────────────────────────┘"
    echo ""
    read -p "Press Enter after adding DNS record, or Ctrl+C to cancel..."
elif [ "$DNS_IP" != "$SERVER_IP" ]; then
    echo "⚠️  WARNING: DNS points to $DNS_IP but server IP is $SERVER_IP"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✅ DNS correctly points to $SERVER_IP"
fi

# Step 2: Install Nginx config
echo ""
echo "📝 Step 2: Installing Nginx configuration..."
cp "$NGINX_CONF" /etc/nginx/sites-available/$DOMAIN
ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/$DOMAIN
echo "✅ Nginx configuration installed"

# Step 3: Test Nginx configuration
echo ""
echo "🔍 Step 3: Testing Nginx configuration..."
nginx -t
echo "✅ Nginx configuration is valid"

# Step 4: Reload Nginx
echo ""
echo "🔄 Step 4: Reloading Nginx..."
systemctl reload nginx
echo "✅ Nginx reloaded"

# Step 5: Setup SSL with Certbot
echo ""
echo "🔒 Step 5: Setting up SSL certificate with Let's Encrypt..."
read -p "Install SSL certificate now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@polly.wang || {
        echo "⚠️  Certbot failed. You may need to run manually:"
        echo "   sudo certbot --nginx -d $DOMAIN"
    }
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "   Your MCP Server should now be accessible at:"
echo "   ┌─────────────────────────────────────────────┐"
echo "   │ https://$DOMAIN                     │"
echo "   │ https://$DOMAIN/health (health check) │"
echo "   │ https://$DOMAIN/sse (SSE endpoint)    │"
echo "   └─────────────────────────────────────────────┘"
echo ""
echo "   Make sure your MCP server is running:"
 echo "   cd /home/azureuser/GitHub_Workspace/Stylist-MCP-Server"
 echo "   source venv/bin/activate"
 echo "   python src/mcp_server.py --sse --port 8888"