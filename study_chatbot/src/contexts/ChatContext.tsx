import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import {
    sendChatMessage,
    generateSessionId,
    createNewChat,
    getChatHistory,
    getChatNames,
    deleteChat as apiDeleteChat,
    deleteMessage as apiDeleteMessage,
    getCurrentModel,
    getAvailableModels,
    uploadImage,
    ApiMessage,
    Model,
} from '../services/api';
import { ChatHistory } from '../components/Sidebar';
import { FileAttachment } from '../services/DocumentPickerService';
import { useToast } from './ToastContext';

interface Message {
    id: number;
    content: string;
    isUser: boolean;
    timestamp: Date;
    backendTimestamp?: string; // ISO timestamp from backend
    images?: string[]; // Image URIs
    files?: FileAttachment[]; // File attachments
}

interface ChatContextType {
    messages: Message[];
    inputValue: string;
    isLoading: boolean;
    chatHistory: ChatHistory[];
    currentChatId: string | null;
    currentModelName: string;
    availableModels: Model[];
    setInputValue: (value: string) => void;
    sendMessage: (message: string, images?: string[], files?: FileAttachment[]) => void;
    startNewChat: () => void;
    loadChat: (chatId: string) => Promise<void>;
    refreshChatHistory: () => Promise<void>;
    deleteChat: (chatId: string) => Promise<void>;
    deleteMessage: (messageId: number) => Promise<void>;
    setCurrentModelName: (modelName: string) => void;
    loadCurrentModel: () => Promise<void>;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export const ChatProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const { showToast } = useToast();
    const [messages, setMessages] = useState<Message[]>([]);
    const [inputValue, setInputValue] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [messageIdCounter, setMessageIdCounter] = useState(0);
    const [sessionId, setSessionId] = useState(generateSessionId());
    const [chatHistory, setChatHistory] = useState<ChatHistory[]>([]);
    const [currentChatId, setCurrentChatId] = useState<string | null>(null);
    const [currentModelName, setCurrentModelName] = useState<string>('Loading...');
    const [availableModels, setAvailableModels] = useState<Model[]>([]);

    // Fetch available models
    const fetchAvailableModels = async () => {
        try {
            const models = await getAvailableModels();
            setAvailableModels(models);
        } catch (error) {
            console.error('Error fetching available models:', error);
        }
    };

    // Load current model name
    const loadCurrentModel = async () => {
        try {
            const modelData = await getCurrentModel();
            setCurrentModelName(modelData.current_model_name || 'Unknown Model');
        } catch (error) {
            console.error('Error loading current model:', error);
            setCurrentModelName('Model Unavailable');
        }
    };

    // Load chat history and current model on mount
    useEffect(() => {
        const initialize = async () => {
            try {
                await Promise.all([
                    refreshChatHistory(),
                    loadCurrentModel(),
                    fetchAvailableModels(),
                ]);

                // If no chat history exists, start a new chat session (but don't save it yet)
                const chats = await getChatNames();
                if (chats.length === 0) {
                    // Just generate a session ID, don't create the chat yet
                    const newSessionId = generateSessionId();
                    setSessionId(newSessionId);
                    setCurrentChatId(null);
                    console.log('No chat history found, starting new session (not saved):', newSessionId);
                }
            } catch (error) {
                // If authentication fails, let the error propagate
                // The user will be redirected to login via the navigation guard
                if (error instanceof Error && error.message.includes('Authentication required')) {
                    console.log('Authentication required, user needs to sign in');
                }
            }
        };

        initialize();
    }, []);

    // Convert API messages to local Message format
    const convertApiMessages = (apiMessages: ApiMessage[]): Message[] => {
        let messages: Message[] = [];
        apiMessages.forEach((msg, index) => {
            messages.push({
                id: messages.length, // Use messages array length for unique ID
                content: msg.msg,
                isUser: msg.role === 'human',
                timestamp: new Date(msg.timestamp || Date.now()),
                backendTimestamp: msg.timestamp, // Keep original timestamp for API calls
                images: msg.image_urls, // Include image URLs from backend
            });
        });
        return messages;
    };

    // Refresh chat history from server
    const refreshChatHistory = async () => {
        try {
            const chats = await getChatNames();
            const formattedChats: ChatHistory[] = chats.map(chat => ({
                id: chat.id,
                title: chat.name,
                timestamp: new Date(chat.key), // key is timestamp in milliseconds
                modelUsed: chat.model_used, // Include model information
            }));
            setChatHistory(formattedChats);
        } catch (error) {
            console.error('Error refreshing chat history:', error);
        }
    };

