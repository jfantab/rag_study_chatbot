import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import {
    sendChatMessage,
    generateSessionId,
    createNewChat,
    getChatHistory,
    getChatNames,
    deleteChat as apiDeleteChat,
    deleteMessage as apiDeleteMessage,
    editMessage as apiEditMessage,
    getCurrentModel,
    getAvailableModels,
    uploadImage,
    uploadDocument,
    ApiMessage,
    Model,
} from '../services/api';
import { ChatHistory } from '../components/Sidebar';
import { FileAttachment } from '../services/DocumentPickerService';
import { useToast } from './ToastContext';
import { useAuth } from './AuthContext';

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
    isEditingMessage: boolean;
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
    editMessage: (messageId: number, newContent: string) => Promise<void>;
    setCurrentModelName: (modelName: string) => void;
    loadCurrentModel: () => Promise<void>;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export const ChatProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const { showToast } = useToast();
    const { isAuthenticated, isLoading: authLoading } = useAuth();
    const [messages, setMessages] = useState<Message[]>([]);
    const [inputValue, setInputValue] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isEditingMessage, setIsEditingMessage] = useState(false);
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
            // Don't throw - let the app continue with empty models list
            setAvailableModels([]);
        }
    };

    // Load current model name
    const loadCurrentModel = async () => {
        try {
            const modelData = await getCurrentModel();
            setCurrentModelName(modelData.current_model_name || 'Unknown Model');
        } catch (error) {
            console.error('Error loading current model:', error);
            setCurrentModelName('Connection Error');
            // Don't throw - let the app continue to function
        }
    };

    // Load chat history and current model ONLY when authenticated
    useEffect(() => {
        // Don't fetch anything if:
        // 1. Auth is still loading
        // 2. User is not authenticated
        if (authLoading || !isAuthenticated) {
            return;
        }

        const initialize = async () => {
            try {
                // Use Promise.allSettled to allow partial success
                const results = await Promise.allSettled([
                    refreshChatHistory(),
                    loadCurrentModel(),
                    fetchAvailableModels(),
                ]);

                // Log any failures but don't crash the app
                results.forEach((result, index) => {
                    if (result.status === 'rejected') {
                        const taskNames = ['refreshChatHistory', 'loadCurrentModel', 'fetchAvailableModels'];
                        console.error(`${taskNames[index]} failed:`, result.reason);
                    }
                });

                // If no chat history exists, start a new chat session (but don't save it yet)
                try {
                    const chats = await getChatNames();
                    if (chats.length === 0) {
                        // Just generate a session ID, don't create the chat yet
                        const newSessionId = generateSessionId();
                        setSessionId(newSessionId);
                        setCurrentChatId(null);
                    }
                } catch (error) {
                    // If getChatNames fails, start a new session anyway
                    const newSessionId = generateSessionId();
                    setSessionId(newSessionId);
                    setCurrentChatId(null);
                }
            } catch (error) {
                // If authentication fails, let the error propagate
                // The user will be redirected to login via the navigation guard
            }
        };

        initialize();
    }, [isAuthenticated, authLoading]); // Re-run when authentication status changes

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
                files: msg.file_attachments, // Include file attachments from backend
            });
        });
        return messages;
    };

    // Refresh chat history from server
    const refreshChatHistory = async () => {
        try {
            const chats = await getChatNames();
            const formattedChats: ChatHistory[] = chats.map(chat => ({
                id: chat.session_id,
                title: chat.chat_name,
                timestamp: new Date(chat.updated_at),
                modelUsed: chat.model_id,
            }));
            setChatHistory(formattedChats);
        } catch (error) {
            console.error('Error refreshing chat history:', error);
            // Don't show toast on initial load failures - just log the error
            // The app can still function with an empty chat history
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

    // Edit a single message
    const editMessage = async (messageId: number, newContent: string) => {
        if (!currentChatId) {
            console.error('❌ Cannot edit message without a chat ID.');
            showToast('Cannot edit message: No active chat session', 'error');
            return;
        }

        const messageIndex = messages.findIndex(m => m.id === messageId);
        if (messageIndex === -1) {
            console.error('❌ Message to edit not found in state.');
            showToast('Message not found', 'error');
            return;
        }

        const messageToEdit = messages[messageIndex];

        // Only allow editing user messages without attachments
        if (!messageToEdit.isUser) {
            console.error('❌ Cannot edit bot messages.');
            showToast('Cannot edit bot messages', 'error');
            return;
        }

        if (messageToEdit.images && messageToEdit.images.length > 0) {
            console.error('❌ Cannot edit messages with images.');
            showToast('Cannot edit messages with images', 'error');
            return;
        }

        if (messageToEdit.files && messageToEdit.files.length > 0) {
            console.error('❌ Cannot edit messages with files.');
            showToast('Cannot edit messages with files', 'error');
            return;
        }

        // Save original messages for rollback on error
        const originalMessages = [...messages];

        try {
            // OPTIMISTIC UPDATE: Update UI immediately before backend call
            const optimisticMessages = [...messages];

            // Update the user message content
            optimisticMessages[messageIndex] = {
                ...optimisticMessages[messageIndex],
                content: newContent,
            };

            // Replace the AI response with "Thinking..." placeholder
            if (messageIndex + 1 < optimisticMessages.length && !optimisticMessages[messageIndex + 1].isUser) {
                // Replace existing AI message with thinking placeholder
                optimisticMessages[messageIndex + 1] = {
                    ...optimisticMessages[messageIndex + 1],
                    content: 'Thinking...',
                };
            } else {
                // Add a new AI message placeholder
                optimisticMessages.splice(messageIndex + 1, 0, {
                    id: messageIdCounter,
                    content: 'Thinking...',
                    isUser: false,
                    timestamp: new Date(),
                });
            }

            // Apply optimistic update to UI
            setMessages(optimisticMessages);

            // Mark as editing message (don't show bottom loading indicator)
            setIsEditingMessage(true);

            // CRITICAL: Use backend timestamp if available (for new message table)
            // Fall back to message index for old table
            let messageIdentifier: string | number;

            if (messageToEdit.backendTimestamp) {
                messageIdentifier = messageToEdit.backendTimestamp;
            } else {
                messageIdentifier = messageIndex;
            }

            // Call the API to edit the message - this will resend and regenerate the AI response
            const newAiResponse = await apiEditMessage(currentChatId, messageIdentifier, newContent);

            // Reload messages from backend to get the updated state with regenerated response
            const apiMessages = await getChatHistory(currentChatId);
            const updatedMessages = convertApiMessages(apiMessages);
            setMessages(updatedMessages);
            setMessageIdCounter(updatedMessages.length);

            showToast('Message edited and response regenerated', 'success');

        } catch (error) {
            console.error('❌ Error editing message:', error);
            console.error('❌ Error details:', {
                errorType: error instanceof Error ? error.constructor.name : typeof error,
                errorMessage: error instanceof Error ? error.message : String(error),
                errorStack: error instanceof Error ? error.stack : undefined,
                messageId,
                messageIndex,
                hasTimestamp: !!messageToEdit.backendTimestamp,
                timestamp: messageToEdit.backendTimestamp,
                newContentLength: newContent.length,
            });

            // ROLLBACK: Restore original messages on error
            setMessages(originalMessages);

            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            showToast(`Failed to edit message: ${errorMessage}`, 'error');

            // Don't throw - just show the error and exit edit mode
            // The MessageItem component will handle staying in edit mode if needed
        } finally {
            setIsEditingMessage(false);
        }
    };

    // Delete a single message
    const deleteMessage = async (messageId: number) => {
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

        try {
            // CRITICAL FIX: Always reload messages from backend before deleting
            // This ensures we have the correct backend timestamps
            if (!messageToDelete.backendTimestamp) {
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

                    // Now delete using the correct timestamp
                    await apiDeleteMessage(currentChatId, reloadedMessage.backendTimestamp);

                } catch (reloadError) {
                    console.error('❌ Failed to reload messages:', reloadError);
                    alert('Failed to delete: could not reload message data');
                    return;
                }
            } else {
                // Message has timestamp, proceed with delete
                await apiDeleteMessage(currentChatId, messageToDelete.backendTimestamp);
            }

            // Reload messages from backend to get the updated state
            const apiMessages = await getChatHistory(currentChatId);
            const updatedMessages = convertApiMessages(apiMessages);
            setMessages(updatedMessages);
            setMessageIdCounter(updatedMessages.length);

            // If chat was deleted (no messages remaining), refresh chat history and start new chat
            if (updatedMessages.length === 0) {
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
                // Use the first message (truncated) as the chat name
                const chatName = message.trim().length > 50
                    ? message.trim().substring(0, 47) + '...'
                    : message.trim();

                await createNewChat(sessionId, chatName);
                setCurrentChatId(sessionId);
            }

            // Upload images to S3 if any
            let imageUrls: string[] | undefined = undefined;
            if (images && images.length > 0) {
                try {
                    imageUrls = await Promise.all(
                        images.map(imageUri => uploadImage(imageUri, sessionId))
                    );

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

            // Upload documents to S3 and prepare for backend processing
            let filesForBackend: any[] | undefined = undefined;
            if (files && files.length > 0) {
                try {
                    // Step 1: Upload to S3 for persistence (in background)
                    const uploadPromises = files.map(file =>
                        uploadDocument(file.uri, file.name, file.type, file.size, sessionId)
                            .catch(err => {
                                console.warn('⚠️ S3 upload failed (non-critical):', err);
                                return null; // Continue even if S3 upload fails
                            })
                    );

                    // Step 2: Read file content as base64 for immediate processing
                    const contentPromises = files.map(async (file) => {
                        const fileBase64 = await fetch(file.uri)
                            .then(res => res.blob())
                            .then(blob => new Promise<string>((resolve, reject) => {
                                const reader = new FileReader();
                                reader.onloadend = () => {
                                    const base64String = (reader.result as string).split(',')[1];
                                    resolve(base64String);
                                };
                                reader.onerror = reject;
                                reader.readAsDataURL(blob);
                            }));

                        return {
                            name: file.name,
                            type: file.type,
                            size: file.size,
                            content: fileBase64, // Base64 encoded content for backend processing
                        };
                    });

                    // Wait for both S3 uploads and content reading
                    const [uploadResults, filesWithContent] = await Promise.all([
                        Promise.all(uploadPromises),
                        Promise.all(contentPromises)
                    ]);

                    filesForBackend = filesWithContent;

                    // Update the user message to show files in UI
                    setMessages(prev =>
                        prev.map(msg =>
                            msg.id === newMessageId
                                ? { ...msg, files: files }
                                : msg
                        )
                    );
                } catch (uploadError) {
                    console.error('❌ Error processing documents:', uploadError);
                    throw new Error('Failed to process documents. Please try again.');
                }
            }

            // Call the real API with uploaded image URLs and file content
            const response = await sendChatMessage(message.trim(), sessionId, imageUrls, filesForBackend);

            const botMessage: Message = {
                id: newMessageId + 1,
                content: response,
                isUser: false,
                timestamp: new Date(),
            };
            setMessages(prev => [...prev, botMessage]);
            setMessageIdCounter(newMessageId + 2);

            // IMPORTANT: Reload messages from backend to get proper timestamps for delete/edit
            try {
                const apiMessages = await getChatHistory(sessionId);
                const reloadedMessages = convertApiMessages(apiMessages);
                setMessages(reloadedMessages);
                setMessageIdCounter(reloadedMessages.length);
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
