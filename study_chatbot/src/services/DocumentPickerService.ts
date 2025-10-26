import * as DocumentPicker from 'expo-document-picker';
import { Platform } from 'react-native';

export interface FileAttachment {
  uri: string;
  name: string;
  size: number;
  type: string;
  s3_key?: string; // S3 key after upload
  file_id?: string; // File ID from backend
}

export class DocumentPickerService {
  private static instance: DocumentPickerService;
  private isPickingDocument: boolean = false;

  private constructor() {}

  public static getInstance(): DocumentPickerService {
    if (!DocumentPickerService.instance) {
      DocumentPickerService.instance = new DocumentPickerService();
    }
    return DocumentPickerService.instance;
  }

  /**
   * Pick a document with platform-specific optimizations
   */
  public async pickDocument(): Promise<FileAttachment | null> {
    if (this.isPickingDocument) {
      return null;
    }

    this.isPickingDocument = true;

    try {
      // Small delay to avoid race conditions
      await new Promise(resolve => setTimeout(resolve, 100));

      // Platform-specific options
      const options: DocumentPicker.DocumentPickerOptions = {
        type: '*/*', // More permissive for all platforms
        copyToCacheDirectory: Platform.OS !== 'web', // Web doesn't support this
        multiple: false
      };

      const result = await DocumentPicker.getDocumentAsync(options);

      if (result.canceled) {
        return null;
      }

      // Handle both new and old API formats
      let fileAsset: any;
      if ('assets' in result && result.assets && result.assets.length > 0) {
        fileAsset = result.assets[0];
      } else if ('uri' in result && (result as any).uri) {
        fileAsset = result;
      } else {
        throw new Error('Invalid document picker result format');
      }

      if (!fileAsset.uri) {
        throw new Error('No file URI found in result');
      }

      const fileData: FileAttachment = {
        uri: fileAsset.uri,
        name: fileAsset.name || this.getFileNameFromUri(fileAsset.uri),
        size: fileAsset.size || 0,
        type: fileAsset.mimeType || this.getMimeTypeFromExtension(fileAsset.name || ''),
      };

      return fileData;

    } catch (error) {
      console.error('Document picker error:', error);
      throw error;
    } finally {
      this.isPickingDocument = false;
    }
  }

  /**
   * Test document picker functionality
   */
  public async testDocumentPicker(): Promise<boolean> {
    try {
      if (!DocumentPicker || !DocumentPicker.getDocumentAsync) {
        return false;
      }

      return true;
    } catch (error) {
      console.error('DocumentPicker test failed:', error);
      return false;
    }
  }

  /**
   * Get diagnostic information
   */
  public getDiagnosticInfo(): object {
    return {
      platform: Platform.OS,
      documentPickerAvailable: !!DocumentPicker,
      isActive: this.isPickingDocument
    };
  }

  private getFileNameFromUri(uri: string): string {
    const parts = uri.split('/');
    return parts[parts.length - 1] || 'unknown-file';
  }

  private getMimeTypeFromExtension(filename: string): string {
    const extension = filename.toLowerCase().split('.').pop() || '';

    const mimeTypes: { [key: string]: string } = {
      'pdf': 'application/pdf',
      'txt': 'text/plain',
      'doc': 'application/msword',
      'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'jpg': 'image/jpeg',
      'jpeg': 'image/jpeg',
      'png': 'image/png',
      'gif': 'image/gif',
      'mp4': 'video/mp4',
      'json': 'application/json',
      'zip': 'application/zip'
    };

    return mimeTypes[extension] || 'application/octet-stream';
  }

  /**
   * Force reset service state
   */
  public forceReset(): void {
    this.isPickingDocument = false;
  }
}

export default DocumentPickerService;
