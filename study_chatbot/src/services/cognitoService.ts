import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserSession,
  CognitoUserAttribute,
  CognitoRefreshToken, // Import CognitoRefreshToken
} from 'amazon-cognito-identity-js';
import * as SecureStore from 'expo-secure-store';
import {
  COGNITO_USER_POOL_ID,
  COGNITO_CLIENT_ID,
  AWS_REGION,
} from '@env';

// Configure Cognito User Pool
const poolData = {
  UserPoolId: COGNITO_USER_POOL_ID,
  ClientId: COGNITO_CLIENT_ID,
};

const userPool = new CognitoUserPool(poolData);

// Token storage keys
const TOKEN_KEY = 'cognito_id_token';
const REFRESH_TOKEN_KEY = 'cognito_refresh_token';
const USER_EMAIL_KEY = 'user_email';
const USER_USERNAME_KEY = 'user_username';

export interface SignUpResponse {
  success: boolean;
  message: string;
  userSub?: string;
  confirmationRequired?: boolean;
}

export interface SignInResponse {
  success: boolean;
  message: string;
  idToken?: string;
  user?: {
    email: string;
    username: string;
  };
}

/**
 * Sign up a new user with Cognito
 */
export const signUp = async (
  email: string,
  username: string,
  password: string
): Promise<SignUpResponse> => {
  return new Promise((resolve, reject) => {
    const attributeList = [
      new CognitoUserAttribute({
        Name: 'email',
        Value: email,
      }),
    ];

    userPool.signUp(username, password, attributeList, [], (err, result) => {
      if (err) {
        console.error('Signup error:', err);
        resolve({
          success: false,
          message: err.message || 'Failed to sign up',
        });
        return;
      }

      if (result) {
        resolve({
          success: true,
          message: 'User signed up successfully. Please check your email for verification.',
          userSub: result.userSub,
          confirmationRequired: !result.userConfirmed,
        });
      }
    });
  });
};

/**
 * Sign in a user with Cognito
 */
export const signIn = async (
  username: string,
  password: string
): Promise<SignInResponse> => {
  return new Promise((resolve, reject) => {
    const authenticationDetails = new AuthenticationDetails({
      Username: username,
      Password: password,
    });

    const cognitoUser = new CognitoUser({
      Username: username,
      Pool: userPool,
    });

    cognitoUser.authenticateUser(authenticationDetails, {
      onSuccess: async (session: CognitoUserSession) => {
        const idToken = session.getIdToken().getJwtToken();
        const refreshToken = session.getRefreshToken().getToken();

        // Store tokens securely
        try {
          await SecureStore.setItemAsync(TOKEN_KEY, idToken);
          await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, refreshToken);
          await SecureStore.setItemAsync(USER_USERNAME_KEY, username); // Store username

          // Get user email
          cognitoUser.getUserAttributes((err, attributes) => {
            if (err) {
              console.error('Error getting user attributes:', err);
              resolve({
                success: true,
                message: 'Signed in successfully',
                idToken,
                user: {
                  email: '',
                  username,
                },
              });
              return;
            }

            const emailAttr = attributes?.find(attr => attr.Name === 'email');
            const email = emailAttr?.Value || '';

            // Store user email
            SecureStore.setItemAsync(USER_EMAIL_KEY, email);

            resolve({
              success: true,
              message: 'Signed in successfully',
              idToken,
              user: {
                email,
                username,
              },
            });
          });
        } catch (error) {
          console.error('Error storing tokens:', error);
          resolve({
            success: false,
            message: 'Failed to store authentication tokens',
          });
        }
      },
      onFailure: (err) => {
        console.error('Authentication error:', err);
        resolve({
          success: false,
          message: err.message || 'Authentication failed',
        });
      },
    });
  });
};

/**
 * Sign out the current user
 */
