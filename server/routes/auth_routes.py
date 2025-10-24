"""
Authentication routes for user signup and account management
"""
from flask import Blueprint, jsonify, request
from core.aws.cognito_service import signup_user, delete_user_account

auth_bp = Blueprint('auth', __name__)


@auth_bp.route("/signup", methods=["POST"])
def signup():
    """Sign up a new user using AWS Cognito"""
    try:
        data = request.get_json()
        if not data or 'email' not in data or 'username' not in data or 'password' not in data:
            return jsonify({"error": "email, username, and password are required"}), 400

        result = signup_user(data['email'], data['username'], data['password'])

        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), result.get('status_code', 400)
    except Exception as e:
        print(f"Error in signup endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@auth_bp.route("/delete_account", methods=["POST"])
def delete_account():
    """Delete a user account using AWS Cognito"""
    try:
        data = request.get_json()
        if not data or 'username' not in data:
            return jsonify({"error": "username is required"}), 400

        result = delete_user_account(data['username'])

        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), result.get('status_code', 400)
    except Exception as e:
        print(f"Error in delete_account endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
