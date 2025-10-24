import React, { useState } from 'react';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    ScrollView,
    Alert,
    ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../contexts/AuthContext';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { RootStackParamList } from '../navigation/AppNavigator';

interface ProfileScreenProps {
    userEmail?: string;
}

type ProfileScreenNavigationProp = StackNavigationProp<RootStackParamList>;

const ProfileScreen: React.FC<ProfileScreenProps> = () => {
    const { user, signOut, deleteAccount } = useAuth();
    const [isLoading, setIsLoading] = useState(false);
    const navigation = useNavigation<ProfileScreenNavigationProp>();

    const handleLogout = () => {
        Alert.alert('Logout', 'Are you sure you want to logout?', [
            {
                text: 'Cancel',
                style: 'cancel',
            },
            {
                text: 'Logout',
                style: 'destructive',
                onPress: async () => {
                    setIsLoading(true);
                    try {
                        await signOut();
                    } catch (error: any) {
                        Alert.alert('Error', error.message || 'Failed to logout');
                    } finally {
                        setIsLoading(false);
                    }
                },
            },
        ]);
    };

    const handleDeleteAccount = () => {
        Alert.alert(
            'Delete Account',
            'Are you sure you want to delete your account? This action cannot be undone.',
            [
                {
                    text: 'Cancel',
                    style: 'cancel',
                },
                {
                    text: 'Delete',
                    style: 'destructive',
                    onPress: async () => {
                        setIsLoading(true);
                        try {
                            const response = await deleteAccount();
                            if (response.success) {
                                Alert.alert('Success', 'Your account has been deleted');
                            } else {
                                Alert.alert('Error', response.message);
                            }
                        } catch (error: any) {
                            Alert.alert('Error', error.message || 'Failed to delete account');
                        } finally {
                            setIsLoading(false);
                        }
                    },
                },
            ]
        );
    };

    const handleAbout = () => {
        navigation.navigate('About');
    };

    if (isLoading) {
        return (
            <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color="#007AFF" />
            </View>
        );
    }

    return (
        <ScrollView style={styles.container}>
            <View style={styles.header}>
                <View style={styles.avatarContainer}>
                    <Ionicons name="person-circle" size={80} color="#007AFF" />
                </View>
                <Text style={styles.username}>{user?.username || 'Profile'}</Text>
                <Text style={styles.email}>{user?.email || 'No email'}</Text>
            </View>

            <View style={styles.section}>
                <Text style={styles.sectionTitle}>Account</Text>

                <TouchableOpacity style={styles.menuItem} onPress={handleAbout}>
                    <View style={styles.menuItemLeft}>
                        <Ionicons
                            name="information-circle-outline"
                            size={24}
                            color="#666"
                        />
                        <Text style={styles.menuItemText}>About</Text>
                    </View>
                    <Ionicons name="chevron-forward" size={20} color="#999" />
                </TouchableOpacity>

                <TouchableOpacity style={styles.menuItem} onPress={handleDeleteAccount}>
                    <View style={styles.menuItemLeft}>
                        <Ionicons
                            name="trash-outline"
                            size={24}
                            color="#FF3B30"
                        />
                        <Text style={[styles.menuItemText, styles.deleteText]}>
                            Delete Account
                        </Text>
                    </View>
                    <Ionicons name="chevron-forward" size={20} color="#999" />
                </TouchableOpacity>
            </View>

            <View style={styles.section}>
                <TouchableOpacity
                    style={[styles.menuItem, styles.logoutItem]}
                    onPress={handleLogout}
                >
                    <View style={styles.menuItemLeft}>
                        <Ionicons
                            name="log-out-outline"
                            size={24}
                            color="#FF3B30"
                        />
                        <Text style={[styles.menuItemText, styles.logoutText]}>
                            Logout
                        </Text>
                    </View>
                </TouchableOpacity>
            </View>

            <View style={styles.footer}>
                <Text style={styles.footerText}>Study Chatbot</Text>
                <Text style={styles.footerSubtext}>Version 1.0.0</Text>
            </View>
        </ScrollView>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#F8F8F8',
    },
    loadingContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: '#F8F8F8',
    },
    backButton: {
        flexDirection: 'row',
        alignItems: 'center',
        padding: 16,
        paddingTop: 60,
    },
    backText: {
        fontSize: 16,
        color: '#007AFF',
        marginLeft: 8,
    },
    header: {
        backgroundColor: '#FFFFFF',
        alignItems: 'center',
        paddingTop: 40,
        paddingBottom: 30,
        borderBottomWidth: 1,
        borderBottomColor: '#E0E0E0',
    },
    avatarContainer: {
        marginBottom: 15,
    },
    username: {
        fontSize: 24,
        fontWeight: 'bold' as 'bold',
        color: '#000',
        marginBottom: 5,
    },
    email: {
        fontSize: 16,
        color: '#666',
    },
    section: {
        backgroundColor: '#FFFFFF',
        marginTop: 20,
        borderTopWidth: 1,
        borderBottomWidth: 1,
        borderColor: '#E0E0E0',
    },
    sectionTitle: {
        fontSize: 16,
        fontWeight: '600' as '600',
        color: '#666',
        paddingHorizontal: 20,
        paddingTop: 15,
        paddingBottom: 10,
        textTransform: 'uppercase' as 'uppercase',
        letterSpacing: 0.5,
    },
    menuItem: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: 20,
        paddingVertical: 15,
        borderBottomWidth: 1,
        borderBottomColor: '#F0F0F0',
    },
    menuItemLeft: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    menuItemText: {
        fontSize: 16,
        color: '#000',
        marginLeft: 15,
    },
    logoutItem: {
        borderBottomWidth: 0,
    },
    logoutText: {
        color: '#FF3B30',
    },
    deleteText: {
        color: '#FF3B30',
    },
    footer: {
        alignItems: 'center',
        paddingVertical: 40,
    },
    footerText: {
        fontSize: 16,
        fontWeight: '600' as '600',
        color: '#666',
        marginBottom: 5,
    },
    footerSubtext: {
        fontSize: 14,
        color: '#999',
    },
});

export default ProfileScreen;
