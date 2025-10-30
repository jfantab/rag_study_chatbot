import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import {
  signIn as cognitoSignIn,
  signUp as cognitoSignUp,
  signOut as cognitoSignOut,
  getIdToken,
  getUserEmail,
  isAuthenticated as checkAuthentication,
  refreshSession,
  deleteAccount as cognitoDeleteAccount,
  forgotPassword as cognitoForgotPassword,
  confirmForgotPassword as cognitoConfirmForgotPassword,
  confirmSignUp as cognitoConfirmSignUp,
  resendConfirmationCode as cognitoResendConfirmationCode,
  SignInResponse,
  SignUpResponse,
  ForgotPasswordResponse,
  ConfirmSignUpResponse,
} from '../services/cognitoService';

interface User {
  email: string;
  username: string;
}

interface AuthContextType {
  user: User | null;
  idToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  signIn: (username: string, password: string) => Promise<SignInResponse>;
  signUp: (email: string, username: string, password: string) => Promise<SignUpResponse>;
  signOut: () => Promise<void>;
  deleteAccount: () => Promise<SignUpResponse>;
  refreshAuth: () => Promise<void>;
  forgotPassword: (username: string) => Promise<ForgotPasswordResponse>;
  confirmForgotPassword: (username: string, verificationCode: string, newPassword: string) => Promise<ForgotPasswordResponse>;
  confirmSignUp: (username: string, verificationCode: string) => Promise<ConfirmSignUpResponse>;
  resendConfirmationCode: (username: string) => Promise<ConfirmSignUpResponse>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [idToken, setIdToken] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Check authentication status on mount
  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const authenticated = await checkAuthentication();
      setIsAuthenticated(authenticated);

      if (authenticated) {
        const token = await getIdToken();
        const email = await getUserEmail();

        setIdToken(token);
        if (email) {
          setUser({
            email,
            username: email.split('@')[0], // Extract username from email
          });
        }
      }
    } catch (error) {
      console.error('Error checking auth status:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const signIn = async (username: string, password: string): Promise<SignInResponse> => {
    try {
      const response = await cognitoSignIn(username, password);

      if (response.success && response.idToken && response.user) {
        setIdToken(response.idToken);
        setUser(response.user);
        setIsAuthenticated(true);
      }

      return response;
    } catch (error: any) {
      console.error('Sign in error:', error);
      return {
        success: false,
        message: error.message || 'Sign in failed',
      };
    }
  };

  const signUp = async (
    email: string,
    username: string,
    password: string
  ): Promise<SignUpResponse> => {
    try {
      const response = await cognitoSignUp(email, username, password);
      return response;
    } catch (error: any) {
      console.error('Sign up error:', error);
      return {
        success: false,
        message: error.message || 'Sign up failed',
      };
    }
  };

  const signOut = async (): Promise<void> => {
    try {
      await cognitoSignOut();
      setUser(null);
      setIdToken(null);
      setIsAuthenticated(false);
    } catch (error) {
      console.error('Sign out error:', error);
      throw error;
    }
  };

  const deleteAccount = async (): Promise<SignUpResponse> => {
    try {
      const response = await cognitoDeleteAccount();

      if (response.success) {
        setUser(null);
        setIdToken(null);
        setIsAuthenticated(false);
      }

      return response;
    } catch (error: any) {
      console.error('Delete account error:', error);
      return {
        success: false,
        message: error.message || 'Failed to delete account',
      };
    }
  };

  const refreshAuth = async (): Promise<void> => {
    try {
      const token = await refreshSession();

      if (token) {
        setIdToken(token);
        const email = await getUserEmail();

        if (email) {
          setUser({
            email,
            username: email.split('@')[0],
          });
        }
        setIsAuthenticated(true);
      } else {
        // Session refresh failed, sign out
        await signOut();
      }
    } catch (error) {
      console.error('Refresh auth error:', error);
      await signOut();
    }
  };

  const forgotPassword = async (username: string): Promise<ForgotPasswordResponse> => {
    try {
      const response = await cognitoForgotPassword(username);
      return response;
    } catch (error: any) {
      console.error('Forgot password error:', error);
      return {
        success: false,
        message: error.message || 'Failed to initiate password reset',
      };
    }
  };

  const confirmForgotPassword = async (
    username: string,
    verificationCode: string,
    newPassword: string
  ): Promise<ForgotPasswordResponse> => {
    try {
      const response = await cognitoConfirmForgotPassword(username, verificationCode, newPassword);
      return response;
    } catch (error: any) {
      console.error('Confirm forgot password error:', error);
      return {
        success: false,
        message: error.message || 'Failed to reset password',
      };
    }
  };

  const confirmSignUp = async (
    username: string,
    verificationCode: string
  ): Promise<ConfirmSignUpResponse> => {
    try {
      const response = await cognitoConfirmSignUp(username, verificationCode);
      return response;
    } catch (error: any) {
      console.error('Confirm signup error:', error);
      return {
        success: false,
        message: error.message || 'Failed to verify email',
      };
    }
  };

  const resendConfirmationCode = async (username: string): Promise<ConfirmSignUpResponse> => {
    try {
      const response = await cognitoResendConfirmationCode(username);
      return response;
    } catch (error: any) {
      console.error('Resend confirmation code error:', error);
      return {
        success: false,
        message: error.message || 'Failed to resend verification code',
      };
    }
  };

  const value: AuthContextType = {
    user,
    idToken,
    isAuthenticated,
    isLoading,
    signIn,
    signUp,
    signOut,
    deleteAccount,
    refreshAuth,
    forgotPassword,
    confirmForgotPassword,
    confirmSignUp,
    resendConfirmationCode,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
