"""
Authentication service for JWT validation and Cognito integration
"""
import os
import requests
import time
import boto3
from jose import jwk, jwt as jose_jwt
from functools import wraps
from flask import request, jsonify
from constants import AWS_REGION, COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID, COGNITO_IDENTITY_POOL_ID, KEYS_CACHE_DURATION

# Cache for Cognito public keys
_cognito_public_keys = None
_keys_cache_time = 0


def get_cognito_public_keys():
    """Fetch and cache Cognito public keys for JWT validation"""
    global _cognito_public_keys, _keys_cache_time

    current_time = time.time()
    if _cognito_public_keys and (current_time - _keys_cache_time) < KEYS_CACHE_DURATION:
        return _cognito_public_keys

    try:
        keys_url = f'https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json'
        response = requests.get(keys_url)
        response.raise_for_status()

        _cognito_public_keys = response.json()
        _keys_cache_time = current_time
        return _cognito_public_keys

    except Exception as e:
        print(f"❌ Error fetching Cognito public keys: {str(e)}")
        return None


def get_cognito_identity_id_from_token(id_token):
    """Get Cognito Identity ID from ID token using Cognito Identity Pool"""
    try:
        cognito_identity_client = boto3.client('cognito-identity', region_name=AWS_REGION)

        response = cognito_identity_client.get_id(
            IdentityPoolId=COGNITO_IDENTITY_POOL_ID,
            Logins={
                f'cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}': id_token
            }
        )

        identity_id = response.get('IdentityId')
        if not identity_id:
            raise Exception("Failed to get Cognito Identity ID")

        return identity_id

    except Exception as e:
        print(f"❌ Error getting Cognito Identity ID: {str(e)}")
        raise Exception(f"Failed to get Identity ID: {str(e)}")


def validate_jwt_token(token):
    """Validate JWT token and extract user information"""
    try:
        # Get public keys from Cognito
        jwks = get_cognito_public_keys()
        if not jwks:
            raise Exception("Could not fetch Cognito public keys")

        # Decode token header to get kid (key ID)
        unverified_header = jose_jwt.get_unverified_header(token)
        kid = unverified_header['kid']

        # Find the correct public key
        key = None
        for jwk_key in jwks['keys']:
            if jwk_key['kid'] == kid:
                key = jwk.construct(jwk_key)
                break

        if not key:
            raise Exception("Public key not found")

        # Verify and decode the token
        decoded_token = jose_jwt.decode(
            token,
            key,
            algorithms=['RS256'],
            audience=COGNITO_CLIENT_ID,
            issuer=f'https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}'
        )

        # Extract user ID (username) from token
        user_id = decoded_token.get('username') or decoded_token.get('cognito:username')
        if not user_id:
            raise Exception("User ID not found in token")

        # Get Cognito Identity ID for S3 path consistency
        identity_id = get_cognito_identity_id_from_token(token)

        return identity_id

    except jose_jwt.ExpiredSignatureError:
        raise Exception("Token has expired")
    except jose_jwt.JWTClaimsError:
        raise Exception("Token claims are invalid")
    except jose_jwt.JWTError as e:
        raise Exception(f"Token validation failed: {str(e)}")
    except Exception as e:
        raise Exception(f"Authentication error: {str(e)}")


def require_auth(f):
    """Decorator to require JWT authentication for endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Extract Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': 'Missing Authorization header'}), 401

        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Invalid Authorization header format'}), 401

        # Extract token
        token = auth_header.split(' ')[1]

        try:
            # Validate token and get authenticated user ID
            authenticated_user_id = validate_jwt_token(token)

            # Pass authenticated user ID to the endpoint function
            return f(authenticated_user_id, *args, **kwargs)

        except Exception as e:
            print(f"❌ Authentication failed: {str(e)}")
            return jsonify({'error': str(e)}), 401

    return decorated_function
