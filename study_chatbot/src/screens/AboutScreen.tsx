import React from 'react';
import {
    View,
    Text,
    StyleSheet,
    ScrollView,
    TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';

interface AboutScreenProps {
    navigation: any;
}

const AboutScreen: React.FC<AboutScreenProps> = ({ navigation }) => {
    const features = [
        {
            icon: 'chatbubbles-outline',
            title: 'AI Chat',
            description: 'Engage in conversations with advanced AI models',
        },
        {
            icon: 'swap-horizontal-outline',
            title: 'Model Switching',
            description: 'Switch between different AI models on the fly',
        },
        {
            icon: 'time-outline',
            title: 'Chat History',
            description: 'Access and manage your previous conversations',
        },
        {
            icon: 'person-outline',
            title: 'User Authentication',
            description: 'Secure login and account management via AWS Cognito',
        },
        {
            icon: 'sync-outline',
            title: 'Data Persistence',
            description: 'Your chats are saved and synced across sessions',
        },
        {
            icon: 'shield-checkmark-outline',
            title: 'Encrypted Storage',
            description: 'Your data is encrypted at rest for security',
        },
    ];

    return (
        <SafeAreaView style={styles.container} edges={['top']}>
            <View style={styles.header}>
                <TouchableOpacity
                    style={styles.backButton}
                    onPress={() => navigation.goBack()}
                >
                    <Ionicons name="chevron-back" size={24} color="#007AFF" />
                </TouchableOpacity>
                <Text style={styles.headerTitle}>About</Text>
                <View style={styles.headerSpacer} />
            </View>

            <ScrollView style={styles.scrollContent}>
                <View style={styles.content}>
                    <View style={styles.appInfo}>
                        <View style={styles.appIcon}>
                            <Ionicons
                                name="chatbubbles"
                                size={60}
                                color="#007AFF"
                            />
                        </View>
                        <Text style={styles.appName}>Study Chatbot</Text>
                        <Text style={styles.appVersion}>Version 1.0.0</Text>
                        <Text style={styles.appDescription}>
                            An intelligent study chatbot powered by advanced AI
                            technology, designed to provide helpful and engaging
                            conversations for learning.
                        </Text>
                    </View>

                    <View style={styles.section}>
                        <Text style={styles.sectionTitle}>Key Features</Text>
                        {features.map((feature, index) => (
                            <View key={feature.title} style={styles.featureItem}>
                                <View style={styles.featureIcon}>
                                    <Ionicons
                                        name={feature.icon as any}
                                        size={24}
                                        color="#007AFF"
                                    />
                                </View>
                                <View style={styles.featureContent}>
                                    <Text style={styles.featureTitle}>
                                        {feature.title}
                                    </Text>
                                    <Text style={styles.featureDescription}>
                                        {feature.description}
                                    </Text>
                                </View>
                            </View>
                        ))}
                    </View>

                    <View style={styles.section}>
                        <Text style={styles.sectionTitle}>
                            Technology Stack
                        </Text>
                        <View style={styles.techItem}>
                            <Text style={styles.techLabel}>Frontend:</Text>
                            <Text style={styles.techValue}>
                                React Native with Expo
                            </Text>
                        </View>
                        <View style={styles.techItem}>
                            <Text style={styles.techLabel}>AI Backend:</Text>
                            <Text style={styles.techValue}>AWS Bedrock</Text>
                        </View>
                        <View style={styles.techItem}>
                            <Text style={styles.techLabel}>
                                Authentication:
                            </Text>
                            <Text style={styles.techValue}>AWS Cognito</Text>
                        </View>
                        <View style={styles.techItem}>
                            <Text style={styles.techLabel}>Database:</Text>
                            <Text style={styles.techValue}>DynamoDB</Text>
                        </View>
                        <View style={styles.techItem}>
                            <Text style={styles.techLabel}>Navigation:</Text>
                            <Text style={styles.techValue}>
                                React Navigation
                            </Text>
                        </View>
                    </View>

                    <View style={styles.footer}>
                        <Text style={styles.footerText}>
                            Built with ❤️ for seamless AI conversations
                        </Text>
                    </View>
                </View>
            </ScrollView>
        </SafeAreaView>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#F8F8F8',
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: 16,
        paddingVertical: 12,
        backgroundColor: '#FFFFFF',
        borderBottomWidth: 1,
        borderBottomColor: '#E0E0E0',
    },
    backButton: {
        padding: 8,
    },
    headerTitle: {
        fontSize: 18,
        fontWeight: '600',
        color: '#000',
    },
    headerSpacer: {
        width: 40,
    },
    scrollContent: {
        flex: 1,
    },
    content: {
        padding: 20,
    },
    appInfo: {
        alignItems: 'center',
        backgroundColor: '#FFFFFF',
        borderRadius: 12,
        padding: 24,
        marginBottom: 20,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.1,
        shadowRadius: 3,
        elevation: 2,
    },
    appIcon: {
        marginBottom: 16,
    },
    appName: {
        fontSize: 24,
        fontWeight: 'bold',
        color: '#000',
        marginBottom: 4,
    },
    appVersion: {
        fontSize: 16,
        color: '#666',
        marginBottom: 16,
    },
    appDescription: {
        fontSize: 14,
        color: '#666',
        textAlign: 'center',
        lineHeight: 20,
    },
    section: {
        backgroundColor: '#FFFFFF',
        borderRadius: 12,
        padding: 20,
        marginBottom: 20,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.1,
        shadowRadius: 3,
        elevation: 2,
    },
    sectionTitle: {
        fontSize: 18,
        fontWeight: '600',
        color: '#000',
        marginBottom: 16,
    },
    featureItem: {
        flexDirection: 'row',
        alignItems: 'flex-start',
        marginBottom: 16,
    },
    featureIcon: {
        width: 40,
        height: 40,
        borderRadius: 20,
        backgroundColor: '#F0F8FF',
        alignItems: 'center',
        justifyContent: 'center',
        marginRight: 12,
    },
    featureContent: {
        flex: 1,
    },
    featureTitle: {
        fontSize: 16,
        fontWeight: '600',
        color: '#000',
        marginBottom: 4,
    },
    featureDescription: {
        fontSize: 14,
        color: '#666',
        lineHeight: 18,
    },
    techItem: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: 8,
    },
    techLabel: {
        fontSize: 14,
        fontWeight: '600',
        color: '#000',
        width: 110,
    },
    techValue: {
        fontSize: 14,
        color: '#666',
        flex: 1,
    },
    footer: {
        alignItems: 'center',
        paddingVertical: 20,
    },
    footerText: {
        fontSize: 14,
        color: '#666',
        textAlign: 'center',
    },
});

export default AboutScreen;