    // Start a new chat (only creates session ID, actual chat created on first message)
    const startNewChat = async () => {
        const newSessionId = generateSessionId();

        // Don't create the chat in the database yet - wait for first message
        setSessionId(newSessionId);
        setCurrentChatId(null); // Set to null since chat doesn't exist yet
        setMessages([]);
        setMessageIdCounter(0);
        loadCurrentModel(); // Reset to default model

        console.log('Started new chat session (not saved yet):', newSessionId);
    };

    // Load an existing chat
    const loadChat = async (chatId: string) => {
        try {
            setIsLoading(true);
            const apiMessages = await getChatHistory(chatId);
            const loadedMessages = convertApiMessages(apiMessages);
            setMessages(loadedMessages);
            setSessionId(chatId);
            setCurrentChatId(chatId);
            setMessageIdCounter(loadedMessages.length);

            // Find the chat in history and update the model name
            const chat = chatHistory.find(c => c.id === chatId);
            if (chat && chat.modelUsed) {
                const model = availableModels.find(m => m.id === chat.modelUsed);
                setCurrentModelName(model?.name || chat.modelUsed);
            }

        } catch (error) {
            console.error('Error loading chat:', error);
        } finally {
            setIsLoading(false);
        }
    };

    // Delete a chat
    const deleteChat = async (chatId: string) => {
        try {
            await apiDeleteChat(chatId);
            await refreshChatHistory();

            // If deleting current chat, start a new one
            if (chatId === currentChatId) {
                await startNewChat();
            }
        } catch (error) {
            console.error('Error deleting chat:', error);
            throw error;
        }
    };

    // Delete a single message
    const deleteMessage = async (messageId: number) => {
        console.log('🚀 ChatContext.deleteMessage CALLED with messageId:', messageId);

        if (!currentChatId) {
            console.error('❌ Cannot delete message without a chat ID.');
            alert('Cannot delete message: No active chat session');
            return;
        }

        const messageIndex = messages.findIndex(m => m.id === messageId);
        if (messageIndex === -1) {
            console.error('❌ Message to delete not found in state.');
            alert('Message not found');
            return;
        }

        const messageToDelete = messages[messageIndex];
        console.log('🗑️ Deleting message:', {
            messageId,
            messageIndex,
            totalMessages: messages.length,
            hasBackendTimestamp: !!messageToDelete.backendTimestamp,
            backendTimestamp: messageToDelete.backendTimestamp,
            messageContent: messageToDelete.content.substring(0, 50),
        });

        console.log('📋 All messages with timestamps:', messages.map((m, idx) => ({
            idx,
            id: m.id,
            hasBackendTimestamp: !!m.backendTimestamp,
            timestamp: m.backendTimestamp?.substring(0, 19) || 'NONE',
            isUser: m.isUser
        })));

        try {
            // CRITICAL FIX: Always reload messages from backend before deleting
            // This ensures we have the correct backend timestamps
            if (!messageToDelete.backendTimestamp) {
                console.log('⚠️ Message missing backendTimestamp, reloading from server...');
                try {
                    const apiMessages = await getChatHistory(currentChatId);
                    const reloadedMessages = convertApiMessages(apiMessages);
                    setMessages(reloadedMessages);
                    setMessageIdCounter(reloadedMessages.length);

                    // Find the message again after reload
                    const reloadedMessageIndex = reloadedMessages.findIndex(m =>
                        m.content === messageToDelete.content &&
                        m.isUser === messageToDelete.isUser
                    );

                    if (reloadedMessageIndex === -1) {
                        console.error('❌ Message not found after reload');
                        alert('Failed to delete: message not found in database');
                        return;
                    }

                    const reloadedMessage = reloadedMessages[reloadedMessageIndex];
                    if (!reloadedMessage.backendTimestamp) {
                        console.error('❌ Message still missing timestamp after reload');
                        alert('Failed to delete: message timestamp not available');
                        return;
                    }

                    console.log('✅ Messages reloaded, found timestamp:', reloadedMessage.backendTimestamp);

                    // Now delete using the correct timestamp
                    await apiDeleteMessage(currentChatId, reloadedMessage.backendTimestamp);

                } catch (reloadError) {
                    console.error('❌ Failed to reload messages:', reloadError);
                    alert('Failed to delete: could not reload message data');
                    return;
                }
            } else {
                // Message has timestamp, proceed with delete
                console.log('📤 Sending delete request with timestamp:', messageToDelete.backendTimestamp);
                await apiDeleteMessage(currentChatId, messageToDelete.backendTimestamp);
            }

            console.log('✅ Server delete successful, reloading messages...');

            // Reload messages from backend to get the updated state
            const apiMessages = await getChatHistory(currentChatId);
            const updatedMessages = convertApiMessages(apiMessages);
            setMessages(updatedMessages);
            setMessageIdCounter(updatedMessages.length);

            console.log(`✅ Message deleted and UI updated`);

            // If chat was deleted (no messages remaining), refresh chat history and start new chat
            if (updatedMessages.length === 0) {
                console.log('⚠️  No messages remaining, chat will be cleaned up');
                await refreshChatHistory();
                await startNewChat();
                showToast('All messages deleted. Starting a new chat.', 'info');
            }

        } catch (error) {
            console.error('❌ Error deleting message:', error);
            showToast(`Failed to delete message: ${error instanceof Error ? error.message : 'Unknown error'}`, 'error');
            throw error;
        }
    };


