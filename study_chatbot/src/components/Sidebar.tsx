import React, { useState } from 'react';
import {
    View,
    Text,
    StyleSheet,
    Modal,
    TouchableOpacity,
    FlatList,
    Alert,
    TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Model } from '../services/api';

export interface ChatHistory {
    id: string;
    title: string;
    timestamp: Date;
    modelUsed?: string;
}

interface SidebarProps {
    isVisible: boolean;
    onClose: () => void;
    chatHistory: ChatHistory[];
    currentChatId: string | null;
    availableModels: Model[];
    onNewChat: () => void;
    onLoadChat: (chatId: string) => void;
    onRefresh?: () => void;
    onRenameChat?: (chatId: string, newName: string) => void;
    onDeleteChat?: (chatId: string) => void;
}

const Sidebar: React.FC<SidebarProps> = ({
    isVisible,
    onClose,
    chatHistory,
    currentChatId,
    availableModels,
    onNewChat,
    onLoadChat,
    onRefresh,
    onRenameChat,
    onDeleteChat,
}) => {
    const [showMenuForChat, setShowMenuForChat] = useState<string | null>(null);
    const [editingChatId, setEditingChatId] = useState<string | null>(null);
    const [editingChatName, setEditingChatName] = useState('');

    const getModelName = (modelId?: string): string | null => {
        if (!modelId) return null;
        const model = availableModels.find(m => m.id === modelId);
        return model?.name || modelId;
    };

    const handleNewChat = () => {
        onNewChat();
        onClose();
    };

    const handleLoadChat = (chatId: string) => {
        if (chatId !== currentChatId) {
            onLoadChat(chatId);
        }
        onClose();
    };

    const handleMenuPress = (chatId: string, event: any) => {
        event.stopPropagation();
        setShowMenuForChat(showMenuForChat === chatId ? null : chatId);
    };

    const handleRename = (chatId: string, currentName: string) => {
        setEditingChatId(chatId);
        setEditingChatName(currentName);
        setShowMenuForChat(null);
    };

    const handleRenameSubmit = () => {
        if (editingChatId && editingChatName.trim() && onRenameChat) {
            onRenameChat(editingChatId, editingChatName.trim());
        }
        setEditingChatId(null);
        setEditingChatName('');
    };

    const handleRenameCancel = () => {
        setEditingChatId(null);
        setEditingChatName('');
    };

    const handleDelete = (chatId: string, chatName: string) => {
        setShowMenuForChat(null);
        Alert.alert(
            'Delete Chat',
            `Are you sure you want to delete "${chatName}"? This action cannot be undone.`,
            [
                { text: 'Cancel', style: 'cancel' },
                {
                    text: 'Delete',
                    style: 'destructive',
                    onPress: () => onDeleteChat?.(chatId)
                }
            ]
        );
    };

    const renderChatItem = ({ item }: { item: ChatHistory }) => (
        <View style={styles.chatItemContainer}>
            <TouchableOpacity
                style={[
                    styles.chatItem,
                    item.id === currentChatId && styles.activeChatItem,
                ]}
                onPress={() => handleLoadChat(item.id)}
            >
                <View style={styles.chatItemContent}>
                    {editingChatId === item.id ? (
                        <View style={styles.editContainer}>
                            <TextInput
                                style={styles.editInput}
                                value={editingChatName}
                                onChangeText={setEditingChatName}
                                onSubmitEditing={handleRenameSubmit}
                                onBlur={handleRenameCancel}
                                autoFocus
                                selectTextOnFocus
                            />
                            <View style={styles.editButtons}>
                                <TouchableOpacity onPress={handleRenameSubmit} style={styles.editButton}>
                                    <Ionicons name="checkmark" size={16} color="#007AFF" />
                                </TouchableOpacity>
                                <TouchableOpacity onPress={handleRenameCancel} style={styles.editButton}>
                                    <Ionicons name="close" size={16} color="#FF3B30" />
                                </TouchableOpacity>
                            </View>
                        </View>
                    ) : (
                        <>
                            <Text
                                style={[
                                    styles.chatTitle,
                                    item.id === currentChatId && styles.activeChatTitle,
                                ]}
                                numberOfLines={1}
                            >
                                {item.title}
                            </Text>
                            <View style={styles.chatMetadata}>
                                <Text style={styles.chatTimestamp}>
                                    {item.timestamp.toLocaleDateString()}
                                </Text>
                                {item.modelUsed && (
                                    <>
                                        <Text style={styles.metadataSeparator}> • </Text>
                                        <Text style={styles.chatModel}>
                                            {getModelName(item.modelUsed)}
                                        </Text>
                                    </>
                                )}
                            </View>
                        </>
                    )}
                </View>
            </TouchableOpacity>

            {editingChatId !== item.id && (
                <TouchableOpacity
                    style={styles.menuButton}
                    onPress={(event) => handleMenuPress(item.id, event)}
                >
                    <Ionicons name="ellipsis-horizontal" size={16} color="#666" />
                </TouchableOpacity>
            )}

            {showMenuForChat === item.id && (
                <View style={styles.menuDropdown}>
                    {onRenameChat && (
                        <TouchableOpacity
                            style={styles.menuItem}
                            onPress={() => handleRename(item.id, item.title)}
                        >
                            <Ionicons name="pencil" size={16} color="#007AFF" />
                            <Text style={styles.menuItemText}>Rename</Text>
                        </TouchableOpacity>
                    )}
                    {onDeleteChat && (
                        <TouchableOpacity
                            style={styles.menuItem}
                            onPress={() => handleDelete(item.id, item.title)}
                        >
                            <Ionicons name="trash" size={16} color="#FF3B30" />
                            <Text style={[styles.menuItemText, styles.deleteText]}>Delete</Text>
                        </TouchableOpacity>
                    )}
                </View>
            )}
        </View>
    );

    return (
        <Modal
            visible={isVisible}
            animationType="slide"
            presentationStyle="pageSheet"
            onRequestClose={onClose}
        >
            <SafeAreaView style={styles.container}>
                <View style={styles.header}>
                    <Text style={styles.headerTitle}>Chat History</Text>
                    <View style={styles.headerButtons}>
                        {onRefresh && (
                            <TouchableOpacity style={styles.headerButton} onPress={onRefresh}>
                                <Ionicons name="refresh" size={20} color="#007AFF" />
                            </TouchableOpacity>
                        )}
                        <TouchableOpacity style={styles.headerButton} onPress={onClose}>
                            <Ionicons name="close" size={24} color="#333" />
                        </TouchableOpacity>
                    </View>
                </View>

                <TouchableOpacity style={styles.newChatButton} onPress={handleNewChat}>
                    <Ionicons name="add" size={20} color="#007AFF" />
                    <Text style={styles.newChatText}>Start New Chat</Text>
                </TouchableOpacity>

                <View style={styles.divider} />

                {chatHistory.length === 0 ? (
                    <View style={styles.emptyState}>
                        <Ionicons name="chatbubbles-outline" size={48} color="#999" />
                        <Text style={styles.emptyStateText}>No chat history yet</Text>
                        <Text style={styles.emptyStateSubtext}>
                            Start a conversation to see your chats here
                        </Text>
                    </View>
                ) : (
                    <FlatList
                        data={chatHistory}
                        renderItem={renderChatItem}
                        keyExtractor={(item) => item.id}
                        style={styles.chatList}
                        showsVerticalScrollIndicator={false}
                    />
                )}
            </SafeAreaView>
        </Modal>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#FFFFFF',
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: 20,
        paddingVertical: 16,
        borderBottomWidth: 1,
        borderBottomColor: '#E0E0E0',
    },
    headerTitle: {
        fontSize: 20,
        fontWeight: '600',
        color: '#333',
    },
    headerButtons: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    headerButton: {
        width: 40,
        height: 40,
        borderRadius: 20,
        justifyContent: 'center',
        alignItems: 'center',
        marginLeft: 8,
    },
    newChatButton: {
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: 20,
        paddingVertical: 16,
        backgroundColor: '#F8F9FA',
        marginHorizontal: 20,
        marginTop: 16,
        borderRadius: 12,
    },
    newChatText: {
        fontSize: 16,
        fontWeight: '500',
        color: '#007AFF',
        marginLeft: 8,
    },
    divider: {
        height: 1,
        backgroundColor: '#E0E0E0',
        marginHorizontal: 20,
        marginTop: 16,
    },
    chatList: {
        flex: 1,
        paddingTop: 16,
    },
    chatItemContainer: {
        position: 'relative',
    },
    chatItem: {
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: 20,
        paddingVertical: 12,
        paddingRight: 60,
        borderBottomWidth: 1,
        borderBottomColor: '#F0F0F0',
        flex: 1,
    },
    activeChatItem: {
        backgroundColor: '#F0F8FF',
        borderBottomColor: '#007AFF',
    },
    chatItemContent: {
        flex: 1,
    },
    chatTitle: {
        fontSize: 16,
        fontWeight: '500',
        color: '#333',
        marginBottom: 4,
    },
    activeChatTitle: {
        color: '#007AFF',
    },
    chatMetadata: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    chatTimestamp: {
        fontSize: 12,
        color: '#999',
    },
    metadataSeparator: {
        fontSize: 12,
        color: '#CCC',
    },
    chatModel: {
        fontSize: 12,
        color: '#007AFF',
        fontWeight: '500',
    },
    emptyState: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        paddingHorizontal: 40,
    },
    emptyStateText: {
        fontSize: 18,
        fontWeight: '500',
        color: '#333',
        marginTop: 16,
        marginBottom: 8,
    },
    emptyStateSubtext: {
        fontSize: 14,
        color: '#666',
        textAlign: 'center',
        lineHeight: 20,
    },
    menuButton: {
        position: 'absolute',
        right: 20,
        top: '50%',
        transform: [{ translateY: -16 }],
        width: 32,
        height: 32,
        justifyContent: 'center',
        alignItems: 'center',
        borderRadius: 16,
        backgroundColor: 'rgba(0, 0, 0, 0.05)',
    },
    menuDropdown: {
        position: 'absolute',
        right: 20,
        top: 48,
        backgroundColor: '#FFFFFF',
        borderRadius: 8,
        shadowColor: '#000',
        shadowOffset: {
            width: 0,
            height: 2,
        },
        shadowOpacity: 0.1,
        shadowRadius: 4,
        elevation: 3,
        borderWidth: 1,
        borderColor: '#E0E0E0',
        zIndex: 1000,
    },
    menuItem: {
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: 16,
        paddingVertical: 12,
        minWidth: 120,
    },
    menuItemText: {
        fontSize: 14,
        color: '#333',
        marginLeft: 8,
    },
    deleteText: {
        color: '#FF3B30',
    },
    editContainer: {
        flex: 1,
        flexDirection: 'row',
        alignItems: 'center',
    },
    editInput: {
        flex: 1,
        fontSize: 16,
        color: '#333',
        borderWidth: 1,
        borderColor: '#007AFF',
        borderRadius: 6,
        paddingHorizontal: 8,
        paddingVertical: 4,
        marginRight: 8,
    },
    editButtons: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    editButton: {
        padding: 4,
        marginLeft: 4,
    },
});

export default Sidebar;
