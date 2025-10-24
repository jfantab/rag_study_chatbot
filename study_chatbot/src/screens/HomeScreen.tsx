import React from 'react';
import {
    View,
    Text,
    StyleSheet,
    ScrollView,
    TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';

type TabParamList = {
    Home: undefined;
    Chat: undefined;
    Profile: undefined;
};

type NavigationProp = BottomTabNavigationProp<TabParamList>;

const HomeScreen: React.FC = () => {
    const navigation = useNavigation<NavigationProp>();

    const quickActions = [
        {
            id: 'chat',
            title: 'Start Chat',
            subtitle: 'Ask questions & get help',
            icon: 'chatbubble',
            onPress: () => navigation.navigate('Chat'),
            color: '#007AFF',
        },
        {
            id: 'upload',
            title: 'Upload Files',
            subtitle: 'Add documents to knowledge base',
            icon: 'cloud-upload',
            onPress: () => (navigation as any).navigate('FileUpload'),
            color: '#FF9500',
        },
    ];

    return (
        <SafeAreaView style={styles.container}>
            <ScrollView showsVerticalScrollIndicator={false}>
                {/* Header */}
                <View style={styles.header}>
                    <Text style={styles.greeting}>Welcome back!</Text>
                    <Text style={styles.subtitle}>
                        Ready to learn something new?
                    </Text>
                </View>

                {/* Quick Actions */}
                <View style={styles.actionsContainer}>
                    <Text style={styles.sectionTitle}>Quick Actions</Text>
                    <View style={styles.actionsGrid}>
                        {quickActions.map((action) => (
                            <TouchableOpacity
                                key={action.id}
                                style={[
                                    styles.actionCard,
                                    { borderLeftColor: action.color },
                                ]}
                                onPress={action.onPress}
                                activeOpacity={0.7}
                            >
                                <View style={styles.actionHeader}>
                                    <View
                                        style={[
                                            styles.iconContainer,
                                            { backgroundColor: action.color },
                                        ]}
                                    >
                                        <Ionicons
                                            name={
                                                action.icon as keyof typeof Ionicons.glyphMap
                                            }
                                            size={24}
                                            color="white"
                                        />
                                    </View>
                                    <View style={styles.actionText}>
                                        <Text style={styles.actionTitle}>
                                            {action.title}
                                        </Text>
                                        <Text style={styles.actionSubtitle}>
                                            {action.subtitle}
                                        </Text>
                                    </View>
                                </View>
                                <Ionicons
                                    name="chevron-forward"
                                    size={20}
                                    color="#999"
                                />
                            </TouchableOpacity>
                        ))}
                    </View>
                </View>
            </ScrollView>
        </SafeAreaView>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#F8F9FA',
    },
    header: {
        padding: 20,
        paddingTop: 10,
    },
    greeting: {
        fontSize: 28,
        fontWeight: 'bold' as 'bold',
        color: '#1D1D1F',
        marginBottom: 4,
    },
    subtitle: {
        fontSize: 16,
        color: '#6B7280',
    },
    sectionTitle: {
        fontSize: 20,
        fontWeight: '600' as '600',
        color: '#1D1D1F',
        marginBottom: 16,
    },
    actionsContainer: {
        padding: 20,
        paddingTop: 0,
    },
    actionsGrid: {
        gap: 12,
    },
    actionCard: {
        backgroundColor: 'white',
        padding: 16,
        borderRadius: 12,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderLeftWidth: 4,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.1,
        shadowRadius: 4,
        elevation: 3,
    },
    actionHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        flex: 1,
    },
    iconContainer: {
        width: 48,
        height: 48,
        borderRadius: 24,
        justifyContent: 'center',
        alignItems: 'center',
        marginRight: 16,
    },
    actionText: {
        flex: 1,
    },
    actionTitle: {
        fontSize: 16,
        fontWeight: '600' as '600',
        color: '#1D1D1F',
        marginBottom: 2,
    },
    actionSubtitle: {
        fontSize: 14,
        color: '#6B7280',
    },
    recentContainer: {
        padding: 20,
        paddingTop: 0,
        paddingBottom: 40,
    },
    recentCard: {
        backgroundColor: 'white',
        borderRadius: 12,
        padding: 16,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.1,
        shadowRadius: 4,
        elevation: 3,
    },
    recentItem: {
        flexDirection: 'row',
        alignItems: 'center',
        paddingVertical: 12,
        borderBottomWidth: 1,
        borderBottomColor: '#F3F4F6',
    },
    recentText: {
        marginLeft: 12,
        flex: 1,
    },
    recentTitle: {
        fontSize: 14,
        fontWeight: '500' as '500',
        color: '#1D1D1F',
    },
    recentTime: {
        fontSize: 12,
        color: '#6B7280',
        marginTop: 2,
    },
});

export default HomeScreen;