    const sendMessage = async (message: string, images?: string[], files?: FileAttachment[]) => {
        if (!message.trim() && (!images || images.length === 0) && (!files || files.length === 0)) return;

        const newMessageId = messageIdCounter;
        setMessageIdCounter(messageIdCounter + 1);

        // Add user message
        const userMessage: Message = {
            id: newMessageId,
            content: message.trim(),
            isUser: true,
            timestamp: new Date(),
            images: images,
            files: files,
        };

        setMessages(prev => [...prev, userMessage]);
        setInputValue('');
        setIsLoading(true);

        try {
            // If this is the first message (no current chat ID), create the chat
            if (!currentChatId) {
                console.log('Creating new chat with first message...');
                // Use the first message (truncated) as the chat name
                const chatName = message.trim().length > 50
                    ? message.trim().substring(0, 47) + '...'
                    : message.trim();

                await createNewChat(sessionId, chatName);
                setCurrentChatId(sessionId);
                console.log('✅ Chat created:', sessionId, chatName);
            }

            // Upload images to S3 if any
            let imageUrls: string[] | undefined = undefined;
            if (images && images.length > 0) {
                console.log(`📤 Uploading ${images.length} images to S3...`);
                try {
                    imageUrls = await Promise.all(
                        images.map(imageUri => uploadImage(imageUri, sessionId))
                    );
                    console.log('✅ All images uploaded successfully:', imageUrls);

                    // Update the user message with S3 URLs so images display correctly
                    setMessages(prev =>
                        prev.map(msg =>
                            msg.id === newMessageId
                                ? { ...msg, images: imageUrls }
                                : msg
                        )
                    );
                } catch (uploadError) {
                    console.error('❌ Error uploading images:', uploadError);
                    throw new Error('Failed to upload images. Please try again.');
                }
            }

            // Call the real API with uploaded image URLs
            const response = await sendChatMessage(message.trim(), sessionId, imageUrls, files);

            const botMessage: Message = {
                id: newMessageId + 1,
                content: response,
                isUser: false,
                timestamp: new Date(),
            };
            setMessages(prev => [...prev, botMessage]);
            setMessageIdCounter(newMessageId + 2);

            // IMPORTANT: Reload messages from backend to get proper timestamps for delete/edit
            console.log('🔄 Reloading messages from backend to get timestamps...');
            try {
                const apiMessages = await getChatHistory(sessionId);
                const reloadedMessages = convertApiMessages(apiMessages);
                setMessages(reloadedMessages);
                setMessageIdCounter(reloadedMessages.length);
                console.log('✅ Messages reloaded with backend timestamps');
            } catch (reloadError) {
                console.error('⚠️ Failed to reload messages (delete may not work):', reloadError);
                // Continue anyway - messages are still displayed
            }

            // Refresh chat history to show the new chat in the sidebar
            if (messages.length === 0) {
                await refreshChatHistory();
            }
        } catch (error) {
            console.error('Error sending message:', error);

            // Show error message to user
            const errorMessage: Message = {
                id: newMessageId + 1,
                content: `Error: ${error instanceof Error ? error.message : 'Failed to send message. Please check if the server is running.'}`,
                isUser: false,
                timestamp: new Date(),
            };
            setMessages(prev => [...prev, errorMessage]);
            setMessageIdCounter(newMessageId + 2);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <ChatContext.Provider
            value={{
                messages,
                inputValue,
                isLoading,
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
                deleteMessage, // Add this
                setCurrentModelName,
                loadCurrentModel,
            }}
        >
            {children}
        </ChatContext.Provider>
    );
};

export const useChat = () => {
    const context = useContext(ChatContext);
    if (!context) {
        throw new Error('useChat must be used within a ChatProvider');
    }
    return context;
};
