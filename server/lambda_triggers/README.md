# Cognito Auto-Confirm Lambda Trigger

This directory contains a Lambda function that automatically confirms users when they sign up for your AWS Cognito User Pool.

## Overview

**What it does:**
- Automatically confirms users on signup (no email verification needed)
- Auto-verifies email attribute
- Allows users to sign in immediately after signup

**When to use:**
- Development environments (faster testing)
- Internal applications
- MVPs where email verification isn't critical
- When you want to streamline user onboarding

## Files

- **`cognito_pre_signup.py`** - Lambda function code
- **`deploy.sh`** - Automated deployment script
- **`update.sh`** - Quick update script for code changes
- **`remove.sh`** - Script to remove Lambda trigger
- **`README.md`** - This file

## Prerequisites

1. **AWS CLI installed**
   ```bash
   # macOS
   brew install awscli

   # Linux
   pip install awscli
   ```

2. **AWS credentials configured**
   ```bash
   aws configure
   # Enter your AWS Access Key ID, Secret Access Key, and region
   ```

3. **Cognito User Pool created**
   - User Pool ID must be set in `server/.env` as `COGNITO_USER_POOL_ID`

4. **Proper IAM permissions**
   - Your AWS user needs permissions to:
     - Create/update Lambda functions
     - Create IAM roles
     - Update Cognito User Pools
     - Add Lambda permissions

## Quick Start

### First-Time Deployment

```bash
cd server/lambda_triggers

# Run the deployment script
./deploy.sh
```

The script will:
1. ✅ Check prerequisites (AWS CLI, credentials)
2. ✅ Detect AWS account ID and region
3. ✅ Read User Pool ID from `server/.env`
4. ✅ Create IAM execution role (if needed)
5. ✅ Package Lambda function
6. ✅ Deploy Lambda function to AWS
7. ✅ Configure permissions
8. ✅ Connect Lambda to Cognito User Pool
9. ✅ Verify deployment

### Updating Lambda Code

If you make changes to `cognito_pre_signup.py`:

```bash
# Quick update (much faster than full deploy)
./update.sh
```

## Testing

### Test Auto-Confirmation

1. **Sign up a new user** in your mobile app
2. **User should be immediately confirmed** (no email verification needed)
3. **User can sign in right away**

### View CloudWatch Logs

```bash
# Watch logs in real-time
aws logs tail /aws/lambda/CognitoPreSignupAutoConfirm --follow

# View recent logs
aws logs tail /aws/lambda/CognitoPreSignupAutoConfirm --since 1h
```

### Verify in AWS Console

1. Go to **Amazon Cognito Console**
2. Navigate to your User Pool
3. Click **Users** tab
4. New users should show status: **CONFIRMED** ✅

## How It Works

### Lambda Trigger Flow

```
User signs up
    ↓
Cognito invokes PreSignUp Lambda trigger
    ↓
Lambda sets: autoConfirmUser = True
Lambda sets: autoVerifyEmail = True
    ↓
Cognito creates user with status: CONFIRMED
    ↓
User can sign in immediately
```

### Lambda Function Logic

```python
def lambda_handler(event, context):
    # Auto-confirm the user (skip email verification)
    event['response']['autoConfirmUser'] = True

    # Auto-verify email attribute
    event['response']['autoVerifyEmail'] = True

    return event
```

## Removing Auto-Confirmation

If you want to enable proper email verification:

```bash
./remove.sh
```

This will:
- Disconnect Lambda trigger from Cognito
- Delete the Lambda function
- Clean up IAM roles

After removal, your app will use the `EmailVerificationScreen` for user verification.

## Troubleshooting

### Issue: "AWS CLI is not installed"
**Solution:**
```bash
brew install awscli  # macOS
# or
pip install awscli  # Linux/Windows
```

### Issue: "AWS credentials are not configured"
**Solution:**
```bash
aws configure
# Enter your Access Key ID, Secret Access Key, and region
```

### Issue: "COGNITO_USER_POOL_ID not set in .env"
**Solution:**
- Ensure `server/.env` exists
- Add line: `COGNITO_USER_POOL_ID=your_user_pool_id_here`
- Replace with your actual User Pool ID from AWS Console

### Issue: Lambda not triggering
**Solution:**
1. Check CloudWatch Logs for errors
2. Verify Lambda is connected in Cognito Console:
   - Go to User Pool → User pool properties → Lambda triggers
   - Should see `CognitoPreSignupAutoConfirm` under "Pre sign-up trigger"
3. Check Lambda permissions:
   ```bash
   aws lambda get-policy --function-name CognitoPreSignupAutoConfirm
   ```

### Issue: Users still receiving verification emails
**Solution:**
1. Check if Lambda is actually being invoked:
   ```bash
   aws logs tail /aws/lambda/CognitoPreSignupAutoConfirm --follow
   ```
2. Sign up a new user and watch logs
3. If no logs appear, Lambda trigger isn't connected properly
4. Re-run `./deploy.sh`

## Security Considerations

### Risks of Auto-Confirmation

1. **Email Spoofing**: Users can sign up with emails they don't own
2. **Bot Accounts**: Easier for bots to create fake accounts
3. **Spam**: Potential for abuse without verification

### Mitigation Strategies

1. **Add CAPTCHA**: Use reCAPTCHA on signup form
2. **Rate Limiting**: Limit signups per IP address
3. **Email Domain Validation**: Only allow specific domains
4. **Admin Approval**: Require admin to approve new accounts
5. **Monitoring**: Set up CloudWatch alarms for unusual signup patterns

## AWS Resources Created

This deployment creates:

1. **IAM Role**: `CognitoLambdaExecutionRole`
   - Allows Lambda to write CloudWatch logs

2. **Lambda Function**: `CognitoPreSignupAutoConfirm`
   - Runtime: Python 3.12
   - Memory: 128 MB
   - Timeout: 10 seconds

3. **Lambda Permission**: Allows Cognito to invoke function

4. **Cognito Trigger**: PreSignUp trigger configured on User Pool

## Cost Estimate

Lambda costs are very low for this use case:

- **Lambda invocations**: $0.20 per 1 million requests
- **Compute time**: $0.0000166667 per GB-second
- **Free tier**: 1 million requests/month

**Example:**
- 1000 signups/month = ~$0.0002 (essentially free)
- 10,000 signups/month = ~$0.002

## Additional Resources

- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [Cognito Lambda Triggers](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-identity-pools-working-with-aws-lambda-triggers.html)
- [Pre-Signup Lambda Trigger](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-lambda-pre-sign-up.html)
