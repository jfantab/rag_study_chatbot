import React, { createContext, useContext, useState, useRef, ReactNode } from 'react';
import { Animated, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

interface ToastContextType {
    showToast: (message: string, type?: 'success' | 'error' | 'info') => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [toastMessage, setToastMessage] = useState<string>('');
    const [toastType, setToastType] = useState<'success' | 'error' | 'info'>('info');
    const [isVisible, setIsVisible] = useState(false);
    const fadeAnim = useRef(new Animated.Value(0)).current;

    const showToast = (message: string, type: 'success' | 'error' | 'info' = 'info') => {
        setToastMessage(message);
        setToastType(type);
        setIsVisible(true);

        // Fade in
        Animated.sequence([
            Animated.timing(fadeAnim, {
                toValue: 1,
                duration: 200,
                useNativeDriver: true,
            }),
            Animated.delay(2500),
            // Fade out
            Animated.timing(fadeAnim, {
                toValue: 0,
                duration: 200,
                useNativeDriver: true,
            }),
        ]).start(() => {
            setIsVisible(false);
        });
    };

    const getIconName = (): keyof typeof Ionicons.glyphMap => {
        switch (toastType) {
            case 'success':
                return 'checkmark-circle';
            case 'error':
                return 'close-circle';
            case 'info':
            default:
                return 'information-circle';
        }
    };

    const getIconColor = (): string => {
        switch (toastType) {
            case 'success':
                return '#4CAF50';
            case 'error':
                return '#FF3B30';
            case 'info':
            default:
                return '#007AFF';
        }
    };

    return (
        <ToastContext.Provider value={{ showToast }}>
            {children}
            {isVisible && (
                <Animated.View
                    style={[
                        styles.toast,
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
                    <Ionicons name={getIconName()} size={20} color={getIconColor()} />
                    <Text style={styles.toastText}>{toastMessage}</Text>
                </Animated.View>
            )}
        </ToastContext.Provider>
    );
};

export const useToast = () => {
    const context = useContext(ToastContext);
    if (!context) {
        throw new Error('useToast must be used within a ToastProvider');
    }
    return context;
};

const styles = StyleSheet.create({
    toast: {
        position: 'absolute',
        bottom: 100,
        left: '50%',
        marginLeft: -150,
        width: 300,
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
        zIndex: 9999,
    },
    toastText: {
        fontSize: 14,
        fontWeight: '600',
        color: '#333',
        flexShrink: 1,
    },
});
