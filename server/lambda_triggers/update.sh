#!/bin/bash

###############################################################################
# Quick Update Lambda Function
#
# Fast way to update Lambda code without full redeployment
# Use this after making changes to cognito_pre_signup.py
#
# Usage: ./update.sh
###############################################################################

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

FUNCTION_NAME="CognitoPreSignupAutoConfirm"

echo ""
echo -e "${BLUE}Updating Lambda function...${NC}"

# Check if function file exists
if [ ! -f "cognito_pre_signup.py" ]; then
    echo -e "${RED}❌ cognito_pre_signup.py not found${NC}"
    exit 1
fi

# Package function
echo -e "${BLUE}Packaging code...${NC}"
zip -q function.zip cognito_pre_signup.py

# Update function code
echo -e "${BLUE}Uploading to AWS...${NC}"
aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file fileb://function.zip \
    > /dev/null

echo -e "${GREEN}✅ Lambda function updated!${NC}"
echo ""
echo -e "${BLUE}View logs:${NC}"
echo "  aws logs tail /aws/lambda/$FUNCTION_NAME --follow"
echo ""
