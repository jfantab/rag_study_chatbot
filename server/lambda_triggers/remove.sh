#!/bin/bash

###############################################################################
# Remove Cognito Auto-Confirm Lambda Trigger
#
# This script removes the Lambda function that auto-confirms users.
# Run this to enable proper email verification in your app.
#
# Usage: ./remove.sh
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
FUNCTION_NAME="CognitoPreSignupAutoConfirm"
ROLE_NAME="CognitoLambdaExecutionRole"

echo ""
echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}   Remove Cognito Auto-Confirm Lambda Trigger${NC}"
echo -e "${BLUE}=================================================${NC}"
echo ""

###############################################################################
# Step 1: Check Prerequisites
###############################################################################

echo -e "${YELLOW}Step 1: Checking prerequisites...${NC}"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI is not installed${NC}"
    echo "Please install it first:"
    echo "  macOS: brew install awscli"
    echo "  Linux: pip install awscli"
    exit 1
fi
echo -e "${GREEN}✅ AWS CLI is installed${NC}"

# Check if AWS credentials are configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS credentials are not configured${NC}"
    echo "Please run: aws configure"
    exit 1
fi
echo -e "${GREEN}✅ AWS credentials are configured${NC}"

###############################################################################
# Step 2: Get AWS Account Info
###############################################################################

echo ""
echo -e "${YELLOW}Step 2: Getting AWS account info...${NC}"

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)

if [ -z "$AWS_REGION" ]; then
    AWS_REGION="us-east-1"
    echo -e "${YELLOW}⚠️  No region configured, using default: $AWS_REGION${NC}"
fi

echo -e "${GREEN}✅ Account ID: $AWS_ACCOUNT_ID${NC}"
echo -e "${GREEN}✅ Region: $AWS_REGION${NC}"

###############################################################################
# Step 3: Get Cognito User Pool ID
###############################################################################

echo ""
echo -e "${YELLOW}Step 3: Getting Cognito User Pool ID...${NC}"

# Try to read from .env file
ENV_FILE="../.env"
if [ -f "$ENV_FILE" ]; then
    USER_POOL_ID=$(grep COGNITO_USER_POOL_ID "$ENV_FILE" | cut -d '=' -f2 | tr -d ' "' | tr -d "'")
    if [ -n "$USER_POOL_ID" ]; then
        echo -e "${GREEN}✅ User Pool ID: $USER_POOL_ID${NC}"
    else
        echo -e "${YELLOW}⚠️  Could not find COGNITO_USER_POOL_ID in .env${NC}"
        USER_POOL_ID=""
    fi
else
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    USER_POOL_ID=""
fi

###############################################################################
# Step 4: Disconnect Lambda Trigger from Cognito
###############################################################################

echo ""
echo -e "${YELLOW}Step 4: Disconnecting Lambda trigger from Cognito...${NC}"

if [ -n "$USER_POOL_ID" ]; then
    # Check if trigger exists
    CURRENT_LAMBDA=$(aws cognito-idp describe-user-pool \
        --user-pool-id "$USER_POOL_ID" \
        --query 'UserPool.LambdaConfig.PreSignUp' \
        --output text 2>/dev/null || echo "None")

    if [ "$CURRENT_LAMBDA" == "None" ] || [ -z "$CURRENT_LAMBDA" ]; then
        echo -e "${GREEN}✅ No PreSignUp trigger configured (already removed)${NC}"
    else
        echo -e "${BLUE}Removing PreSignUp trigger from User Pool...${NC}"
        aws cognito-idp update-user-pool \
            --user-pool-id "$USER_POOL_ID" \
            --lambda-config '{}'
        echo -e "${GREEN}✅ Lambda trigger disconnected from Cognito${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Skipping Cognito disconnect (User Pool ID not found)${NC}"
    echo "You can manually disconnect in AWS Console:"
    echo "  1. Go to Cognito User Pool"
    echo "  2. User pool properties → Lambda triggers"
    echo "  3. Remove PreSignUp trigger"
fi

###############################################################################
# Step 5: Delete Lambda Function
###############################################################################

echo ""
echo -e "${YELLOW}Step 5: Deleting Lambda function...${NC}"

# Check if function exists
if aws lambda get-function --function-name "$FUNCTION_NAME" &> /dev/null; then
    echo -e "${BLUE}Deleting Lambda function: $FUNCTION_NAME${NC}"
    aws lambda delete-function --function-name "$FUNCTION_NAME"
    echo -e "${GREEN}✅ Lambda function deleted${NC}"
else
    echo -e "${GREEN}✅ Lambda function doesn't exist (already deleted)${NC}"
fi

###############################################################################
# Step 6: Delete IAM Role (Optional)
###############################################################################

echo ""
echo -e "${YELLOW}Step 6: Cleaning up IAM role...${NC}"

# Check if role exists
if aws iam get-role --role-name "$ROLE_NAME" &> /dev/null 2>&1; then
    echo -e "${BLUE}Detaching policies from role...${NC}"

    # Detach managed policies
    ATTACHED_POLICIES=$(aws iam list-attached-role-policies \
        --role-name "$ROLE_NAME" \
        --query 'AttachedPolicies[].PolicyArn' \
        --output text 2>/dev/null || echo "")

    if [ -n "$ATTACHED_POLICIES" ]; then
        for policy in $ATTACHED_POLICIES; do
            aws iam detach-role-policy --role-name "$ROLE_NAME" --policy-arn "$policy"
            echo -e "${GREEN}✅ Detached policy: $policy${NC}"
        done
    fi

    # Delete inline policies
    INLINE_POLICIES=$(aws iam list-role-policies \
        --role-name "$ROLE_NAME" \
        --query 'PolicyNames[]' \
        --output text 2>/dev/null || echo "")

    if [ -n "$INLINE_POLICIES" ]; then
        for policy in $INLINE_POLICIES; do
            aws iam delete-role-policy --role-name "$ROLE_NAME" --policy-name "$policy"
            echo -e "${GREEN}✅ Deleted inline policy: $policy${NC}"
        done
    fi

    # Delete the role
    echo -e "${BLUE}Deleting IAM role: $ROLE_NAME${NC}"
    aws iam delete-role --role-name "$ROLE_NAME"
    echo -e "${GREEN}✅ IAM role deleted${NC}"
else
    echo -e "${GREEN}✅ IAM role doesn't exist (already deleted)${NC}"
fi

###############################################################################
# Summary
###############################################################################

echo ""
echo -e "${GREEN}=================================================${NC}"
echo -e "${GREEN}✅ Lambda Trigger Successfully Removed!${NC}"
echo -e "${GREEN}=================================================${NC}"
echo ""
echo -e "${BLUE}What was removed:${NC}"
echo "  • Lambda function: $FUNCTION_NAME"
echo "  • IAM role: $ROLE_NAME"
if [ -n "$USER_POOL_ID" ]; then
    echo "  • Cognito PreSignUp trigger (disconnected)"
fi
echo ""
echo -e "${BLUE}What happens now:${NC}"
echo "  • New users will need to verify their email"
echo "  • Users will receive verification codes via email"
echo "  • Email verification screen will be used in your app"
echo ""
echo -e "${YELLOW}Note:${NC} Existing users are not affected"
echo ""
echo -e "${GREEN}Done! 🎉${NC}"
echo ""
