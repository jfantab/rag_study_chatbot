import { Buffer } from 'buffer';

/**
 * API Service for communicating with the RAG Study Chatbot backend
 * Includes Cognito authentication with JWT tokens
 */

import { API_BASE_URL as ENV_API_BASE_URL } from '@env';
import { getIdToken } from './cognitoService';

// Configuration - from environment variables
// For iOS simulator: use http://localhost:8000
// For Android emulator: use http://10.0.2.2:8000
// For physical device: use your computer's IP address
const API_BASE_URL = ENV_API_BASE_URL || 'http://192.168.1.105:8000';

// Request timeout configuration
const REQUEST_TIMEOUT = 120000; // 120 seconds

// Interfaces
interface ChatRequest {
    msg: string;
    msg_id: string;
    image_urls?: string[];
    files?: any[];
}

interface ChatResponse {
    answer: string;
}

export interface ApiMessage {
    role: 'human' | 'ai';
    msg: string;
    image_urls?: string[];
    file_attachments?: Array<{
        name: string;
        type: string;
        size: number;
    }>;
    timestamp?: string; // ISO8601 timestamp from backend (for new message table)
}

export interface ChatHistoryResponse {
    msgs: ApiMessage[];
}

export interface ChatNamesResponse {
    chats: Array<{
        id: string;
        key: number;
        name: string;
        model_used?: string;
    }>;
}

export interface Model {
    name: string;
    id: string;
    category: string;
}

export interface ModelsResponse {
    models: Model[];
    total_count: number;
}

export interface CurrentModelResponse {
    current_model_name: string | null;
    current_model_id: string;
}

export interface ChangeModelResponse {
    success: boolean;
    message?: string;
    model_name?: string;
    model_id?: string;
    error?: string;
}

/**
 * Helper function to create fetch with timeout
 */
const fetchWithTimeout = (url: string, options: RequestInit = {}) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

    return fetch(url, {
        ...options,
        signal: controller.signal,
    }).finally(() => {
        clearTimeout(timeoutId);
    });
};

/**
 * Get authentication headers with JWT token
 * Includes automatic token refresh if expired
 */
