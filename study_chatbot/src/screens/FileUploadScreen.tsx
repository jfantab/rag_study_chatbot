import React, { useState, useEffect } from 'react';
import {
    View,
    Text,
    StyleSheet,
    ScrollView,
    TouchableOpacity,
    ActivityIndicator,
    Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { useAuth } from '../contexts/AuthContext';
import * as DocumentPicker from 'expo-document-picker';
import { API_BASE_URL } from '../services/api';

interface FileInfo {
    s3_key: string;
    filename: string;
    file_size: number;
    size_on_s3: number;
    mime_type: string;
    last_modified: string;
    upload_date?: string;
    is_encrypted: boolean;
    storage_format: string;
}

const FileUploadScreen: React.FC = () => {
    const navigation = useNavigation();
    const { idToken } = useAuth();
    const [uploadedFiles] = useState<any[]>([]);
    const [storageFiles, setStorageFiles] = useState<FileInfo[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState<string>('');

    // Fetch files from S3 on component mount
    useEffect(() => {
        fetchStorageFiles();
    }, []);

    const fetchStorageFiles = async () => {
        if (!idToken) {
            return;
        }

        setIsLoading(true);
        try {
            const response = await fetch(`${API_BASE_URL}/list_s3_files_encrypted`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${idToken}`,
                    'Content-Type': 'application/json',
                },
            });

            if (!response.ok) {
                throw new Error(`Failed to fetch files: ${response.status}`);
            }

            const data = await response.json();
            setStorageFiles(data.files || []);
        } catch (error) {
            console.error('Error fetching storage files:', error);
            Alert.alert('Error', 'Failed to load files from storage');
        } finally {
            setIsLoading(false);
            setIsRefreshing(false);
        }
    };

    const handleRefresh = () => {
        setIsRefreshing(true);
        fetchStorageFiles();
    };

    const handleFileSelect = async () => {
        try {
            // Open document picker
            const result = await DocumentPicker.getDocumentAsync({
                type: [
                    'application/pdf',
                    'text/plain',
                    'application/msword',
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                ],
                copyToCacheDirectory: true,
            });

            if (result.canceled) {
                return;
            }

            const file = result.assets[0];

            // Upload the file
            await uploadFile(file);
        } catch (error) {
            console.error('Error selecting file:', error);
            Alert.alert('Error', 'Failed to select file');
        }
    };

    const uploadFile = async (file: any) => {
        if (!idToken) {
            Alert.alert('Error', 'You must be signed in to upload files');
            return;
        }

        setIsUploading(true);
        setUploadProgress(`Uploading ${file.name}...`);

        try {
            // Create form data
            const formData = new FormData();

            // Create file object for upload
            const fileToUpload: any = {
                uri: file.uri,
                type: file.mimeType || 'application/octet-stream',
                name: file.name,
            };

            formData.append('file', fileToUpload);

            const response = await fetch(`${API_BASE_URL}/upload_to_s3`, {
                method: 'POST',
                headers: {
                    Authorization: `Bearer ${idToken}`,
                    // Don't set Content-Type - let fetch set it with boundary
                },
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(
                    errorData.error || `Upload failed: ${response.status}`
                );
            }

            const data = await response.json();

            Alert.alert(
                'Success',
                `File "${file.name}" uploaded successfully!`,
                [{ text: 'OK' }]
            );

            // Refresh the file list
            await fetchStorageFiles();
        } catch (error: any) {
            console.error('Upload error:', error);
            Alert.alert(
                'Upload Failed',
                error.message || 'Failed to upload file'
            );
        } finally {
            setIsUploading(false);
            setUploadProgress('');
        }
    };

    const formatFileSize = (bytes: number): string => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    const formatDate = (dateString: string): string => {
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
            });
        } catch {
            return 'Unknown date';
        }
    };

    const getFileIcon = (mimeType: string): any => {
        if (mimeType?.includes('pdf')) {
            return 'document-text';
        } else if (
            mimeType?.includes('word') ||
            mimeType?.includes('document')
        ) {
            return 'document';
        } else if (mimeType?.includes('text')) {
            return 'document-outline';
        } else if (mimeType?.includes('image')) {
            return 'image';
        } else {
            return 'document-attach';
        }
    };

    return (
        <SafeAreaView style={styles.container}>
            <ScrollView showsVerticalScrollIndicator={false}>
                {/* Header */}
                <View style={styles.header}>
                    <TouchableOpacity
                        onPress={() => navigation.goBack()}
                        style={styles.backButton}
                    >
                        <Ionicons name="arrow-back" size={24} color="#007AFF" />
                    </TouchableOpacity>
                    <Text style={styles.title}>File Upload</Text>
                </View>

                {/* Upload Section */}
                <View style={styles.uploadContainer}>
                    <Text style={styles.sectionTitle}>Upload Documents</Text>
                    <Text style={styles.description}>
                        Upload documents to enhance your chatbot's knowledge
                        base
                    </Text>

                    <TouchableOpacity
                        style={[
                            styles.uploadArea,
                            isUploading && styles.uploadAreaDisabled,
                        ]}
                        onPress={handleFileSelect}
                        activeOpacity={0.7}
                        disabled={isUploading}
                    >
                        {isUploading ? (
                            <>
                                <ActivityIndicator
                                    size="large"
                                    color="#007AFF"
                                />
                                <Text style={styles.uploadTitle}>
                                    {uploadProgress}
                                </Text>
                                <Text style={styles.uploadSubtitle}>
                                    Please wait...
                                </Text>
                            </>
                        ) : (
                            <>
                                <Ionicons
                                    name="cloud-upload"
                                    size={48}
                                    color="#007AFF"
                                />
                                <Text style={styles.uploadTitle}>
                                    Tap to select files
                                </Text>
                                <Text style={styles.uploadSubtitle}>
                                    Supports PDF, TXT, DOC, DOCX files
                                </Text>
                            </>
                        )}
                    </TouchableOpacity>

                    {/* Storage Files Section */}
                    <View style={styles.storageSection}>
                        <View style={styles.storageSectionHeader}>
                            <View>
                                <Text style={styles.storageTitle}>
                                    Files in Storage
                                </Text>
                                <Text style={styles.fileCount}>
                                    {storageFiles.length} file
                                    {storageFiles.length !== 1 ? 's' : ''}{' '}
                                    available
                                </Text>
                            </View>
                            <TouchableOpacity
                                style={styles.refreshButton}
                                onPress={handleRefresh}
                                disabled={isRefreshing}
                            >
                                <Ionicons
                                    name="refresh"
                                    size={20}
                                    color={isRefreshing ? '#9CA3AF' : '#007AFF'}
                                />
                            </TouchableOpacity>
                        </View>

                        <View style={styles.storageFilesList}>
                            {isLoading ? (
                                <View style={styles.loadingContainer}>
                                    <ActivityIndicator
                                        size="large"
                                        color="#007AFF"
                                    />
                                    <Text style={styles.loadingText}>
                                        Loading files...
                                    </Text>
                                </View>
                            ) : storageFiles.length === 0 ? (
                                <View style={styles.noFilesContainer}>
                                    <Ionicons
                                        name="folder-open-outline"
                                        size={48}
                                        color="#E5E7EB"
                                    />
                                    <Text style={styles.noFilesText}>
                                        No files in storage
                                    </Text>
                                    <Text style={styles.noFilesSubtext}>
                                        Upload files to get started
                                    </Text>
                                </View>
                            ) : (
                                storageFiles.map((file, index) => (
                                    <View
                                        key={file.s3_key}
                                        style={[
                                            styles.fileItem,
                                            index !== storageFiles.length - 1 &&
                                                styles.fileItemBorder,
                                        ]}
                                    >
                                        <View style={styles.fileIconContainer}>
                                            <Ionicons
                                                name={getFileIcon(
                                                    file.mime_type
                                                )}
                                                size={32}
                                                color="#007AFF"
                                            />
                                        </View>
                                        <View style={styles.fileInfo}>
                                            <Text
                                                style={styles.fileName}
                                                numberOfLines={1}
                                            >
                                                {file.filename}
                                            </Text>
                                            <View style={styles.fileMetaRow}>
                                                <Text style={styles.fileSize}>
                                                    {formatFileSize(
                                                        file.file_size
                                                    )}
                                                </Text>
                                                <Text style={styles.fileDot}>
                                                    •
                                                </Text>
                                                <Text style={styles.fileDate}>
                                                    {formatDate(
                                                        file.upload_date ||
                                                            file.last_modified
                                                    )}
                                                </Text>
                                                {file.is_encrypted && (
                                                    <>
                                                        <Text
                                                            style={
                                                                styles.fileDot
                                                            }
                                                        >
                                                            •
                                                        </Text>
                                                        <Ionicons
                                                            name="lock-closed"
                                                            size={12}
                                                            color="#10B981"
                                                        />
                                                    </>
                                                )}
                                            </View>
                                        </View>
                                    </View>
                                ))
                            )}
                        </View>
                    </View>
                </View>
            </ScrollView>
        </SafeAreaView>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#F8F9FA',
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        padding: 20,
        paddingTop: 10,
    },
    backButton: {
        marginRight: 16,
        padding: 8,
    },
    title: {
        fontSize: 24,
        fontWeight: 'bold',
        color: '#1D1D1F',
    },
    uploadContainer: {
        padding: 20,
    },
    sectionTitle: {
        fontSize: 20,
        fontWeight: '600',
        color: '#1D1D1F',
        marginBottom: 8,
    },
    description: {
        fontSize: 16,
        color: '#6B7280',
        marginBottom: 24,
    },
    uploadArea: {
        borderWidth: 2,
        borderColor: '#E5E7EB',
        borderStyle: 'dashed',
        borderRadius: 12,
        padding: 40,
        alignItems: 'center',
        backgroundColor: 'white',
        marginBottom: 32,
    },
    uploadAreaDisabled: {
        opacity: 0.6,
        backgroundColor: '#F9FAFB',
    },
    uploadTitle: {
        fontSize: 18,
        fontWeight: '500',
        color: '#1D1D1F',
        marginTop: 16,
        marginBottom: 8,
    },
    uploadSubtitle: {
        fontSize: 14,
        color: '#6B7280',
    },
    emptyState: {
        alignItems: 'center',
        paddingVertical: 40,
        paddingHorizontal: 20,
    },
    emptyStateTitle: {
        fontSize: 18,
        fontWeight: '600',
        color: '#6B7280',
        marginTop: 16,
        marginBottom: 8,
    },
    emptyStateSubtitle: {
        fontSize: 14,
        color: '#9CA3AF',
        textAlign: 'center',
    },
    storageSection: {
        borderTopWidth: 1,
        borderTopColor: '#E5E7EB',
        paddingTop: 24,
        marginTop: 16,
    },
    storageSectionHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 16,
    },
    storageTitle: {
        fontSize: 18,
        fontWeight: '600',
        color: '#1D1D1F',
    },
    fileCount: {
        fontSize: 14,
        color: '#6B7280',
        marginTop: 2,
    },
    refreshButton: {
        padding: 8,
    },
    storageFilesList: {
        backgroundColor: 'white',
        borderRadius: 12,
        overflow: 'hidden',
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.1,
        shadowRadius: 4,
        elevation: 3,
    },
    noFilesContainer: {
        padding: 40,
        alignItems: 'center',
    },
    noFilesText: {
        fontSize: 16,
        color: '#6B7280',
        fontWeight: '500',
        marginTop: 16,
        marginBottom: 4,
    },
    noFilesSubtext: {
        fontSize: 14,
        color: '#9CA3AF',
    },
    loadingContainer: {
        padding: 40,
        alignItems: 'center',
    },
    loadingText: {
        fontSize: 14,
        color: '#6B7280',
        marginTop: 12,
    },
    fileItem: {
        flexDirection: 'row',
        padding: 16,
        alignItems: 'center',
    },
    fileItemBorder: {
        borderBottomWidth: 1,
        borderBottomColor: '#F3F4F6',
    },
    fileIconContainer: {
        width: 48,
        height: 48,
        borderRadius: 8,
        backgroundColor: '#EFF6FF',
        alignItems: 'center',
        justifyContent: 'center',
        marginRight: 12,
    },
    fileInfo: {
        flex: 1,
    },
    fileName: {
        fontSize: 16,
        fontWeight: '500',
        color: '#1D1D1F',
        marginBottom: 4,
    },
    fileMetaRow: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    fileSize: {
        fontSize: 14,
        color: '#6B7280',
    },
    fileDate: {
        fontSize: 14,
        color: '#6B7280',
    },
    fileDot: {
        fontSize: 14,
        color: '#9CA3AF',
        marginHorizontal: 6,
    },
});

export default FileUploadScreen;
