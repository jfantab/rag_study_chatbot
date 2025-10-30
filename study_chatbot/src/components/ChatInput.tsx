import React, { useState } from 'react';
import {
    View,
    TextInput,
    TouchableOpacity,
    StyleSheet,
    Platform,
    Text,
    Modal,
    Image,
    ScrollView,
    Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import DocumentPickerService, { FileAttachment } from '../services/DocumentPickerService';

interface ChatInputProps {
    value: string;
    onChangeText: (text: string) => void;
    onSend: (message: string, images?: string[], files?: FileAttachment[]) => void;
    isLoading: boolean;
}

const ChatInput: React.FC<ChatInputProps> = ({
    value,
    onChangeText,
    onSend,
    isLoading,
}) => {
    const [showAttachmentMenu, setShowAttachmentMenu] = useState(false);
    const [inputHeight, setInputHeight] = useState(48);
    const [selectedImages, setSelectedImages] = useState<string[]>([]);
    const [selectedFiles, setSelectedFiles] = useState<FileAttachment[]>([]);
    const [isPickingFile, setIsPickingFile] = useState(false);

    const handleSend = () => {
        if ((value.trim() || selectedImages.length > 0 || selectedFiles.length > 0) && !isLoading) {
            onSend(
                value.trim(),
                selectedImages.length > 0 ? selectedImages : undefined,
                selectedFiles.length > 0 ? selectedFiles : undefined
            );
            setSelectedImages([]);
            setSelectedFiles([]);
        }
    };

    const handleContentSizeChange = (event: any) => {
        const newHeight = event.nativeEvent.contentSize.height;
        // Constrain between minHeight and maxHeight
        const constrainedHeight = Math.max(48, Math.min(120, newHeight + 24));
        setInputHeight(constrainedHeight);
    };

    const handleAttachment = () => {
        setShowAttachmentMenu(true);
    };

    const handleTakePhoto = async () => {
        setShowAttachmentMenu(false);

        try {
            const { status } = await ImagePicker.requestCameraPermissionsAsync();
            if (status !== 'granted') {
                Alert.alert(
                    'Camera Permission Required',
                    'Please grant camera permissions to take photos.',
                    [{ text: 'OK' }]
                );
                return;
            }

            const result = await ImagePicker.launchCameraAsync({
                mediaTypes: 'images',
                allowsEditing: false,
                quality: 0.8,
                base64: false,
            });

            if (!result.canceled && result.assets && result.assets[0]) {
                const imageUri = result.assets[0].uri;
                setSelectedImages(prev => [...prev, imageUri]);
            }
        } catch (error: any) {
            console.error('Error capturing image:', error);
            Alert.alert('Error', `Failed to capture image: ${error.message || 'Unknown error'}`);
        }
    };

    const handleImageFromLibrary = async () => {
        setShowAttachmentMenu(false);

        try {
            const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
            if (status !== 'granted') {
                Alert.alert(
                    'Photo Library Permission Required',
                    'Please grant photo library permissions to select images.',
                    [{ text: 'OK' }]
                );
                return;
            }

            const result = await ImagePicker.launchImageLibraryAsync({
                mediaTypes: 'images',
                allowsEditing: false,
                quality: 0.8,
                base64: false,
            });

            if (!result.canceled && result.assets && result.assets[0]) {
                const imageUri = result.assets[0].uri;
                setSelectedImages(prev => [...prev, imageUri]);
            }
        } catch (error: any) {
            console.error('Error picking image:', error);
            Alert.alert('Error', `Failed to select image: ${error.message || 'Unknown error'}`);
        }
    };

    const handleDocumentPicker = async () => {
        if (isPickingFile) {
            return;
        }

        setShowAttachmentMenu(false);
        setIsPickingFile(true);

        try {
            const documentPickerService = DocumentPickerService.getInstance();

            // Test functionality first
            const testResult = await documentPickerService.testDocumentPicker();
            if (!testResult) {
                Alert.alert(
                    'Document Picker Unavailable',
                    'Document picker is not available on this device.',
                    [{ text: 'OK' }]
                );
                return;
            }

            const file = await documentPickerService.pickDocument();

            if (file) {
                setSelectedFiles(prev => [...prev, file]);
            } else {
                // File selection was canceled or the picker was busy
            }
        } catch (error: any) {
            console.error('❌ Document picker error:', error);

            // Handle specific concurrent picker error
            if (error.message && error.message.includes('Different document picking in progress')) {
                Alert.alert(
                    'File Picker Busy',
                    'File picker is currently in use. Please wait a moment and try again.',
                    [
                        { text: 'OK' },
                        {
                            text: 'Retry',
                            onPress: () => {
                                setTimeout(() => {
                                    DocumentPickerService.getInstance().forceReset();
                                    handleDocumentPicker();
                                }, 1000);
                            }
                        }
                    ]
                );
                return;
            }

            Alert.alert(
                'File Selection Error',
                `Failed to select file: ${error.message || 'Unknown error'}`,
                [{ text: 'OK' }]
            );
        } finally {
            setIsPickingFile(false);
        }
    };

    const removeImage = (index: number) => {
        setSelectedImages(prev => prev.filter((_, i) => i !== index));
    };

    const removeFile = (index: number) => {
        setSelectedFiles(prev => prev.filter((_, i) => i !== index));
    };

    const formatFileSize = (bytes: number): string => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    };

    return (
        <View style={styles.container}>
            {/* Attachments Preview */}
            {(selectedImages.length > 0 || selectedFiles.length > 0) && (
                <View style={styles.attachmentsWrapper}>
                    {/* Image Preview */}
                    {selectedImages.length > 0 && (
                        <ScrollView
                            horizontal
                            showsHorizontalScrollIndicator={false}
                            style={styles.imagePreviewContainer}
                            contentContainerStyle={styles.imagePreviewContent}
                        >
                            {selectedImages.map((imageUri, index) => (
                                <View key={imageUri} style={styles.imagePreviewWrapper}>
                                    <Image source={{ uri: imageUri }} style={styles.imagePreview} />
                                    <TouchableOpacity
                                        style={styles.removeImageButton}
                                        onPress={() => removeImage(index)}
                                    >
                                        <Ionicons name="close-circle" size={20} color="#FF3B30" />
                                    </TouchableOpacity>
                                </View>
                            ))}
                        </ScrollView>
                    )}

                    {/* File Preview */}
                    {selectedFiles.length > 0 && (
                        <ScrollView
                            horizontal
                            showsHorizontalScrollIndicator={false}
                            style={styles.filePreviewContainer}
                            contentContainerStyle={styles.filePreviewContent}
                        >
                            {selectedFiles.map((file, index) => (
                                <View key={file.uri} style={styles.filePreviewWrapper}>
                                    <View style={styles.filePreview}>
                                        <Ionicons name="document-text" size={20} color="#007AFF" />
                                        <View style={styles.fileInfo}>
                                            <Text style={styles.fileName} numberOfLines={1}>
                                                {file.name}
                                            </Text>
                                            <Text style={styles.fileSize}>
                                                {formatFileSize(file.size)}
                                            </Text>
                                        </View>
                                    </View>
                                    <TouchableOpacity
                                        style={styles.removeFileButton}
                                        onPress={() => removeFile(index)}
                                    >
                                        <Ionicons name="close-circle" size={20} color="#FF3B30" />
                                    </TouchableOpacity>
                                </View>
                            ))}
                        </ScrollView>
                    )}
                </View>
            )}

            <View style={styles.inputContainer}>
                <TouchableOpacity
                    style={styles.attachmentButton}
                    onPress={handleAttachment}
                    disabled={isLoading}
                >
                    <Ionicons
                        name="attach"
                        size={24}
                        color={isLoading ? '#CCC' : '#666'}
                    />
                </TouchableOpacity>

                <TextInput
                    style={[
                        styles.textInput,
                        { height: inputHeight },
                        isLoading ? styles.textInputDisabled : null,
                    ]}
                    value={value}
                    onChangeText={onChangeText}
                    placeholder="Type your message..."
                    placeholderTextColor="#999"
                    multiline
                    editable={!isLoading}
                    returnKeyType="send"
                    onContentSizeChange={handleContentSizeChange}
                />

                <TouchableOpacity
                    style={[
                        styles.sendButton,
                        ((!value.trim() && selectedImages.length === 0 && selectedFiles.length === 0) || isLoading) &&
                            styles.sendButtonDisabled,
                    ]}
                    onPress={handleSend}
                    disabled={(!value.trim() && selectedImages.length === 0 && selectedFiles.length === 0) || isLoading}
                >
                    <Text style={styles.sendButtonText}>→</Text>
                </TouchableOpacity>
            </View>

            {/* Attachment Menu Modal */}
            <Modal
                visible={showAttachmentMenu}
                transparent={true}
                animationType="fade"
                onRequestClose={() => setShowAttachmentMenu(false)}
            >
                <TouchableOpacity
                    style={styles.modalOverlay}
                    activeOpacity={1}
                    onPress={() => setShowAttachmentMenu(false)}
                >
                    <View style={styles.attachmentMenu}>
                        <Text style={styles.menuTitle}>Choose an option</Text>

                        <TouchableOpacity
                            style={styles.menuOption}
                            onPress={handleTakePhoto}
                        >
                            <View style={styles.menuOptionContent}>
                                <Ionicons
                                    name="camera-outline"
                                    size={24}
                                    color="#007AFF"
                                />
                                <View style={styles.menuOptionText}>
                                    <Text style={styles.menuOptionTitle}>
                                        Take Photo
                                    </Text>
                                    <Text style={styles.menuOptionSubtitle}>
                                        Use your camera
                                    </Text>
                                </View>
                            </View>
                            <Ionicons
                                name="chevron-forward"
                                size={20}
                                color="#C7C7CC"
                            />
                        </TouchableOpacity>

                        <TouchableOpacity
                            style={styles.menuOption}
                            onPress={handleImageFromLibrary}
                        >
                            <View style={styles.menuOptionContent}>
                                <Ionicons
                                    name="images-outline"
                                    size={24}
                                    color="#007AFF"
                                />
                                <View style={styles.menuOptionText}>
                                    <Text style={styles.menuOptionTitle}>
                                        Photo Library
                                    </Text>
                                    <Text style={styles.menuOptionSubtitle}>
                                        Choose from your photos
                                    </Text>
                                </View>
                            </View>
                            <Ionicons
                                name="chevron-forward"
                                size={20}
                                color="#C7C7CC"
                            />
                        </TouchableOpacity>

                        <TouchableOpacity
                            style={styles.menuOption}
                            onPress={handleDocumentPicker}
                        >
                            <View style={styles.menuOptionContent}>
                                <Ionicons
                                    name="document-outline"
                                    size={24}
                                    color="#007AFF"
                                />
                                <View style={styles.menuOptionText}>
                                    <Text style={styles.menuOptionTitle}>
                                        Document
                                    </Text>
                                    <Text style={styles.menuOptionSubtitle}>
                                        Choose a file
                                    </Text>
                                </View>
                            </View>
                            <Ionicons
                                name="chevron-forward"
                                size={20}
                                color="#C7C7CC"
                            />
                        </TouchableOpacity>

                        <TouchableOpacity
                            style={[styles.menuOption, styles.cancelOption]}
                            onPress={() => setShowAttachmentMenu(false)}
                        >
                            <View style={styles.menuOptionContent}>
                                <Ionicons
                                    name="close-circle-outline"
                                    size={24}
                                    color="#FF3B30"
                                />
                                <View style={styles.menuOptionText}>
                                    <Text
                                        style={[
                                            styles.menuOptionTitle,
                                            styles.cancelText,
                                        ]}
                                    >
                                        Cancel
                                    </Text>
                                </View>
                            </View>
                        </TouchableOpacity>
                    </View>
                </TouchableOpacity>
            </Modal>
        </View>
    );
};

