import React, { useEffect, useRef, useState } from 'react';
import {
    FlatList,
    View,
    Text,
    StyleSheet,
    ActivityIndicator,
    TouchableOpacity,
    Animated,
    Image,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useClipboard } from '../hooks/useClipboard';
import ImagePreviewModal from './ImagePreviewModal';

interface Message {
    id: number;
    content: string;
    isUser: boolean;
    timestamp: Date;
    backendTimestamp?: string; // ISO timestamp from backend (for delete/edit operations)
    images?: string[]; // Image URIs
}

interface MessageListProps {
    messages: Message[];
    isLoading: boolean;
    onDeleteMessage?: (messageId: number) => Promise<void>;
}

interface MessageItemProps {
    message: Message;
    onCopySuccess: () => void;
    onDelete?: (messageId: number) => Promise<void>;
    onImagePress: (images: string[], index: number) => void;
}

const MessageItem: React.FC<MessageItemProps> = ({ message, onCopySuccess, onDelete, onImagePress }) => {
    const { copyToClipboard } = useClipboard();
    const [showMenu, setShowMenu] = useState(false);

    const handleCopy = async () => {
        const success = await copyToClipboard(message.content, false);
        if (success) {
            onCopySuccess();
        }
    };

    const handleMenuToggle = () => {
        setShowMenu(!showMenu);
    };

    const handleEdit = () => {
        setShowMenu(false);
        // TODO: Implement edit functionality
        console.log('Edit message:', message.id);
    };

    const handleDelete = async () => {
        console.log('🔴 DELETE CLICKED for message:', message.id);
        setShowMenu(false);
        if (onDelete) {
            try {
                console.log('🔴 Calling onDelete...');
                await onDelete(message.id);
                console.log('✅ Delete completed successfully');
            } catch (error) {
                console.error('❌ Delete failed:', error);
            }
        } else {
            console.warn('⚠️ No onDelete handler provided to MessageItem');
        }
    };

    return (
        <View style={styles.messageWrapper}>
            <View
                style={[
                    styles.messageContainer,
                    message.isUser ? styles.userMessage : styles.botMessage,
                ]}
            >
                <View style={styles.messageHeader}>
                    <Text style={styles.messageSender}>
                        {message.isUser ? 'You' : 'Chatbot'}
                    </Text>
                    <Text style={styles.messageTimestamp}>
                        {message.timestamp.toLocaleTimeString([], {
                            hour: 'numeric',
                            minute: '2-digit',
                            hour12: true,
                        })}
                    </Text>
                </View>

                {/* Image attachment */}
                {message.images && message.images.length > 0 && (
                    <TouchableOpacity
                        activeOpacity={0.8}
                        onPress={() => onImagePress(message.images!, 0)}
                        style={styles.imageContainer}
                    >
                        <Image
                            source={{ uri: message.images[0] }}
                            style={styles.messageImage}
                            resizeMode="cover"
                        />
                    </TouchableOpacity>
                )}

                {message.content && (
                    <Text style={[
                        styles.messageText,
                        message.isUser ? styles.userMessageText : styles.botMessageText,
                    ]}>
                        {message.content}
                    </Text>
                )}

                {/* Action buttons */}
                <View style={styles.actionButtons}>
                    <TouchableOpacity
                        style={[
                            styles.actionButton,
                            message.isUser ? styles.userActionButton : styles.botActionButton,
                        ]}
                        onPress={handleCopy}
                        activeOpacity={0.6}
                    >
                        <Ionicons
                            name="copy-outline"
                            size={16}
                            color={message.isUser ? '#FFFFFF' : '#666'}
                        />
                    </TouchableOpacity>

                    {message.isUser && (
                        <TouchableOpacity
                            style={[styles.actionButton, styles.userActionButton]}
                            onPress={handleMenuToggle}
                            activeOpacity={0.6}
                        >
                            <Ionicons
                                name="ellipsis-vertical"
                                size={16}
                                color="#FFFFFF"
                            />
                        </TouchableOpacity>
                    )}
                </View>
            </View>

            {/* Dropdown Menu */}
            {showMenu && message.isUser && (
                <>
                    <TouchableOpacity
                        style={styles.menuOverlay}
                        activeOpacity={1}
                        onPress={() => setShowMenu(false)}
                    />
                    <View style={styles.dropdownMenu}>
                        {/* Only show Edit if message has no image attachments */}
                        {(!message.images || message.images.length === 0) && (
                            <TouchableOpacity
                                style={styles.menuItem}
                                onPress={handleEdit}
                            >
                                <Ionicons
                                    name="create-outline"
                                    size={16}
                                    color="#333"
                                />
                                <Text style={styles.menuItemText}>Edit</Text>
                            </TouchableOpacity>
                        )}

                        <TouchableOpacity
                            style={[styles.menuItem, styles.menuItemDestructive]}
                            onPress={handleDelete}
                        >
                            <Ionicons
                                name="trash-outline"
                                size={16}
                                color="#FF3B30"
                            />
                            <Text style={[styles.menuItemText, styles.menuItemTextDestructive]}>
                                Delete
                            </Text>
                        </TouchableOpacity>
                    </View>
                </>
            )}
        </View>
    );
};

