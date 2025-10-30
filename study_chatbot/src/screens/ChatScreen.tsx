import React, { useState } from 'react';
import {
    StyleSheet,
    View,
    KeyboardAvoidingView,
    Platform,
    TouchableOpacity,
    Text,
    StatusBar,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useChat } from '../contexts/ChatContext';
import MessageList from '../components/MessageList';
import ChatInput from '../components/ChatInput';
import Sidebar from '../components/Sidebar';
import ModelSwitcher from '../components/ModelSwitcher';

export default function ChatScreen() {
    const {
        messages,
        inputValue,
        isLoading,
        isEditingMessage,
        chatHistory,
        currentChatId,
        currentModelName,
        availableModels,
        setInputValue,
        sendMessage,
        startNewChat,
        loadChat,
        refreshChatHistory,
        deleteChat,
        deleteMessage,
        editMessage,
        setCurrentModelName,
    } = useChat();

    const insets = useSafeAreaInsets();
    const [sidebarVisible, setSidebarVisible] = useState(false);
    const [modelSwitcherVisible, setModelSwitcherVisible] = useState(false);

    const handleModelChanged = (modelName: string) => {
        setCurrentModelName(modelName);
    };

    return (
        <View style={styles.container}>
            <StatusBar
                barStyle="dark-content"
                backgroundColor="transparent"
                translucent={true}
            />

            {/* Header with menu button and model switcher */}
            <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
                <TouchableOpacity
                    style={styles.menuButton}
                    onPress={() => setSidebarVisible(true)}
                >
                    <Ionicons name="menu" size={24} color="#333" />
                </TouchableOpacity>

                <TouchableOpacity
                    style={styles.modelButton}
                    onPress={() => setModelSwitcherVisible(true)}
                    activeOpacity={0.7}
                >
                    <Text style={styles.modelName} numberOfLines={1}>
                        {currentModelName}
                    </Text>
                    <Ionicons
                        name="chevron-down"
                        size={20}
                        color="#007AFF"
                    />
                </TouchableOpacity>

                <TouchableOpacity
                    style={styles.menuButton}
                    onPress={startNewChat}
                >
                    <Ionicons name="add" size={24} color="#333" />
                </TouchableOpacity>
            </View>

            <KeyboardAvoidingView
                style={styles.keyboardAvoidingView}
                behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
                keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
            >
                <View style={styles.innerContainer}>
                    <MessageList
                        messages={messages}
                        isLoading={isLoading}
                        isEditingMessage={isEditingMessage}
                        onDeleteMessage={deleteMessage}
                        onEditMessage={editMessage}
                    />
                    <ChatInput
                        value={inputValue}
                        onChangeText={setInputValue}
                        onSend={sendMessage}
                        isLoading={isLoading}
                    />
                </View>
            </KeyboardAvoidingView>

            {/* Sidebar for chat history */}
            <Sidebar
                isVisible={sidebarVisible}
                onClose={() => setSidebarVisible(false)}
                chatHistory={chatHistory}
                currentChatId={currentChatId}
                availableModels={availableModels}
                onNewChat={startNewChat}
                onLoadChat={loadChat}
                onRefresh={refreshChatHistory}
                onDeleteChat={deleteChat}
            />

            {/* Model Switcher */}
            <ModelSwitcher
                isVisible={modelSwitcherVisible}
                onClose={() => setModelSwitcherVisible(false)}
                onModelChanged={handleModelChanged}
                onStartNewChat={startNewChat}
            />
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#FFFFFF',
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: 16,
        paddingBottom: 12,
        borderBottomWidth: 1,
        borderBottomColor: '#E0E0E0',
        backgroundColor: '#FFFFFF',
        ...Platform.select({
            ios: {
                shadowColor: '#000',
                shadowOffset: { width: 0, height: 1 },
                shadowOpacity: 0.1,
                shadowRadius: 2,
            },
            android: {
                elevation: 2,
            },
        }),
    },
    menuButton: {
        width: 40,
        height: 40,
        borderRadius: 20,
        justifyContent: 'center',
        alignItems: 'center',
    },
    modelButton: {
        flex: 1,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        paddingHorizontal: 12,
        paddingVertical: 8,
        marginHorizontal: 8,
        borderRadius: 8,
    },
    modelName: {
        fontSize: 18,
        fontWeight: '600',
        color: '#333',
        marginRight: 4,
    },
    keyboardAvoidingView: {
        flex: 1,
    },
    innerContainer: {
        flex: 1,
    },
});
