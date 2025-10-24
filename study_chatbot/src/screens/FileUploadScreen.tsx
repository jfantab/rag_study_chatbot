import React, { useState } from 'react';
import {
    View,
    Text,
    StyleSheet,
    ScrollView,
    TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';

const FileUploadScreen: React.FC = () => {
    const navigation = useNavigation();
    const [uploadedFiles] = useState<any[]>([]);

    const handleFileSelect = () => {
        // UI only - no functionality yet
        console.log('File select tapped');
    };

    const formatFileSize = (bytes: number): string => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
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
                        Upload documents to enhance your chatbot's knowledge base
                    </Text>

                    <TouchableOpacity
                        style={styles.uploadArea}
                        onPress={handleFileSelect}
                        activeOpacity={0.7}
                    >
                        <Ionicons name="cloud-upload" size={48} color="#007AFF" />
                        <Text style={styles.uploadTitle}>Tap to select files</Text>
                        <Text style={styles.uploadSubtitle}>
                            Supports PDF, TXT, DOC, DOCX files
                        </Text>
                    </TouchableOpacity>

                    {/* Selected Files (Empty State) */}
                    {uploadedFiles.length === 0 && (
                        <View style={styles.emptyState}>
                            <Ionicons name="document-outline" size={64} color="#E5E7EB" />
                            <Text style={styles.emptyStateTitle}>No files selected</Text>
                            <Text style={styles.emptyStateSubtitle}>
                                Select files to upload to your knowledge base
                            </Text>
                        </View>
                    )}

                    {/* Storage Files Section */}
                    <View style={styles.storageSection}>
                        <View style={styles.storageSectionHeader}>
                            <View>
                                <Text style={styles.storageTitle}>Files in Storage</Text>
                                <Text style={styles.fileCount}>0 files available</Text>
                            </View>
                            <TouchableOpacity style={styles.refreshButton}>
                                <Ionicons name="refresh" size={20} color="#007AFF" />
                            </TouchableOpacity>
                        </View>

                        <View style={styles.storageFilesList}>
                            <View style={styles.noFilesContainer}>
                                <Ionicons name="folder-open-outline" size={48} color="#E5E7EB" />
                                <Text style={styles.noFilesText}>No files in storage</Text>
                                <Text style={styles.noFilesSubtext}>
                                    Upload files to get started
                                </Text>
                            </View>
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
});

export default FileUploadScreen;
