import React from 'react';
import { View, StyleSheet } from 'react-native';
import { ChatProvider } from './src/contexts/ChatContext';
import { AuthProvider } from './src/contexts/AuthContext';
import { ToastProvider } from './src/contexts/ToastContext';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import AppNavigator from './src/navigation/AppNavigator';

export default function App() {
    return (
        <SafeAreaProvider>
            <SafeAreaView style={styles.container}>
                <AuthProvider>
                    <ToastProvider>
                        <ChatProvider>
                            <View style={styles.container}>
                                <AppNavigator />
                            </View>
                        </ChatProvider>
                    </ToastProvider>
                </AuthProvider>
            </SafeAreaView>
        </SafeAreaProvider>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#fff',
    },
});
