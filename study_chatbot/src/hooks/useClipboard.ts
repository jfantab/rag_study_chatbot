import { useState } from 'react';
import * as Clipboard from 'expo-clipboard';
import { Alert, Platform } from 'react-native';

interface UseClipboardReturn {
  copyToClipboard: (text: string, showFeedback?: boolean) => Promise<boolean>;
  pasteFromClipboard: () => Promise<string>;
  hasClipboardContent: () => Promise<boolean>;
  isCopying: boolean;
}

/**
 * Custom hook for clipboard operations with feedback
 * @returns Clipboard utilities
 */
export const useClipboard = (): UseClipboardReturn => {
  const [isCopying, setIsCopying] = useState(false);

  /**
   * Copy text to clipboard with optional feedback
   * @param text - Text to copy
   * @param showFeedback - Whether to show success/error feedback (default: true)
   * @returns Promise<boolean> - Success status
   */
  const copyToClipboard = async (
    text: string,
    showFeedback: boolean = true
  ): Promise<boolean> => {
    if (!text || text.trim().length === 0) {
      if (showFeedback) {
        Alert.alert('Error', 'No text to copy');
      }
      return false;
    }

    setIsCopying(true);
    try {
      await Clipboard.setStringAsync(text);

      if (showFeedback) {
        if (Platform.OS === 'web') {
          // For web, use alert or console
          console.log('Copied to clipboard!');
        } else {
          Alert.alert('Success', 'Copied to clipboard!', [{ text: 'OK' }]);
        }
      }

      setIsCopying(false);
      return true;
    } catch (error) {
      console.error('Failed to copy to clipboard:', error);

      if (showFeedback) {
        Alert.alert('Error', 'Failed to copy to clipboard');
      }

      setIsCopying(false);
      return false;
    }
  };

  /**
   * Paste text from clipboard
   * @returns Promise<string> - Clipboard content
   */
  const pasteFromClipboard = async (): Promise<string> => {
    try {
      const text = await Clipboard.getStringAsync();
      return text;
    } catch (error) {
      console.error('Failed to paste from clipboard:', error);
      return '';
    }
  };

  /**
   * Check if clipboard has content
   * @returns Promise<boolean> - Whether clipboard has content
   */
  const hasClipboardContent = async (): Promise<boolean> => {
    try {
      const hasContent = await Clipboard.hasStringAsync();
      return hasContent;
    } catch (error) {
      console.error('Failed to check clipboard content:', error);
      return false;
    }
  };

  return {
    copyToClipboard,
    pasteFromClipboard,
    hasClipboardContent,
    isCopying,
  };
};