const styles = StyleSheet.create({
    container: {
        backgroundColor: '#FFFFFF',
        borderTopWidth: 1,
        borderTopColor: '#E0E0E0',
        paddingHorizontal: 12,
        paddingTop: 8,
        paddingBottom: Platform.OS === 'ios' ? 34 : 12,
    },
    inputContainer: {
        flexDirection: 'row',
        alignItems: 'flex-end',
    },
    attachmentButton: {
        width: 40,
        height: 40,
        justifyContent: 'center',
        alignItems: 'center',
    },
    textInput: {
        flex: 1,
        fontSize: 16,
        paddingHorizontal: 16,
        paddingVertical: 12,
        backgroundColor: '#F5F5F5',
        borderRadius: 20,
        marginRight: 8,
        maxHeight: 120,
        minHeight: 48,
    },
    textInputDisabled: {
        backgroundColor: '#E5E5E5',
        color: '#999',
    },
    sendButton: {
        width: 40,
        height: 40,
        borderRadius: 20,
        backgroundColor: '#007AFF',
        justifyContent: 'center',
        alignItems: 'center',
    },
    sendButtonDisabled: {
        backgroundColor: '#CCC',
    },
    sendButtonText: {
        fontSize: 24,
        color: '#FFFFFF',
        fontWeight: '600',
    },
    modalOverlay: {
        flex: 1,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        justifyContent: 'flex-end',
        paddingBottom: Platform.OS === 'ios' ? 120 : 100,
        paddingHorizontal: 16,
    },
    attachmentMenu: {
        backgroundColor: '#FFFFFF',
        borderRadius: 16,
        paddingVertical: 12,
        paddingHorizontal: 8,
        marginLeft: 0,
        alignSelf: 'flex-start',
        minWidth: 240,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 8,
        elevation: 8,
    },
    menuTitle: {
        fontSize: 18,
        fontWeight: '600',
        color: '#333',
        marginBottom: 16,
        textAlign: 'center',
    },
    menuOption: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingVertical: 16,
        paddingHorizontal: 12,
        borderRadius: 12,
        backgroundColor: '#F8F9FA',
        marginBottom: 12,
    },
    menuOptionContent: {
        flexDirection: 'row',
        alignItems: 'center',
        flex: 1,
    },
    menuOptionText: {
        marginLeft: 16,
        flex: 1,
    },
    menuOptionTitle: {
        fontSize: 16,
        fontWeight: '600',
        color: '#333',
        marginBottom: 2,
    },
    menuOptionSubtitle: {
        fontSize: 14,
        color: '#666',
    },
    cancelOption: {
        backgroundColor: '#FFF5F5',
    },
    cancelText: {
        color: '#FF3B30',
    },
    // Attachments wrapper
    attachmentsWrapper: {
        marginBottom: 12,
    },
    // Image preview styles
    imagePreviewContainer: {
        maxHeight: 80,
        paddingVertical: 8,
        marginBottom: 8,
    },
    imagePreviewContent: {
        paddingHorizontal: 8,
    },
    imagePreviewWrapper: {
        position: 'relative',
        marginRight: 12,
    },
    imagePreview: {
        width: 56,
        height: 56,
        borderRadius: 8,
        backgroundColor: '#F0F0F0',
    },
    removeImageButton: {
        position: 'absolute',
        top: -6,
        right: -6,
        backgroundColor: '#FFFFFF',
        borderRadius: 10,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.2,
        shadowRadius: 2,
        elevation: 2,
    },
    // File preview styles
    filePreviewContainer: {
        maxHeight: 80,
        paddingVertical: 4,
    },
    filePreviewContent: {
        paddingHorizontal: 8,
    },
    filePreviewWrapper: {
        position: 'relative',
        marginRight: 12,
    },
    filePreview: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: '#F8F9FA',
        borderRadius: 8,
        paddingHorizontal: 12,
        paddingVertical: 8,
        minWidth: 140,
        maxWidth: 200,
    },
    fileInfo: {
        marginLeft: 8,
        flex: 1,
    },
    fileName: {
        fontSize: 12,
        fontWeight: '500',
        color: '#333',
        marginBottom: 2,
    },
    fileSize: {
        fontSize: 10,
        color: '#666',
    },
    removeFileButton: {
        position: 'absolute',
        top: -6,
        right: -6,
        backgroundColor: '#FFFFFF',
        borderRadius: 10,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.2,
        shadowRadius: 2,
        elevation: 2,
    },
});

export default ChatInput;
