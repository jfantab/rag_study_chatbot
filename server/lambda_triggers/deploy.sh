#!/bin/bash

###############################################################################
# Deploy Cognito Auto-Confirm Lambda Trigger
#
# This script deploys a Lambda function that automatically confirms users
# when they sign up, eliminating the need for email verification.
#
# Usage: ./deploy.sh
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
HANDLER="cognito_pre_signup.lambda_handler"
RUNTIME="python3.12"
ROLE_NAME="CognitoLambdaExecutionRole"

echo ""
echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}   Deploy Cognito Auto-Confirm Lambda Trigger${NC}"
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

# Check if Lambda function file exists
if [ ! -f "cognito_pre_signup.py" ]; then
    echo -e "${RED}❌ cognito_pre_signup.py not found${NC}"
    echo "Please run this script from the lambda_triggers directory"
    exit 1
fi
echo -e "${GREEN}✅ Lambda function file exists${NC}"

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
# Step 3: Read Cognito User Pool ID from .env
###############################################################################

echo ""
echo -e "${YELLOW}Step 3: Reading Cognito User Pool ID...${NC}"

ENV_FILE="../.env"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ .env file not found at $ENV_FILE${NC}"
    echo "Please create server/.env with COGNITO_USER_POOL_ID"
    exit 1
fi

USER_POOL_ID=$(grep COGNITO_USER_POOL_ID "$ENV_FILE" | cut -d '=' -f2 | tr -d ' "' | tr -d "'")

if [ -z "$USER_POOL_ID" ]; then
    echo -e "${RED}❌ COGNITO_USER_POOL_ID not set in .env${NC}"
    echo "Please add: COGNITO_USER_POOL_ID=your_pool_id_here"
    exit 1
fi

echo -e "${GREEN}✅ User Pool ID: $USER_POOL_ID${NC}"

###############################################################################
# Step 4: Create IAM Role for Lambda
###############################################################################

echo ""
echo -e "${YELLOW}Step 4: Creating IAM role for Lambda...${NC}"

ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"

# Check if role already exists
if aws iam get-role --role-name "$ROLE_NAME" &> /dev/null; then
    echo -e "${GREEN}✅ IAM role already exists: $ROLE_NAME${NC}"
else
    echo -e "${BLUE}Creating IAM role: $ROLE_NAME${NC}"

    # Create trust policy
    cat > /tmp/trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    # Create the role
    aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document file:///tmp/trust-policy.json \
        --description "Execution role for Cognito Lambda triggers"

    # Attach basic Lambda execution policy
    aws iam attach-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

    echo -e "${GREEN}✅ IAM role created${NC}"

    # Wait for role to be available
    echo -e "${BLUE}Waiting for role to propagate...${NC}"
    sleep 10
fi

###############################################################################
# Step 5: Package Lambda Function
###############################################################################

echo ""
echo -e "${YELLOW}Step 5: Packaging Lambda function...${NC}"

zip -q function.zip cognito_pre_signup.py

echo -e "${GREEN}✅ Lambda function packaged${NC}"

###############################################################################
# Step 6: Deploy Lambda Function
###############################################################################

echo ""
echo -e "${YELLOW}Step 6: Deploying Lambda function...${NC}"

# Check if function already exists
if aws lambda get-function --function-name "$FUNCTION_NAME" &> /dev/null; then
    echo -e "${BLUE}Function exists, updating code...${NC}"
    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --zip-file fileb://function.zip \
        > /dev/null
    echo -e "${GREEN}✅ Lambda function code updated${NC}"
else
    echo -e "${BLUE}Creating new Lambda function...${NC}"
    aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --runtime "$RUNTIME" \
        --role "$ROLE_ARN" \
        --handler "$HANDLER" \
        --zip-file fileb://function.zip \
        --timeout 10 \
        --memory-size 128 \
        --description "Auto-confirms Cognito users on signup" \
        > /dev/null
    echo -e "${GREEN}✅ Lambda function created${NC}"
fi

LAMBDA_ARN="arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${FUNCTION_NAME}"

###############################################################################
# Step 7: Add Lambda Permission for Cognito
###############################################################################

echo ""
echo -e "${YELLOW}Step 7: Configuring Lambda permissions...${NC}"

SOURCE_ARN="arn:aws:cognito-idp:${AWS_REGION}:${AWS_ACCOUNT_ID}:userpool/${USER_POOL_ID}"

# Remove existing permission if it exists
aws lambda remove-permission \
    --function-name "$FUNCTION_NAME" \
    --statement-id "CognitoInvoke" \
    &> /dev/null || true

# Add new permission
aws lambda add-permission \
    --function-name "$FUNCTION_NAME" \
    --statement-id "CognitoInvoke" \
    --action "lambda:InvokeFunction" \
    --principal "cognito-idp.amazonaws.com" \
    --source-arn "$SOURCE_ARN" \
    > /dev/null

echo -e "${GREEN}✅ Lambda permissions configured${NC}"

###############################################################################
# Step 8: Connect Lambda to Cognito User Pool
###############################################################################

echo ""
echo -e "${YELLOW}Step 8: Connecting Lambda to Cognito User Pool...${NC}"

aws cognito-idp update-user-pool \
    --user-pool-id "$USER_POOL_ID" \
    --lambda-config "PreSignUp=$LAMBDA_ARN"

echo -e "${GREEN}✅ Lambda trigger connected to Cognito${NC}"

###############################################################################
# Step 9: Verify Deployment
###############################################################################

echo ""
echo -e "${YELLOW}Step 9: Verifying deployment...${NC}"

# Check Lambda function
if aws lambda get-function --function-name "$FUNCTION_NAME" &> /dev/null; then
    echo -e "${GREEN}✅ Lambda function is deployed${NC}"
fi

# Check Cognito configuration
CONFIGURED_LAMBDA=$(aws cognito-idp describe-user-pool \
    --user-pool-id "$USER_POOL_ID" \
    --query 'UserPool.LambdaConfig.PreSignUp' \
    --output text)

if [ "$CONFIGURED_LAMBDA" == "$LAMBDA_ARN" ]; then
    echo -e "${GREEN}✅ Cognito trigger is configured correctly${NC}"
else
    echo -e "${RED}⚠️  Warning: Cognito trigger may not be configured correctly${NC}"
fi

###############################################################################
# Cleanup
###############################################################################

rm -f /tmp/trust-policy.json

###############################################################################
# Summary
###############################################################################

echo ""
echo -e "${GREEN}=================================================${NC}"
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo -e "${GREEN}=================================================${NC}"
echo ""
echo -e "${BLUE}Lambda Function:${NC} $FUNCTION_NAME"
echo -e "${BLUE}Region:${NC} $AWS_REGION"
echo -e "${BLUE}User Pool ID:${NC} $USER_POOL_ID"
echo ""
echo -e "${YELLOW}What happens now:${NC}"
echo "  • New users will be auto-confirmed on signup"
echo "  • No email verification required"
echo "  • Users can sign in immediately after signup"
echo ""
echo -e "${BLUE}View logs:${NC}"
echo "  aws logs tail /aws/lambda/$FUNCTION_NAME --follow"
echo ""
echo -e "${GREEN}Done! 🎉${NC}"
echo ""
