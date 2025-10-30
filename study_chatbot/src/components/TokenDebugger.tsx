import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Alert } from 'react-native';
import { getIdToken } from '../services/cognitoService';
import * as Clipboard from 'expo-clipboard';

/**
 * TokenDebugger Component
 * Temporary component to display and copy JWT token for testing
 *
 * Usage: Add this to any screen (e.g., ProfileScreen or ChatScreen)
 * <TokenDebugger />
 */
const TokenDebugger: React.FC = () => {
    const [token, setToken] = useState<string>('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string>('');

    useEffect(() => {
        fetchToken();
    }, []);

    const fetchToken = async () => {
        setLoading(true);
        setError('');
        try {
            const idToken = await getIdToken();
            if (idToken) {
                setToken(idToken);
            } else {
                setError('No token available - user may not be authenticated');
            }
        } catch (err: any) {
            setError(err.message || 'Failed to get token');
            console.error('❌ Error getting token:', err);
        } finally {
            setLoading(false);
        }
    };

    const copyToClipboard = async () => {
        if (token) {
            await Clipboard.setStringAsync(token);
            Alert.alert('Copied!', 'JWT token copied to clipboard');
        }
    };

    const copyAsCurlCommand = async () => {
        if (token) {
            const curlCommand = `curl -H "Authorization: Bearer ${token}" "https://jfantabai.xyz/get_chat_names"`;
            await Clipboard.setStringAsync(curlCommand);
            Alert.alert('Copied!', 'Curl command copied to clipboard. Paste in terminal to test.');
        }
    };

    if (loading) {
        return (
            <View style={styles.container}>
                <Text style={styles.title}>Loading token...</Text>
            </View>
        );
    }

    if (error) {
        return (
            <View style={styles.container}>
                <Text style={styles.title}>Token Debugger</Text>
                <Text style={styles.error}>Error: {error}</Text>
                <TouchableOpacity style={styles.button} onPress={fetchToken}>
                    <Text style={styles.buttonText}>Retry</Text>
                </TouchableOpacity>
            </View>
        );
    }

    return (
        <View style={styles.container}>
            <Text style={styles.title}>🔑 JWT Token Debugger</Text>

            <View style={styles.infoBox}>
                <Text style={styles.label}>Token Length:</Text>
                <Text style={styles.value}>{token.length} characters</Text>
            </View>

            <View style={styles.infoBox}>
                <Text style={styles.label}>Token Preview:</Text>
                <Text style={styles.tokenPreview} numberOfLines={3}>
                    {token.substring(0, 100)}...
                </Text>
            </View>

            <View style={styles.buttonContainer}>
                <TouchableOpacity style={styles.button} onPress={copyToClipboard}>
                    <Text style={styles.buttonText}>Copy Token</Text>
                </TouchableOpacity>

                <TouchableOpacity style={[styles.button, styles.secondaryButton]} onPress={copyAsCurlCommand}>
                    <Text style={styles.buttonText}>Copy as Curl</Text>
                </TouchableOpacity>

                <TouchableOpacity style={[styles.button, styles.refreshButton]} onPress={fetchToken}>
                    <Text style={styles.buttonText}>Refresh</Text>
                </TouchableOpacity>
            </View>

            <View style={styles.instructionsBox}>
                <Text style={styles.instructionsTitle}>📋 How to use:</Text>
                <Text style={styles.instructions}>
                    1. Click "Copy Token" to copy the JWT token{'\n'}
                    2. Or click "Copy as Curl" to get a ready-to-run test command{'\n'}
                    3. Paste in terminal to test the endpoint{'\n'}
                    {'\n'}
                    <Text style={styles.instructionsBold}>Or use in terminal directly:</Text>{'\n'}
                    curl -H "Authorization: Bearer YOUR_TOKEN" https://jfantabai.xyz/get_chat_names
                </Text>
            </View>

            <Text style={styles.warning}>
                ⚠️ Remove this component in production!
            </Text>
        </View>
    );
};

const styles = StyleSheet.create({
    container: {
        backgroundColor: '#F8F9FA',
        padding: 16,
        margin: 16,
        borderRadius: 12,
        borderWidth: 2,
        borderColor: '#FF6B6B',
    },
    title: {
        fontSize: 18,
        fontWeight: 'bold',
        color: '#333',
        marginBottom: 16,
        textAlign: 'center',
    },
    infoBox: {
        backgroundColor: '#FFF',
        padding: 12,
        borderRadius: 8,
        marginBottom: 12,
    },
    label: {
        fontSize: 12,
        fontWeight: '600',
        color: '#666',
        marginBottom: 4,
    },
    value: {
        fontSize: 14,
        color: '#333',
    },
    tokenPreview: {
        fontSize: 11,
        color: '#333',
        fontFamily: 'Courier',
        backgroundColor: '#F0F0F0',
        padding: 8,
        borderRadius: 4,
    },
    buttonContainer: {
        flexDirection: 'row',
        gap: 8,
        marginTop: 12,
        marginBottom: 16,
    },
    button: {
        flex: 1,
        backgroundColor: '#007AFF',
        paddingVertical: 12,
        paddingHorizontal: 16,
        borderRadius: 8,
        alignItems: 'center',
    },
    secondaryButton: {
        backgroundColor: '#34C759',
    },
    refreshButton: {
        backgroundColor: '#666',
        flex: 0.5,
    },
    buttonText: {
        color: '#FFF',
        fontSize: 14,
        fontWeight: '600',
    },
    instructionsBox: {
        backgroundColor: '#E3F2FD',
        padding: 12,
        borderRadius: 8,
        marginBottom: 12,
    },
    instructionsTitle: {
        fontSize: 14,
        fontWeight: '600',
        color: '#1976D2',
        marginBottom: 8,
    },
    instructions: {
        fontSize: 12,
        color: '#333',
        lineHeight: 18,
    },
    instructionsBold: {
        fontWeight: '600',
    },
    error: {
        color: '#FF3B30',
        fontSize: 14,
        marginBottom: 12,
        textAlign: 'center',
    },
    warning: {
        fontSize: 12,
        color: '#FF6B6B',
        fontWeight: '600',
        textAlign: 'center',
        fontStyle: 'italic',
    },
});

export default TokenDebugger;
