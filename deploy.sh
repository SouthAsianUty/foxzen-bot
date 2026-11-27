#!/bin/bash
# ==========================================================
# 🦊 Foxzen Bot - 1-Click Fast Deploy to Hostinger VPS
# ==========================================================

# Apne Hostinger VPS ka IP address yahan daalein:
VPS_IP="YOUR_VPS_IP"
VPS_USER="root"
VPS_PATH="/root/Foxzen_bot"

if [ "$VPS_IP" = "YOUR_VPS_IP" ]; then
    echo "❌ Error: Pehle deploy.sh ko open karke line 7 par apna Hostinger VPS IP daalein!"
    exit 1
fi

echo "🚀 Syncing modified files to Hostinger VPS ($VPS_IP)..."

# rsync sirf unhi files ko bhejta hai jo change hui hain (takes 1-2 seconds)
# Important: bot_database.db ko exclude rakha hai taaki VPS ka live customer data safe rahe
rsync -avz --progress \
  --exclude '.venv' \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '*/__pycache__' \
  --exclude '.DS_Store' \
  --exclude 'bot_database.db' \
  --exclude 'foxzen_deploy.zip' \
  ./ "$VPS_USER@$VPS_IP:$VPS_PATH/"

echo "🔄 Restarting Foxzen bot service on VPS..."
ssh "$VPS_USER@$VPS_IP" "systemctl restart foxzen && systemctl status foxzen --no-pager | grep -E 'Active:|Main PID'"

echo "🎉 Done! Aapke changes instant Hostinger VPS par live ho gaye hain!"