const LoadingIndicator: React.FC = () => (
    <View style={styles.loadingContainer}>
        <ActivityIndicator size="small" color="#007AFF" />
        <Text style={styles.loadingText}>Thinking...</Text>
    </View>
);

const EmptyState: React.FC = () => (
    <View style={styles.emptyState}>
        <Text style={styles.emptyStateTitle}>How can I help you today?</Text>
        <Text style={styles.emptyStateSubtitle}>
            Start a conversation by typing a message below.
        </Text>
    </View>
);

const MessageList: React.FC<MessageListProps> = ({ messages, isLoading, onDeleteMessage }) => {
    const flatListRef = useRef<FlatList>(null);
    const [showCopyToast, setShowCopyToast] = useState(false);
    const fadeAnim = useRef(new Animated.Value(0)).current;
    const [previewImages, setPreviewImages] = useState<string[]>([]);
    const [previewIndex, setPreviewIndex] = useState(0);
    const [showImagePreview, setShowImagePreview] = useState(false);

    useEffect(() => {
        if (messages.length > 0 || isLoading) {
            setTimeout(() => {
                flatListRef.current?.scrollToEnd({ animated: true });
            }, 100);
        }
    }, [messages.length, isLoading]);

    const handleCopySuccess = () => {
        setShowCopyToast(true);

        // Fade in
        Animated.sequence([
            Animated.timing(fadeAnim, {
                toValue: 1,
                duration: 200,
                useNativeDriver: true,
            }),
            Animated.delay(1500),
            // Fade out
            Animated.timing(fadeAnim, {
                toValue: 0,
                duration: 200,
                useNativeDriver: true,
            }),
        ]).start(() => {
            setShowCopyToast(false);
        });
    };

    const handleImagePress = (images: string[], index: number) => {
        setPreviewImages(images);
        setPreviewIndex(index);
        setShowImagePreview(true);
    };

    const handleCloseImagePreview = () => {
        setShowImagePreview(false);
    };

    const renderMessage = ({ item }: { item: Message }) => (
        <MessageItem
            message={item}
            onCopySuccess={handleCopySuccess}
            onDelete={onDeleteMessage}
            onImagePress={handleImagePress}
        />
    );

    const renderFooter = () => {
        if (!isLoading) return null;
        return <LoadingIndicator />;
    };

    return (
        <View style={styles.container}>
            {messages.length === 0 && !isLoading ? (
                <EmptyState />
            ) : (
                <FlatList
                    ref={flatListRef}
                    data={messages}
                    renderItem={renderMessage}
                    keyExtractor={(item) => item.id.toString()}
                    ListFooterComponent={renderFooter}
                    style={styles.messagesList}
                    contentContainerStyle={styles.messagesContent}
                    showsVerticalScrollIndicator={true}
                    scrollEventThrottle={16}
                    removeClippedSubviews={false}
                />
            )}

            {/* Copy Success Toast */}
            {showCopyToast && (
                <Animated.View
                    style={[
                        styles.copyToast,
                        {
                            opacity: fadeAnim,
                            transform: [
                                {
                                    translateY: fadeAnim.interpolate({
                                        inputRange: [0, 1],
                                        outputRange: [20, 0],
                                    }),
                                },
                            ],
                        },
                    ]}
                >
                    <Ionicons name="checkmark-circle" size={20} color="#4CAF50" />
                    <Text style={styles.copyToastText}>Copied to clipboard!</Text>
                </Animated.View>
            )}

            {/* Image Preview Modal */}
            <ImagePreviewModal
                visible={showImagePreview}
                images={previewImages}
                initialIndex={previewIndex}
                onClose={handleCloseImagePreview}
            />
        </View>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: 'white',
    },
    messagesList: {
        flex: 1,
    },
    messagesContent: {
        padding: 16,
        paddingBottom: 24,
    },
    messageWrapper: {
        position: 'relative',
        marginBottom: 8,
    },
    messageContainer: {
        padding: 12,
        borderRadius: 12,
        maxWidth: '70%',
    },
    userMessage: {
        backgroundColor: '#e6e7e9ff',
        alignSelf: 'flex-end',
    },
    botMessage: {
        backgroundColor: 'white',
        alignSelf: 'flex-start',
        borderWidth: 1,
        borderColor: '#D1D5DB',
    },
    messageHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 6,
        gap: 12,
    },
    messageSender: {
        fontSize: 14,
        fontWeight: '700',
        color: '#333',
    },
    messageTimestamp: {
        fontSize: 10,
        color: '#999',
        flexShrink: 0,
    },
    messageText: {
        fontSize: 16,
        lineHeight: 20,
    },
    userMessageText: {
        color: 'black',
    },
    botMessageText: {
        color: 'black',
    },
    actionButtons: {
        flexDirection: 'row',
        justifyContent: 'flex-end',
        alignItems: 'center',
        marginTop: 8,
        gap: 8,
    },
    actionButton: {
        width: 28,
        height: 28,
        borderRadius: 14,
        justifyContent: 'center',
        alignItems: 'center',
    },
    userActionButton: {
        backgroundColor: 'rgba(0, 0, 0, 0.3)',
    },
    botActionButton: {
        backgroundColor: 'rgba(0, 0, 0, 0.05)',
    },
    loadingContainer: {
        flexDirection: 'row',
        alignItems: 'center',
        padding: 12,
        marginBottom: 12,
    },
    loadingText: {
        marginLeft: 8,
        fontSize: 14,
        color: '#666',
    },
    emptyState: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        padding: 32,
    },
    emptyStateTitle: {
        fontSize: 24,
        fontWeight: '600',
        color: '#333',
        marginBottom: 8,
        textAlign: 'center',
    },
    emptyStateSubtitle: {
        fontSize: 16,
        color: '#666',
        textAlign: 'center',
    },
    copyToast: {
        position: 'absolute',
        bottom: 20,
        left: '50%',
        marginLeft: -100,
        width: 200,
        backgroundColor: '#FFFFFF',
        borderRadius: 24,
        paddingVertical: 12,
        paddingHorizontal: 20,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 8,
        elevation: 8,
        borderWidth: 1,
        borderColor: '#E0E0E0',
    },
    copyToastText: {
        fontSize: 14,
        fontWeight: '600',
        color: '#333',
    },
    menuOverlay: {
        position: 'absolute',
        top: -1000,
        left: -1000,
        right: -1000,
        bottom: -1000,
        zIndex: 999,
    },
    dropdownMenu: {
        position: 'absolute',
        top: '100%',
        right: 0,
        backgroundColor: '#FFFFFF',
        borderRadius: 8,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.15,
        shadowRadius: 8,
        elevation: 5,
        minWidth: 120,
        zIndex: 1000,
        borderWidth: 1,
        borderColor: '#E0E0E0',
        marginTop: 4,
    },
    menuItem: {
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: 16,
        paddingVertical: 12,
        gap: 8,
    },
    menuItemDestructive: {
        borderTopWidth: 1,
        borderTopColor: '#F0F0F0',
    },
    menuItemText: {
        fontSize: 14,
        color: '#333',
        fontWeight: '500',
    },
    menuItemTextDestructive: {
        color: '#FF3B30',
    },
    // Image styles
    imageContainer: {
        marginVertical: 8,
        marginBottom: 4,
    },
    imageContent: {
        gap: 8,
    },
    messageImage: {
        width: 120,
        height: 120,
        borderRadius: 8,
        backgroundColor: '#F0F0F0',
    },
});

export default MessageList;