const getAuthHeaders = async (): Promise<HeadersInit> => {
    let token = await getIdToken();
    const { refreshSession } = await import('./cognitoService');
    let needsRefresh = false;

    if (token) {
        try {
            const payloadBase64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
            const payloadJson = Buffer.from(payloadBase64, 'base64').toString();
            const payload = JSON.parse(payloadJson);

            if (payload.exp * 1000 < Date.now()) {
                console.log('Token expired, flagging for refresh.');
                needsRefresh = true;
            }
        } catch (e) {
            console.error('Error decoding token:', e);
            // Can't determine if expired, but something is wrong with the token.
            // Let's try refreshing it just in case.
            needsRefresh = true;
        }
    } else {
        // No token at all
        needsRefresh = true;
    }

    if (needsRefresh) {
        console.log('Attempting to refresh session...');
        token = await refreshSession();
    }

    const headers: HeadersInit = {
        'Content-Type': 'application/json',
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    return headers;
};

// Track if we're currently refreshing to prevent multiple simultaneous refresh attempts
let isRefreshing = false;
let refreshPromise: Promise<string | null> | null = null;

/**
 * Wrapper for fetch with automatic token refresh on 401 errors
 */
const fetchWithAuth = async (
    url: string,
    options: RequestInit = {},
    retryCount: number = 0
): Promise<Response> => {
    const headers = await getAuthHeaders();
    const response = await fetch(url, {
        ...options,
        headers: {
            ...headers,
            ...options.headers,
        },
    });

    // Handle 401 errors with automatic token refresh and retry
    if (response.status === 401 && retryCount === 0) {
        console.log('🔄 Token expired, attempting to refresh session...');

        // If already refreshing, wait for that refresh to complete
        if (isRefreshing && refreshPromise) {
            const newToken = await refreshPromise;
            if (newToken) {
                return fetchWithAuth(url, options, retryCount + 1);
            } else {
                throw new Error('Authentication required. Please sign in again.');
            }
        }

        // Start a new refresh
        isRefreshing = true;
        const { refreshSession } = await import('./cognitoService');
        refreshPromise = refreshSession();

        try {
            const newToken = await refreshPromise;

            if (newToken) {
                console.log('✅ Token refreshed, retrying request...');
                // Retry the request with new token
                return fetchWithAuth(url, options, retryCount + 1);
            } else {
                console.log('❌ Token refresh failed, authentication required');
                throw new Error('Authentication required. Please sign in again.');
            }
        } finally {
            isRefreshing = false;
            refreshPromise = null;
        }
    }

    return response;
};

/**
 * Upload an image to S3
 * Returns the S3 URL of the uploaded image
 */
export const uploadImage = async (
    imageUri: string,
    sessionId: string
): Promise<string> => {
    try {
        console.log('📤 Uploading image to S3:', imageUri);

        // Create form data
        const formData = new FormData();

        // Extract filename from URI or use a default
        const filename = imageUri.split('/').pop() || 'image.jpg';

        // Create file object for React Native
        const file: any = {
            uri: imageUri,
            type: 'image/jpeg', // Default to JPEG, can be made dynamic
            name: filename,
        };

        formData.append('file', file);
        formData.append('chatId', sessionId);

        const authHeaders = await getAuthHeaders();

        const response = await fetchWithTimeout(`${API_BASE_URL}/upload-image`, {
            method: 'POST',
            headers: {
                ...authHeaders,
                // Don't set Content-Type - let the browser/RN set it with boundary
            },
            body: formData,
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(
                errorData.error || `Failed to upload image: ${response.status}`
            );
        }

        const data = await response.json();
        console.log('✅ Image uploaded successfully:', data.s3_url);

        return data.s3_url;
    } catch (error) {
        console.error('❌ Error uploading image:', error);
        throw error;
    }
};

/**
 * Upload a document to S3
 * Returns file metadata including S3 key
 */
export const uploadDocument = async (
    fileUri: string,
    fileName: string,
    fileType: string,
    fileSize: number,
    sessionId: string
): Promise<{ file_id: string; s3_key: string; filename: string }> => {
    try {
        console.log('📄 Uploading document to S3:', fileName);

        // Create form data
        const formData = new FormData();

        // Create file object for React Native
        const file: any = {
            uri: fileUri,
            type: fileType,
            name: fileName,
        };

        formData.append('file', file);

        const authHeaders = await getAuthHeaders();

        const response = await fetchWithTimeout(`${API_BASE_URL}/upload_to_s3`, {
            method: 'POST',
            headers: {
                ...authHeaders,
                // Don't set Content-Type - let the browser/RN set it with boundary
            },
            body: formData,
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(
                errorData.error || `Failed to upload document: ${response.status}`
            );
        }

        const data = await response.json();
        console.log('✅ Document uploaded successfully:', data);

        return {
            file_id: data.file_id,
            s3_key: data.s3_key,
            filename: data.filename,
        };
    } catch (error) {
        console.error('❌ Error uploading document:', error);
        throw error;
    }
};

/**
 * Send a chat message to the server (Bedrock invoke)
 * Includes authentication token in headers with automatic retry on token expiration
 */
export const sendChatMessage = async (
    message: string,
    sessionId: string,
    imageUrls?: string[],
    files?: any[]
): Promise<string> => {
    try {
        const requestBody: ChatRequest = {
            msg: message,
            msg_id: sessionId,
            image_urls: imageUrls,
            files: files,
        };

        console.log('📤 Sending chat request to Bedrock:', requestBody);

        const response = await fetchWithAuth(`${API_BASE_URL}/chat`, {
            method: 'POST',
            body: JSON.stringify(requestBody),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));

            if (response.status === 401) {
                throw new Error(
                    'Authentication required. Please sign in again.'
                );
            }

            throw new Error(
                errorData.error || `Server error: ${response.status}`
            );
        }

        const data: ChatResponse = await response.json();
        console.log('📥 Received response from Bedrock:', data);

        return data.answer;
    } catch (error) {
        console.error('❌ Error sending chat message:', error);
        throw error;
    }
};

/**
 * Generate a unique session ID for new chats
 */
export const generateSessionId = (): string => {
    return Date.now().toString() + Math.random().toString(36).substring(2, 11);
};

/**
 * Create a new chat session
 */
export const createNewChat = async (
    sessionId: string,
    chatName: string
): Promise<string> => {
    const response = await fetchWithAuth(`${API_BASE_URL}/new_chat`, {
        method: 'POST',
        body: JSON.stringify({
            msg_id: sessionId,
            chat_name: chatName,
        }),
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.text();
};

/**
 * Get chat history for a specific session
 */
export const getChatHistory = async (
    sessionId: string
): Promise<ApiMessage[]> => {
    const response = await fetchWithAuth(
        `${API_BASE_URL}/retrieve_messages?msgId=${sessionId}`,
        {
            method: 'GET',
        }
    );

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data: ChatHistoryResponse = await response.json();
    return data.msgs;
};

/**
 * Get list of all chat sessions for the user
 */
export const getChatNames = async (): Promise<ChatNamesResponse['chats']> => {
    const response = await fetchWithAuth(
        `${API_BASE_URL}/get_chat_names`,
        {
            method: 'GET',
        }
    );

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data: ChatNamesResponse = await response.json();
    return data.chats;
};

/**
 * Delete a chat session
 */
export const deleteChat = async (sessionId: string): Promise<string> => {
    const response = await fetchWithAuth(`${API_BASE_URL}/delete_chat`, {
        method: 'POST',
        body: JSON.stringify({
            msg_id: sessionId,
        }),
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.text();
};

/**
 * Delete a specific message from a chat
 * Supports both message_index (old) and message_timestamp (new table)
 */
export const deleteMessage = async (
    sessionId: string,
    messageIndexOrTimestamp: number | string,
    deleteNext?: boolean
): Promise<any> => {
    console.log('📤 deleteMessage API called:', { sessionId, messageIndexOrTimestamp, deleteNext });

    // Build request body - support both timestamp (new table) and index (old table)
    const body: any = {
        msg_id: sessionId,
    };

    // If it's a string (ISO timestamp), use message_timestamp
    // If it's a number, use message_index
    if (typeof messageIndexOrTimestamp === 'string') {
        body.message_timestamp = messageIndexOrTimestamp;
        console.log('   Using message_timestamp:', messageIndexOrTimestamp);
    } else {
        body.message_index = messageIndexOrTimestamp;
        console.log('   Using message_index:', messageIndexOrTimestamp);
    }

    // Only include delete_next if explicitly set (allows server auto-detection)
    if (deleteNext !== undefined) {
        body.delete_next = deleteNext;
    }

    console.log('📤 DELETE request body:', body);

    const response = await fetchWithAuth(`${API_BASE_URL}/delete_message`, {
        method: 'POST',
        body: JSON.stringify(body),
    });

    console.log('📥 DELETE response status:', response.status);

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        console.error('❌ DELETE failed:', errorData);
        throw new Error(`Delete message failed: ${errorData.error || response.statusText}`);
    }

    const result = await response.json();
    console.log('✅ DELETE result:', result);
    return result;
};

/**
 * Edit a specific message in a chat
 * Supports both message_index (old) and message_timestamp (new table)
 */
export const editMessage = async (
    sessionId: string,
    messageIndexOrTimestamp: number | string,
    newContent: string
): Promise<string> => {
    console.log('📤 editMessage API called:', { sessionId, messageIndexOrTimestamp, newContent: newContent.substring(0, 50) });

    // Build request body - support both timestamp (new table) and index (old table)
    const body: any = {
        msg_id: sessionId,
        new_content: newContent,
    };

    // If it's a string (ISO timestamp), use message_timestamp
    // If it's a number, use message_index
    if (typeof messageIndexOrTimestamp === 'string') {
        body.message_timestamp = messageIndexOrTimestamp;
        console.log('   Using message_timestamp:', messageIndexOrTimestamp);
    } else {
        body.message_index = messageIndexOrTimestamp;
        console.log('   Using message_index:', messageIndexOrTimestamp);
    }

    console.log('📤 EDIT request body:', body);

    const response = await fetchWithAuth(`${API_BASE_URL}/edit_message`, {
        method: 'POST',
        body: JSON.stringify(body),
    });

    console.log('📥 EDIT response status:', response.status);

    if (!response.ok) {
        let errorData;
        const responseText = await response.text();
        console.error('❌ EDIT failed - Response text:', responseText);

        try {
            errorData = JSON.parse(responseText);
        } catch (parseError) {
            console.error('❌ Failed to parse error response as JSON:', parseError);
            errorData = { error: responseText || 'Unknown error' };
        }

        console.error('❌ EDIT failed - Error data:', errorData);
        throw new Error(`Edit message failed: ${errorData.error || errorData.detail || response.statusText}`);
    }

    let result;
    const responseText = await response.text();
    console.log('📥 EDIT response text:', responseText);

    try {
        result = JSON.parse(responseText);
    } catch (parseError) {
        console.error('❌ Failed to parse successful response as JSON:', parseError);
        console.error('❌ Response was:', responseText);
        throw new Error(`Failed to parse edit response: ${parseError instanceof Error ? parseError.message : 'Unknown error'}`);
    }

    console.log('✅ EDIT result:', result);

    if (!result.new_ai_response) {
        console.error('❌ No new_ai_response in result:', result);
        throw new Error('Edit succeeded but no AI response was returned');
    }

    return result.new_ai_response;
};

/**
 * Get list of available AI models
 */
export const getAvailableModels = async (): Promise<Model[]> => {
    const response = await fetchWithAuth(`${API_BASE_URL}/get_models`, {
        method: 'GET',
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data: ModelsResponse = await response.json();
    return data.models;
};

/**
 * Get the currently selected model
 */
export const getCurrentModel = async (): Promise<CurrentModelResponse> => {
    const response = await fetchWithAuth(`${API_BASE_URL}/get_current_model`, {
        method: 'GET',
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
};

/**
 * Change the current AI model
 */
export const changeModel = async (modelName: string): Promise<ChangeModelResponse> => {
    const response = await fetchWithAuth(`${API_BASE_URL}/change_model`, {
        method: 'POST',
        body: JSON.stringify({
            model_name: modelName,
        }),
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
};

export default {
    sendChatMessage,
    generateSessionId,
    createNewChat,
    getChatHistory,
    getChatNames,
    deleteChat,
    deleteMessage,
    editMessage,
    getAvailableModels,
    getCurrentModel,
    changeModel,
};