export const signOut = async (): Promise<void> => {
  const cognitoUser = userPool.getCurrentUser();

  if (cognitoUser) {
    cognitoUser.signOut();
  }

  // Clear stored tokens
  try {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
    await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
    await SecureStore.deleteItemAsync(USER_EMAIL_KEY);
    await SecureStore.deleteItemAsync(USER_USERNAME_KEY); // Clear username
  } catch (error) {
    console.error('Error clearing tokens:', error);
  }
};

/**
 * Get the current user's ID token
 */
export const getIdToken = async (): Promise<string | null> => {
  try {
    const token = await SecureStore.getItemAsync(TOKEN_KEY);
    return token;
  } catch (error) {
    console.error('Error retrieving token:', error);
    return null;
  }
};

/**
 * Get the current user's email
 */
export const getUserEmail = async (): Promise<string | null> => {
  try {
    const email = await SecureStore.getItemAsync(USER_EMAIL_KEY);
    return email;
  } catch (error) {
    console.error('Error retrieving user email:', error);
    return null;
  }
};

/**
 * Check if user is authenticated
 */
export const isAuthenticated = async (): Promise<boolean> => {
  const token = await getIdToken();
  return token !== null;
};

/**
 * Refresh the current session
 */
export const refreshSession = async (): Promise<string | null> => {
  return new Promise(async (resolve) => {
    const storedUsername = await SecureStore.getItemAsync(USER_USERNAME_KEY);
    const storedRefreshToken = await SecureStore.getItemAsync(REFRESH_TOKEN_KEY);

    if (!storedUsername || !storedRefreshToken) {
      console.log('No username or refresh token found, cannot refresh session');
      resolve(null);
      return;
    }

    const cognitoUser = new CognitoUser({
      Username: storedUsername,
      Pool: userPool,
    });

    const refreshToken = new CognitoRefreshToken({ RefreshToken: storedRefreshToken });

    cognitoUser.refreshSession(refreshToken, async (err, session: CognitoUserSession) => {
      if (err) {
        console.error('Session refresh error:', err);
        // If refresh fails, clear all tokens to force re-login
        try {
          await SecureStore.deleteItemAsync(TOKEN_KEY);
          await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
          await SecureStore.deleteItemAsync(USER_USERNAME_KEY);
          await SecureStore.deleteItemAsync(USER_EMAIL_KEY);
        } catch (e) {
          console.error('Error clearing invalid tokens:', e);
        }
        resolve(null);
        return;
      }

      if (session && session.isValid()) {
        const idToken = session.getIdToken().getJwtToken();
        const newRefreshToken = session.getRefreshToken().getToken();

        try {
          await SecureStore.setItemAsync(TOKEN_KEY, idToken);
          // Cognito may or may not return a new refresh token. If it does, store it.
          if (newRefreshToken) {
            await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, newRefreshToken);
          }
          console.log('✅ Session refreshed successfully');
          resolve(idToken);
        } catch (error) {
          console.error('Error storing refreshed token:', error);
          resolve(null);
        }
      } else {
        console.log('Session is invalid after refresh');
        resolve(null);
      }
    });
  });
};

/**
 * Delete user account
 */
export const deleteAccount = async (): Promise<SignUpResponse> => {
  return new Promise((resolve, reject) => {
    const cognitoUser = userPool.getCurrentUser();

    if (!cognitoUser) {
      resolve({
        success: false,
        message: 'No user is currently signed in',
      });
      return;
    }

    cognitoUser.getSession((err: any, session: CognitoUserSession) => {
      if (err) {
        console.error('Session error:', err);
        resolve({
          success: false,
          message: 'Failed to verify session',
        });
        return;
      }

      cognitoUser.deleteUser((err) => {
        if (err) {
          console.error('Delete account error:', err);
          resolve({
            success: false,
            message: err.message || 'Failed to delete account',
          });
          return;
        }

        // Clear stored tokens
        signOut();

        resolve({
          success: true,
          message: 'Account deleted successfully',
        });
      });
    });
  });
};
